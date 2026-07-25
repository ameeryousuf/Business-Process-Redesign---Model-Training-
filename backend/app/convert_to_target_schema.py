import copy
import json
import glob
import os
from collections import deque

from app.bpmn_parser import parse_bpmn
from app.bpmn_writer import parsed_to_bpmn_xml

NVA_NAME_KEYWORDS = ["check", "review", "verify", "audit", "validate", "approve", "confirm", "inspect"]

# Synthetic PKR/hour rates, scaled up from the old synthetic unit-rate pipeline's
# ratios (Officer=10, Clerk=8, Manager=15, Analyst=12, System=2) to a realistic PKR
# scale matching the ranges observed in the real SaaS sample data (job.hourlyRate).
RESOURCE_RATE_PKR = {
    "Officer": 3000,
    "Clerk": 2400,
    "Manager": 4500,
    "Analyst": 3600,
    "System": 600,
}
DEFAULT_RATE_PKR = 3000
MAX_REWORK_PROBABILITY = 0.95


def _classify_value(task_name):
    name = (task_name or "").lower()
    if any(keyword in name for keyword in NVA_NAME_KEYWORDS):
        return "NVA"
    return "VA"


def _collapse_pass_through_nodes(parsed):
    """The target schema's gateway branches can only reference a task or a named end
    event -- there is no slot for intermediate events / other pass-through elements.
    Splice every such node out of the flow graph (chaining probabilities through it)
    before conversion, so every remaining flow's source/target is a task, gateway, or
    end event the relational schema can actually express.
    """
    keep_ids = {t["id"] for t in parsed.tasks}
    keep_ids |= {g["id"] for g in parsed.gateways}
    keep_ids |= {e["id"] for e in parsed.end_events}
    keep_ids |= {e["id"] for e in parsed.start_events}

    collapse_ids = {o["id"] for o in parsed.other_elements} - keep_ids

    if not collapse_ids:
        return

    flows = parsed.flows

    changed = True
    while changed:
        changed = False
        incoming_to_collapse = [f for f in flows if f["target"] in collapse_ids]

        for in_flow in incoming_to_collapse:
            collapse_node = in_flow["target"]
            outgoing = [f for f in flows if f["source"] == collapse_node]

            for out_flow in outgoing:
                flows.append({
                    "id": f"{in_flow['id']}_{out_flow['id']}",
                    "source": in_flow["source"],
                    "target": out_flow["target"],
                    "probability": in_flow["probability"] * out_flow["probability"]
                })

            flows.remove(in_flow)
            changed = True

    parsed.flows = [f for f in flows if f["target"] not in collapse_ids and f["source"] not in collapse_ids]
    parsed.other_elements = [o for o in parsed.other_elements if o["id"] not in collapse_ids]


def _detect_and_collapse_back_edges(parsed):
    """Find cycle-forming (back-edge) flows via DFS from the start event, collapse
    each into an `expected_rework_time` contribution on the loop-entry task using
    the textbook's CT = CTb/(1-r) rework-block formula (the *extra* time beyond the
    first pass is CTb * r/(1-r)), then remove the back edge so the resulting graph
    is acyclic -- the target schema has no loop construct, only a flat per-task
    rework-time field.
    """
    if not parsed.start_events:
        return {}

    graph = {}
    for flow in parsed.flows:
        graph.setdefault(flow["source"], []).append(flow)

    task_lookup = {t["id"]: t for t in parsed.tasks}
    extra_rework_minutes = {}
    back_edges = []

    on_stack = set()
    visited = set()
    path = []

    def dfs(node_id):
        if node_id in on_stack:
            return
        if node_id in visited:
            return
        visited.add(node_id)
        on_stack.add(node_id)
        path.append(node_id)

        for flow in graph.get(node_id, []):
            target = flow["target"]
            if target in on_stack:
                back_edges.append((flow, list(path)))
            else:
                dfs(target)

        path.pop()
        on_stack.discard(node_id)

    dfs(parsed.start_events[0]["id"])

    for flow, current_path in back_edges:
        loop_entry = flow["target"]
        loop_exit = flow["source"]
        r = min(flow["probability"], MAX_REWORK_PROBABILITY)

        if loop_entry not in current_path:
            continue

        loop_task_ids = current_path[current_path.index(loop_entry):]
        loop_body_hours = sum(
            task_lookup[tid]["duration"] for tid in loop_task_ids if tid in task_lookup
        )

        if r < 1.0:
            extra_hours = loop_body_hours * (r / (1.0 - r))
        else:
            extra_hours = loop_body_hours * (MAX_REWORK_PROBABILITY / (1.0 - MAX_REWORK_PROBABILITY))

        extra_rework_minutes[loop_entry] = extra_rework_minutes.get(loop_entry, 0.0) + extra_hours * 60.0

    back_edge_flow_ids = {id(flow) for flow, _ in back_edges}
    parsed.flows = [f for f in parsed.flows if id(f) not in back_edge_flow_ids]

    return extra_rework_minutes


