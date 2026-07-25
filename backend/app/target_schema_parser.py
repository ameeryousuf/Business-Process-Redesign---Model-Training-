import json
import re
from pathlib import Path

from app.bpmn_parser import parse_bpmn_string
from app.metrics_calculator import calculate_metrics, calculate_theoretical_metrics
from app import currency

ACTIVITY_ID_PATTERN = re.compile(r"^Activity_(\d+)$")
SUBPROCESS_ID_PATTERN = re.compile(r"^SubProcess_(\d+)$")


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
    # Theoretical/processing time excludes only waiting time -- rework is real work
    # re-executed, not idle time, so it still counts (Dumas et al. Ch.7.1.2).
    processing_time = process_time_h + rework_time_h

    cost = 0.0
    resource = None
    raci = []

    for job_task in task_record.get("jobTasks") or []:
        job = job_task.get("job") or {}
        allocation_pct = float(job_task.get("time_allocation_percentage") or 0)
        allocation = allocation_pct / 100.0
        rate_pkr = currency.convert_to_pkr(job.get("hourlyRate") or 0, job.get("currencyType"))
        cost += process_time_h * allocation * rate_pkr

        role = job_task.get("role")
        if role == "R":
            resource = job.get("name")

        raci.append({
            "role": role,
            "name": job.get("name"),
            "time_allocation_percentage": allocation_pct
        })

    return duration, processing_time, round(cost, 2), resource, raci


def _resolve_subprocess(child_process_id, processes_dir, currently_resolving):
    if child_process_id in currently_resolving:
        raise CircularSubprocessError(
            f"Circular subprocess reference detected while resolving process {child_process_id}."
        )

    subprocess_path = Path(processes_dir) / f"{child_process_id}.json"
    if not subprocess_path.exists():
        raise SubprocessNotFoundError(
            f"The process you are redesigning has subprocess {child_process_id}, "
            f"whose data is not available."
        )

    with open(subprocess_path, "r", encoding="utf-8") as f:
        sub_data = json.load(f)

    sub_parsed = _parse_target_process(
        sub_data, processes_dir, currently_resolving | {child_process_id}
    )
    sub_metrics = calculate_metrics(sub_parsed)
    sub_theoretical = calculate_theoretical_metrics(sub_parsed)
    return sub_metrics["total_time_hours"], sub_metrics["total_cost_usd"], sub_theoretical["theoretical_time_hours"]


def _parse_target_process(data, processes_dir, currently_resolving):
    parsed = parse_bpmn_string(data["bpmn_xml"])

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

        child_process_id = _subprocess_child_process_id(task["id"])
        if child_process_id is not None:
            pt = process_task_by_child_process_id.get(child_process_id)
            duration, cost, processing_time = _resolve_subprocess(
                child_process_id, processes_dir, currently_resolving
            )
            task["duration"] = duration
            task["processing_time"] = processing_time
            task["cost"] = cost
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
        duration, processing_time, cost, resource, raci = _compute_task_metrics(task_record)
        task["duration"] = duration
        task["processing_time"] = processing_time
        task["cost"] = cost
        task["resource"] = resource
        task["raci"] = raci
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

            for flow in outgoing:
                if id(flow) in matched_flows:
                    continue
                if flow["target"] == target_xml_id:
                    flow["probability"] = probability
                    matched_flows.add(id(flow))
                    break

        remaining_flows = [f for f in outgoing if id(f) not in matched_flows]
        if len(unresolved_branches) == 1 and len(remaining_flows) == 1:
            remaining_flows[0]["probability"] = unresolved_branches[0]

    return parsed


def parse_target_process(data, processes_dir):
    """Parse a process dict in the SaaS's relational JSON schema into a ParsedProcess.

    Graph topology (tasks/gateways/flows) comes from the embedded `bpmn_xml`, which is
    the unambiguous source of truth for structure. The relational fields (`process_task`,
    `gateways[].branches[].probability`, `jobTasks`, `value_classification`,
    `child_process_id`) are used to enrich each node with real duration/cost/resource/
    value-add data. `after_task_id` / `converge_at_*` are informational in the source
    schema and intentionally unused here since the XML already encodes that structure.
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
