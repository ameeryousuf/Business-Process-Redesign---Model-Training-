import copy


def apply_parallelism(parsed, task_a_id, task_b_id):
    new_parsed = copy.deepcopy(parsed)

    task_lookup = {t["id"]: t for t in new_parsed.tasks}
    task_a = task_lookup[task_a_id]
    task_b = task_lookup[task_b_id]

    flows = new_parsed.flows

    incoming_flow = next((f for f in flows if f["target"] == task_a_id), None)
    middle_flow = next((f for f in flows if f["source"] == task_a_id and f["target"] == task_b_id), None)
    outgoing_flow = next((f for f in flows if f["source"] == task_b_id), None)

    if incoming_flow is None or middle_flow is None or outgoing_flow is None:
        return None

    split_id = f"Gateway_ANDsplit_{task_a_id}_{task_b_id}"
    join_id = f"Gateway_ANDjoin_{task_a_id}_{task_b_id}"

    new_parsed.gateways.append({"id": split_id, "name": "Parallel Split", "type": "parallel"})
    new_parsed.gateways.append({"id": join_id, "name": "Parallel Join", "type": "parallel"})

    flows.remove(incoming_flow)
    flows.remove(middle_flow)
    flows.remove(outgoing_flow)

    flows.append({"id": f"{incoming_flow['id']}_new", "source": incoming_flow["source"], "target": split_id, "probability": 1.0})
    flows.append({"id": f"flow_split_to_{task_a_id}", "source": split_id, "target": task_a_id, "probability": 1.0})
    flows.append({"id": f"flow_split_to_{task_b_id}", "source": split_id, "target": task_b_id, "probability": 1.0})
    flows.append({"id": f"flow_{task_a_id}_to_join", "source": task_a_id, "target": join_id, "probability": 1.0})
    flows.append({"id": f"flow_{task_b_id}_to_join", "source": task_b_id, "target": join_id, "probability": 1.0})
    flows.append({"id": f"{outgoing_flow['id']}_new", "source": join_id, "target": outgoing_flow["target"], "probability": 1.0})

    task_a["parallel_group"] = join_id
    task_b["parallel_group"] = join_id

    return new_parsed


if __name__ == "__main__":
    from app.bpmn_parser import parse_bpmn
    from app.metrics_calculator import calculate_metrics

    parsed = parse_bpmn("data/sample_process.bpmn")
    print("AS-IS Metrics:", calculate_metrics(parsed))

    new_parsed = apply_parallelism(parsed, "Task_A", "Task_B")
    print("TO-BE Metrics (after Parallelism):", calculate_metrics(new_parsed))