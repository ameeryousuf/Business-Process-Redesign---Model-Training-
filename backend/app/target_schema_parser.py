import json
import re
from pathlib import Path

from app.bpmn_parser import parse_bpmn_string, ParsedProcess
from app.metrics_calculator import calculate_metrics, calculate_theoretical_metrics
from app import currency

ACTIVITY_ID_PATTERN = re.compile(r"^Activity_(\d+)$")
SUBPROCESS_ID_PATTERN = re.compile(r"^SubProcess_(\d+)$")

START_ID = "StartEvent_1"
MAIN_END_ID = "EndEvent_1"


class SubprocessNotFoundError(Exception):
    pass


class CircularSubprocessError(Exception):
    pass


def _activity_task_id(xml_element_id):
    match = ACTIVITY_ID_PATTERN.match(xml_element_id or "")
    return int(match.group(1)) if match else None


def _subprocess_child_process_id(xml_element_id):
    match = SUBPROCESS_ID_PATTERN.match(xml_element_id or "")
    return int(match.group(1)) if match else None


def _compute_task_metrics(task_record):
    process_time_h = (task_record.get("expected_process_time") or 0) / 60.0
    waiting_time_h = (task_record.get("expected_waiting_time") or 0) / 60.0
    rework_time_h = (task_record.get("expected_rework_time") or 0) / 60.0
    duration = process_time_h + waiting_time_h + rework_time_h
    # Theoretical Cycle Time uses processing time only -- per the reference cost/cycle
    # time spec, Tproc(path) excludes both waiting time AND rework time. Rework still
    # counts toward Duration (and toward labor cost, below) but not toward the
    # "value-adding" theoretical/processing time used for CTE.
    processing_time = process_time_h

    # Labor cost basis per the cost-model spec: Hwork = (Tproc + Trework) / 60 --
    # labor hours accrue during active work (processing AND rework), never during
    # waiting (non-working queue time).
    work_hours = process_time_h + rework_time_h

    cost = 0.0
    rework_cost = 0.0
    resource = None
    raci = []

    for job_task in task_record.get("jobTasks") or []:
        job = job_task.get("job") or {}
        allocation_pct = float(job_task.get("time_allocation_percentage") or 0)
        allocation = allocation_pct / 100.0
        rate_usd = currency.convert_to_usd(job.get("hourlyRate") or 0, job.get("currencyType"))
        cost += work_hours * allocation * rate_usd
        # The rework-attributable slice of this task's cost -- same per-role rate/
        # allocation, just against rework hours only instead of (process + rework).
        rework_cost += rework_time_h * allocation * rate_usd

        role = job_task.get("role")
        if role == "R":
            resource = job.get("name")

        raci.append({
            "role": role,
            "name": job.get("name"),
            "time_allocation_percentage": allocation_pct
        })

    return {
        "duration": duration,
        "processing_time": processing_time,
        "waiting_time_hours": waiting_time_h,
        "rework_time_hours": rework_time_h,
        "cost": round(cost, 2),
        "rework_cost": round(rework_cost, 2),
        "resource": resource,
        "raci": raci
    }


def _load_subprocess_data(child_process_id, source):
    """`source` is either a directory path (reads <id>.json from disk -- the local
    dataset/testing mode) or a dict already keyed by process_id (an in-memory bundle
    of subprocess data the caller already fetched, e.g. from the live Digital Twin
    API) -- the frontend recursively fetches every referenced subprocess and bundles
    them together in one request, so the backend never needs its own API credentials.
    """
    if isinstance(source, dict):
        if child_process_id not in source:
            raise SubprocessNotFoundError(
                f"The process you are redesigning has subprocess {child_process_id}, "
                f"whose data is not available."
            )
        return source[child_process_id]

    subprocess_path = Path(source) / f"{child_process_id}.json"
    if not subprocess_path.exists():
        raise SubprocessNotFoundError(
            f"The process you are redesigning has subprocess {child_process_id}, "
            f"whose data is not available."
        )

    with open(subprocess_path, "r", encoding="utf-8") as f:
        return json.load(f)