def _relabel_task_ids(parsed):
    id_map = {}
    for index, task in enumerate(parsed.tasks, start=1):
        old_id = task["id"]
        new_id = f"Activity_{index}"
        id_map[old_id] = new_id
        task["id"] = new_id

    for flow in parsed.flows:
        if flow["source"] in id_map:
            flow["source"] = id_map[flow["source"]]
        if flow["target"] in id_map:
            flow["target"] = id_map[flow["target"]]

    return id_map


def _ensure_unique_names(items, prefix):
    seen = {}
    for item in items:
        base_name = item.get("name") or f"{prefix}_{item['id']}"
        name = base_name
        count = seen.get(base_name, 0)
        if count > 0:
            name = f"{base_name} ({count + 1})"
        seen[base_name] = count + 1
        item["name"] = name


def convert_bpmn_file_to_target_schema(bpmn_path, process_id):
    parsed = copy.deepcopy(parse_bpmn(bpmn_path))

    _collapse_pass_through_nodes(parsed)
    extra_rework_minutes = _detect_and_collapse_back_edges(parsed)
    id_map = _relabel_task_ids(parsed)
    extra_rework_minutes = {id_map.get(k, k): v for k, v in extra_rework_minutes.items()}

    _ensure_unique_names(parsed.gateways, "Gateway")
    _ensure_unique_names(parsed.end_events, "End")

    xml = parsed_to_bpmn_xml(parsed, process_id=f"Process_{process_id}")

    process_task = []
    for index, task in enumerate(parsed.tasks, start=1):
        task_id = index
        resource = task["resource"] or "Officer"
        rate = RESOURCE_RATE_PKR.get(resource, DEFAULT_RATE_PKR)
        process_time_minutes = round(task["duration"] * 60.0, 2)
        rework_minutes = round(extra_rework_minutes.get(task["id"], 0.0), 2)

        process_task.append({
            "process_task_id": task_id,
            "process_id": process_id,
            "task_id": task_id,
            "order": index,
            "child_process_id": None,
            "value_classification": _classify_value(task["name"]),
            "value_rationale": "inferred: task-name heuristic (converted from legacy BPMN dataset)",
            "bva_business_goal": None,
            "value_source": "inferred",
            "task": {
                "task_id": task_id,
                "task_code": f"T-{task_id}",
                "task_name": task["name"] or task["id"],
                "task_overview": None,
                "expected_process_time": process_time_minutes,
                "expected_rework_time": rework_minutes,
                "expected_waiting_time": 0,
                "frequency_interval": 1,
                "frequency_period": "WEEK",
                "occurrences": "1",
                "jobTasks": [
                    {
                        "job_id": task_id,
                        "task_id": task_id,
                        "role": "R",
                        "time_allocation_percentage": "100",
                        "job": {
                            "job_id": task_id,
                            "name": resource,
                            "hourlyRate": rate,
                            "maxHoursPerDay": 8,
                            "days_per_week": "5",
                            "hours_per_day": "8",
                            "capacity_buffer": "10",
                            "currencyType": "PKR"
                        }
                    }
                ]
            },
            "child_process": None
        })

    task_id_by_activity_id = {task["id"]: index for index, task in enumerate(parsed.tasks, start=1)}
    end_event_by_id = {e["id"]: e for e in parsed.end_events}
    gateway_pk_by_xml_id = {gateway["id"]: index for index, gateway in enumerate(parsed.gateways, start=1)}

    gateway_type_map = {"exclusive": "EXCLUSIVE", "parallel": "PARALLEL", "inclusive": "INCLUSIVE"}

    flows_by_source = {}
    for flow in parsed.flows:
        flows_by_source.setdefault(flow["source"], []).append(flow)

    gateways_out = []
    for gw_index, gateway in enumerate(parsed.gateways, start=1):
        outgoing = flows_by_source.get(gateway["id"], [])
        if len(outgoing) < 2:
            continue

        branches = []
        for branch_index, flow in enumerate(outgoing, start=1):
            target_task_id = task_id_by_activity_id.get(flow["target"])
            end_event = end_event_by_id.get(flow["target"])
            target_gateway_id = gateway_pk_by_xml_id.get(flow["target"])

            branches.append({
                "id": gw_index * 100 + branch_index,
                "gateway_pk_id": gw_index,
                "is_default": False,
                "target_task_id": target_task_id,
                "condition": f"branch_{branch_index}",
                "end_event_name": end_event["name"] if end_event else None,
                "end_task_id": None,
                "connect_to_end": True,
                "target_gateway_id": target_gateway_id,
                "probability": flow["probability"]
            })

        gateways_out.append({
            "gateway_pk_id": gw_index,
            "process_id": process_id,
            "gateway_type": gateway_type_map.get(gateway["type"], "EXCLUSIVE"),
            "after_task_id": None,
            "name": gateway["name"],
            "converge_at_task_id": None,
            "converge_gateway_name": "",
            "converge_to_end": True,
            "converge_at_gateway_id": None,
            "after_gateway_id": None,
            "branches": branches
        })

    return {
        "process_id": process_id,
        "company_id": 1,
        "process_code": f"CONV-P-{process_id}",
        "process_name": os.path.splitext(os.path.basename(bpmn_path))[0],
        "process_overview": "Converted from legacy BPMN training corpus.",
        "process_category_id": 1,
        "process_status_id": 1,
        "process_version": 0,
        "bpmn_xml": xml,
        "gateways": gateways_out,
        "process_task": process_task
    }


