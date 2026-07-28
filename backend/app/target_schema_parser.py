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
    processing_time = process_time_h
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
                unresolved_branches.append(probability)

        remaining_flows = [f for f in outgoing if id(f) not in matched_flows]
        if len(unresolved_branches) == 1 and len(remaining_flows) == 1:
            remaining_flows[0]["probability"] = unresolved_branches[0]


def _process_task_sort_key(pt):
    order = pt.get("order")
    return (order if order is not None else 10 ** 9, pt.get("task_id") or 0)


def _task_node_id(pt):
    if pt.get("child_process_id") is not None:
        return f"SubProcess_{pt['child_process_id']}"
    return f"Activity_{pt['task_id']}"


def _slugify(name):
    slug = re.sub(r"[^A-Za-z0-9]+", "_", name or "").strip("_")
    return slug or "End"


def _build_graph_from_relations(data, source, currently_resolving):
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

    trunk_tasks = [pt for pt in process_tasks if pt.get("task_id") not in jump_target_task_ids]
    trunk_node_ids = [_task_node_id(pt) for pt in trunk_tasks]
    trunk_index_by_node_id = {node_id: i for i, node_id in enumerate(trunk_node_ids)}

    def node_after_trunk_position(idx):
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

    for gw in gateways:
        parsed.gateways.append({
            "id": gateway_node_id(gw),
            "name": gw.get("name"),
            "type": (gw.get("gateway_type") or "exclusive").lower()
        })

    add_flow(START_ID, node_after_trunk_position(-1), 1.0)

    for pt in process_tasks:
        node_id = _task_node_id(pt)
        task_id = pt.get("task_id")

        pinned_gateway = gateway_by_after_task_id.get(task_id) if task_id is not None else None
        if pinned_gateway is not None:
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
                parsed = None
            else:
                _enrich_from_relations(parsed, data, processes_dir, currently_resolving)
        except Exception:
            parsed = None

    if parsed is None:
        parsed = _build_graph_from_relations(data, processes_dir, currently_resolving)

    return parsed


def parse_target_process(data, processes_dir):
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