def _resolve_subprocess(child_process_id, source, currently_resolving):
    if child_process_id in currently_resolving:
        raise CircularSubprocessError(
            f"Circular subprocess reference detected while resolving process {child_process_id}."
        )

    sub_data = _load_subprocess_data(child_process_id, source)

    sub_parsed = _parse_target_process(
        sub_data, source, currently_resolving | {child_process_id}
    )
    sub_metrics = calculate_metrics(sub_parsed)
    sub_theoretical = calculate_theoretical_metrics(sub_parsed)
    # Same expectation machinery as duration/cost, just pointed at the waiting-time,
    # rework-time, and rework-cost fields instead -- gives the subprocess-as-a-whole
    # an aggregate breakdown consistent with how its own tasks are broken down.
    sub_waiting = calculate_metrics(sub_parsed, time_field="waiting_time_hours")
    sub_rework_time = calculate_metrics(sub_parsed, time_field="rework_time_hours")
    sub_rework_cost = calculate_metrics(sub_parsed, cost_field="rework_cost")

    return {
        "duration": sub_metrics["total_time_hours"],
        "processing_time": sub_theoretical["theoretical_time_hours"],
        "cost": sub_metrics["total_cost_usd"],
        "waiting_time_hours": sub_waiting["total_time_hours"],
        "rework_time_hours": sub_rework_time["total_time_hours"],
        "rework_cost": sub_rework_cost["total_cost_usd"]
    }


def _enrich_from_relations(parsed, data, processes_dir, currently_resolving):
    """Fills in duration/cost/resource/RACI/probabilities on a graph that was already
    built from `bpmn_xml`, cross-referencing the relational fields (`process_task`,
    `gateways[].branches[].probability`, `jobTasks`, `value_classification`,
    `child_process_id`) by matching XML element ids/gateway names against them.
    """
    process_task_by_task_id = {
        pt["task_id"]: pt for pt in data.get("process_task", []) if pt.get("task_id") is not None
    }
    process_task_by_child_process_id = {
        pt["child_process_id"]: pt for pt in data.get("process_task", [])
        if pt.get("child_process_id") is not None
    }

    for task in parsed.tasks:
        task["value_classification"] = None
        task["is_subprocess"] = False
        task["raci"] = []
        # Defaults for any task this loop doesn't end up matching against relational
        # data (e.g. an XML element with no corresponding process_task row) -- without
        # these, calculate_metrics(time_field="waiting_time_hours"/...) would treat the
        # field as simply absent rather than genuinely zero.
        task["waiting_time_hours"] = 0.0
        task["rework_time_hours"] = 0.0
        task["rework_cost"] = 0.0

        child_process_id = _subprocess_child_process_id(task["id"])
        if child_process_id is not None:
            pt = process_task_by_child_process_id.get(child_process_id)
            sub = _resolve_subprocess(child_process_id, processes_dir, currently_resolving)
            task["duration"] = sub["duration"]
            task["processing_time"] = sub["processing_time"]
            task["cost"] = sub["cost"]
            task["waiting_time_hours"] = sub["waiting_time_hours"]
            task["rework_time_hours"] = sub["rework_time_hours"]
            task["rework_cost"] = sub["rework_cost"]
            task["resource"] = None
            task["is_subprocess"] = True
            if pt is not None:
                task["value_classification"] = pt.get("value_classification")
            continue

        task_id = _activity_task_id(task["id"])
        if task_id is None or task_id not in process_task_by_task_id:
            continue

        pt = process_task_by_task_id[task_id]
        task["value_classification"] = pt.get("value_classification")

        task_record = pt.get("task") or {}
        metrics = _compute_task_metrics(task_record)
        task["duration"] = metrics["duration"]
        task["processing_time"] = metrics["processing_time"]
        task["cost"] = metrics["cost"]
        task["waiting_time_hours"] = metrics["waiting_time_hours"]
        task["rework_time_hours"] = metrics["rework_time_hours"]
        task["rework_cost"] = metrics["rework_cost"]
        task["resource"] = metrics["resource"]
        task["raci"] = metrics["raci"]
        task["name"] = task["name"] or task_record.get("task_name")

    xml_gateway_by_name = {g["name"]: g for g in parsed.gateways if g.get("name")}
    end_event_by_name = {e["name"]: e for e in parsed.end_events if e.get("name")}
    flows_by_source = {}
    for flow in parsed.flows:
        flows_by_source.setdefault(flow["source"], []).append(flow)

    gateway_name_by_pk_id = {g["gateway_pk_id"]: g.get("name") for g in data.get("gateways", [])}

    for gw in data.get("gateways", []):
        xml_gateway = xml_gateway_by_name.get(gw.get("name"))
        if xml_gateway is None:
            continue

        outgoing = flows_by_source.get(xml_gateway["id"], [])
        matched_flows = set()
        unresolved_branches = []

        for branch in gw.get("branches", []):
            probability = branch.get("probability")
            if probability is None:
                continue

            target_xml_id = None
            if branch.get("target_task_id") is not None:
                target_xml_id = f"Activity_{branch['target_task_id']}"
            elif branch.get("end_event_name"):
                end_event = end_event_by_name.get(branch["end_event_name"])
                if end_event is not None:
                    target_xml_id = end_event["id"]
            elif branch.get("target_gateway_id") is not None:
                target_gateway_name = gateway_name_by_pk_id.get(branch["target_gateway_id"])
                target_gateway = xml_gateway_by_name.get(target_gateway_name)
                if target_gateway is not None:
                    target_xml_id = target_gateway["id"]

            if target_xml_id is None:
                # Branch converges directly to a gateway/join with no explicit task or
                # named end event target (e.g. connect_to_end without an end_event_name).
                # Resolved below once flows matched by explicit target are excluded.
                unresolved_branches.append(probability)
                continue

            matched = False
            for flow in outgoing:
                if id(flow) in matched_flows:
                    continue
                if flow["target"] == target_xml_id:
                    flow["probability"] = probability
                    matched_flows.add(id(flow))
                    matched = True
                    break

            if not matched:
                # The branch's target_task_id doesn't match any direct outgoing flow --
                # the XML routes through an explicit join/converge gateway before reaching
                # that task (e.g. "Yes" -> Gateway_Join -> the actual task), so there's no
                # flow whose target is literally that task. Treat the same as an
                # unresolved branch so it can still be matched by position below, instead
                # of silently dropping the probability and leaving the flow at its default.
                unresolved_branches.append(probability)

        remaining_flows = [f for f in outgoing if id(f) not in matched_flows]
        if len(unresolved_branches) == 1 and len(remaining_flows) == 1:
            remaining_flows[0]["probability"] = unresolved_branches[0]