def convert_directory(src_dir, dst_dir, id_offset=0):
    os.makedirs(dst_dir, exist_ok=True)
    files = sorted(glob.glob(os.path.join(src_dir, "*.bpmn")))

    converted = 0
    failed = []

    for index, bpmn_path in enumerate(files):
        process_id = id_offset + index + 1
        try:
            record = convert_bpmn_file_to_target_schema(bpmn_path, process_id)
        except Exception as e:
            failed.append((bpmn_path, str(e)))
            continue

        out_path = os.path.join(dst_dir, f"{process_id}.json")
        with open(out_path, "w", encoding="utf-8") as f:
            json.dump(record, f)

        converted += 1

    return converted, failed


if __name__ == "__main__":
    train_converted, train_failed = convert_directory(
        "data/training_final", "data/target_training", id_offset=0
    )
    print(f"training_final -> target_training: {train_converted} converted, {len(train_failed)} failed")
    for path, err in train_failed[:10]:
        print("  FAILED:", path, err)

    eval_converted, eval_failed = convert_directory(
        "data/eval_final", "data/target_eval", id_offset=100000
    )
    print(f"eval_final -> target_eval: {eval_converted} converted, {len(eval_failed)} failed")
    for path, err in eval_failed[:10]:
        print("  FAILED:", path, err)
