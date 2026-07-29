import copy


def apply_composition(parsed, task_a_id, task_b_id):
    new_parsed = copy.deepcopy(parsed)

    task_lookup = {t["id"]: t for t in new_parsed.tasks}
    task_a = task_lookup[task_a_id]
    task_b = task_lookup[task_b_id]

    flows = new_parsed.flows

    incoming_flows = [f for f in flows if f["target"] == task_a_id]
    middle_flows = [f for f in flows if f["source"] == task_a_id and f["target"] == task_b_id]
    outgoing_flows = [f for f in flows if f["source"] == task_b_id]

    if len(incoming_flows) != 1 or len(middle_flows) != 1 or len(outgoing_flows) != 1:
        return None

    incoming_flow = incoming_flows[0]
    middle_flow = middle_flows[0]
    outgoing_flow = outgoing_flows[0]

    merged_task = {
        "id": f"{task_a_id}_{task_b_id}_merged",
        "name": f"{task_a['name']} + {task_b['name']}",
        "duration": round(task_a["duration"] + task_b["duration"] * 0.8, 2),
        "cost": round(task_a["cost"] + task_b["cost"], 2),
        "resource": task_a["resource"]
    }

    new_parsed.tasks = [t for t in new_parsed.tasks if t["id"] not in (task_a_id, task_b_id)]
    new_parsed.tasks.append(merged_task)

    flows.remove(incoming_flow)
    flows.remove(middle_flow)
    flows.remove(outgoing_flow)

    flows.append({"id": f"{incoming_flow['id']}_new", "source": incoming_flow["source"], "target": merged_task["id"], "probability": incoming_flow["probability"]})
    flows.append({"id": f"{outgoing_flow['id']}_new", "source": merged_task["id"], "target": outgoing_flow["target"], "probability": outgoing_flow["probability"]})

    return new_parsed


if __name__ == "__main__":
    from app.bpmn_parser import parse_bpmn
    from app.utils.metrics_calculator import calculate_metrics

    parsed = parse_bpmn("data/sample_process.bpmn")
    print("AS-IS Metrics:", calculate_metrics(parsed))

    new_parsed = apply_composition(parsed, "Task_A", "Task_B")
    print("TO-BE Metrics (after Composing Task_A+Task_B):", calculate_metrics(new_parsed))