def _process_task_sort_key(pt):
    order = pt.get("order")
    # Rows with no order (data still "under construction") sort last, deterministically.
    return (order if order is not None else 10 ** 9, pt.get("task_id") or 0)


def _task_node_id(pt):
    if pt.get("child_process_id") is not None:
        return f"SubProcess_{pt['child_process_id']}"
    return f"Activity_{pt['task_id']}"


def _slugify(name):
    slug = re.sub(r"[^A-Za-z0-9]+", "_", name or "").strip("_")
    return slug or "End"


def _build_graph_from_relations(data, source, currently_resolving):
    """Builds a full ParsedProcess graph (tasks/gateways/flows/start/end events)
    directly from the relational `process_task[]` / `gateways[]` data -- no bpmn_xml
    involved at all. This is the fallback (and, for many processes, the only viable)
    construction path: the live system's generated BPMN XML is still under active
    development and is sometimes missing or malformed, so the graph must be derivable
    from the relational data alone.

    `process_task[].order` is the only ordering signal available, and it is NOT a
    strict "next task" pointer -- it reflects authoring/creation order, so a later
    `order` value can still represent an earlier step (e.g. a short alternate branch
    task created right after its gateway, while the main branch keeps extending with
    higher order values). To reconstruct real adjacency:
      - `gateways[].after_task_id` (or None, for "before the first task") pins a
        gateway to a specific position -- whatever normally would come next from that
        position is instead entirely replaced by the gateway's branches.
      - For a gateway's branches, the ONE branch whose `target_task_id` matches the
        task that would naturally come next in `order` is treated as continuing the
        main flow (falls through normally afterward). Any OTHER branch that targets a
        task is a short alternate path: after that task finishes, it goes straight to
        the process end (unless some other gateway is explicitly pinned to it via its
        own `after_task_id`).
    """
    parsed = ParsedProcess()

    process_tasks = sorted(
        [
            pt for pt in data.get("process_task", [])
            if pt.get("task_id") is not None or pt.get("child_process_id") is not None
        ],
        key=_process_task_sort_key
    )

    gateways = data.get("gateways", []) or []
    gateway_by_pk = {gw["gateway_pk_id"]: gw for gw in gateways if gw.get("gateway_pk_id") is not None}

    def gateway_node_id(gw):
        return f"Gateway_{gw['gateway_pk_id']}"

    gateway_by_after_task_id = {}
    for gw in gateways:
        gateway_by_after_task_id.setdefault(gw.get("after_task_id"), gw)

    parsed.start_events.append({"id": START_ID, "name": "Start"})
    parsed.end_events.append({"id": MAIN_END_ID, "name": "End"})
    end_node_by_name = {}

    def end_node_for_name(name):
        if not name:
            return MAIN_END_ID
        if name not in end_node_by_name:
            node_id = f"EndEvent_{_slugify(name)}"
            end_node_by_name[name] = node_id
            parsed.end_events.append({"id": node_id, "name": name})
        return end_node_by_name[name]

    # A branch target is a "jump" (a short alternate path, not a main-flow
    # continuation) if it does not match the task that would naturally come next
    # from the gateway's position in the raw `order` sequence.
    jump_target_task_ids = set()
    for gw in gateways:
        after_task_id = gw.get("after_task_id")
        if after_task_id is None:
            gw_idx = -1
        else:
            gw_idx = next(
                (i for i, pt in enumerate(process_tasks) if pt.get("task_id") == after_task_id), None
            )
            if gw_idx is None:
                continue

        natural_idx = gw_idx + 1
        natural_task_id = process_tasks[natural_idx].get("task_id") if natural_idx < len(process_tasks) else None

        for branch in gw.get("branches", []):
            target_task_id = branch.get("target_task_id")
            if target_task_id is not None and target_task_id != natural_task_id:
                jump_target_task_ids.add(target_task_id)

    # The main trunk excludes jump-target tasks entirely -- they're short dead-end
    # alternate branches, not steps on the through-line, so they must not be treated
    # as "next" for whatever plain (non-gateway-pinned) task precedes them in `order`.
    trunk_tasks = [pt for pt in process_tasks if pt.get("task_id") not in jump_target_task_ids]
    trunk_node_ids = [_task_node_id(pt) for pt in trunk_tasks]
    trunk_index_by_node_id = {node_id: i for i, node_id in enumerate(trunk_node_ids)}

    def node_after_trunk_position(idx):
        """The node that comes immediately after trunk position `idx` (-1 = before
        the first trunk task) if nothing else intervenes: an explicit gateway pinned
        to that position takes priority over the next trunk task; with nothing left,
        flow reaches the shared end event."""
        gw = None
        if idx < 0:
            gw = gateway_by_after_task_id.get(None)
        else:
            task_id = trunk_tasks[idx].get("task_id")
            if task_id is not None:
                gw = gateway_by_after_task_id.get(task_id)

        if gw is not None:
            return gateway_node_id(gw)

        next_idx = idx + 1
        if next_idx < len(trunk_node_ids):
            return trunk_node_ids[next_idx]
        return MAIN_END_ID

    def add_flow(source_id, target_id, probability):
        parsed.flows.append({
            "id": f"Flow_{source_id}_{target_id}_{len(parsed.flows)}",
            "source": source_id,
            "target": target_id,
            "probability": probability
        })

    # --- Task nodes ---
    for pt in process_tasks:
        node_id = _task_node_id(pt)
        task = {
            "id": node_id,
            "name": None,
            "value_classification": pt.get("value_classification"),
            "is_subprocess": False,
            "raci": []
        }

        child_process_id = pt.get("child_process_id")
        if child_process_id is not None:
            sub = _resolve_subprocess(child_process_id, source, currently_resolving)
            child_process = pt.get("child_process") or {}
            task.update({
                "duration": sub["duration"],
                "processing_time": sub["processing_time"],
                "cost": sub["cost"],
                "waiting_time_hours": sub["waiting_time_hours"],
                "rework_time_hours": sub["rework_time_hours"],
                "rework_cost": sub["rework_cost"],
                "resource": None,
                "is_subprocess": True,
                "name": child_process.get("process_name")
            })
        else:
            task_record = pt.get("task") or {}
            metrics = _compute_task_metrics(task_record)
            task.update({
                "duration": metrics["duration"],
                "processing_time": metrics["processing_time"],
                "cost": metrics["cost"],
                "waiting_time_hours": metrics["waiting_time_hours"],
                "rework_time_hours": metrics["rework_time_hours"],
                "rework_cost": metrics["rework_cost"],
                "resource": metrics["resource"],
                "raci": metrics["raci"],
                "name": task_record.get("task_name")
            })

        parsed.tasks.append(task)

    # --- Gateway nodes ---
    for gw in gateways:
        parsed.gateways.append({
            "id": gateway_node_id(gw),
            "name": gw.get("name"),
            "type": (gw.get("gateway_type") or "exclusive").lower()
        })

    # --- Flows: start, plain trunk continuations, and gateway branches ---
    add_flow(START_ID, node_after_trunk_position(-1), 1.0)

    for pt in process_tasks:
        node_id = _task_node_id(pt)
        task_id = pt.get("task_id")

        pinned_gateway = gateway_by_after_task_id.get(task_id) if task_id is not None else None
        if pinned_gateway is not None:
            # Flow enters the gateway (probability 1.0); the gateway's own branches
            # (added below) take over from there.
            add_flow(node_id, gateway_node_id(pinned_gateway), 1.0)
            continue

        if task_id is not None and task_id in jump_target_task_ids:
            add_flow(node_id, MAIN_END_ID, 1.0)
            continue

        add_flow(node_id, node_after_trunk_position(trunk_index_by_node_id[node_id]), 1.0)

    node_id_by_task_id = {
        pt["task_id"]: _task_node_id(pt) for pt in process_tasks if pt.get("task_id") is not None
    }

    for gw in gateways:
        gw_node_id = gateway_node_id(gw)

        for branch in gw.get("branches", []):
            probability = branch.get("probability")
            if probability is None:
                continue

            target_task_id = branch.get("target_task_id")
            target_gateway_id = branch.get("target_gateway_id")
            end_event_name = branch.get("end_event_name")

            if target_task_id is not None:
                target_node = node_id_by_task_id.get(target_task_id)
                if target_node is None:
                    continue
            elif target_gateway_id is not None:
                target_gw = gateway_by_pk.get(target_gateway_id)
                if target_gw is None:
                    continue
                target_node = gateway_node_id(target_gw)
            elif end_event_name:
                target_node = end_node_for_name(end_event_name)
            else:
                target_node = MAIN_END_ID

            add_flow(gw_node_id, target_node, probability)

    return parsed


def _parse_target_process(data, processes_dir, currently_resolving):
    parsed = None
    xml = data.get("bpmn_xml")

    if xml:
        try:
            parsed = parse_bpmn_string(xml)
            if not parsed.tasks:
                # Parses fine but describes nothing usable -- treat like a missing XML.
                parsed = None
            else:
                _enrich_from_relations(parsed, data, processes_dir, currently_resolving)
        except Exception:
            # bpmn_xml is still under active development server-side and is sometimes
            # malformed or inconsistent with the relational data -- never let a bad XML
            # payload take down the whole parse, fall back to the relational data below.
            parsed = None

    if parsed is None:
        parsed = _build_graph_from_relations(data, processes_dir, currently_resolving)

    return parsed


def parse_target_process(data, processes_dir):
    """Parse a process dict in the SaaS's relational JSON schema into a ParsedProcess.

    `bpmn_xml`, when present and well-formed, is used as the graph topology source
    (it's the most precise representation when available), enriched with the
    relational fields (`process_task`, `gateways[].branches[].probability`,
    `jobTasks`, `value_classification`, `child_process_id`) for duration/cost/
    resource/value-add data. But `bpmn_xml` is generated by a system that's still
    under construction -- it can be missing, null, or malformed -- so whenever it
    isn't usable, the graph is instead built entirely from `process_task[]` and
    `gateways[]` (see `_build_graph_from_relations`). Either way the result is a
    normal ParsedProcess; callers never need to know which path was used.

    `processes_dir` resolves any `child_process_id` subprocess reference -- pass either
    a directory path (reads `<id>.json` from disk) or a dict already keyed by
    process_id (an in-memory bundle, e.g. subprocesses fetched from a live API).
    """
    return _parse_target_process(data, processes_dir, frozenset())


def parse_target_process_file(filepath, processes_dir=None):
    filepath = Path(filepath)
    if processes_dir is None:
        processes_dir = filepath.parent

    with open(filepath, "r", encoding="utf-8") as f:
        data = json.load(f)

    return parse_target_process(data, processes_dir)


if __name__ == "__main__":
    import sys

    path = sys.argv[1] if len(sys.argv) > 1 else "data/target_samples/1972.json"
    parsed = parse_target_process_file(path)

    print("Tasks:")
    for t in parsed.tasks:
        print(" ", t["id"], t["name"], "dur=", round(t["duration"], 2), "cost=", t["cost"],
              "resource=", t["resource"], "value=", t["value_classification"], "subprocess=", t["is_subprocess"])

    print("Metrics:", calculate_metrics(parsed))
