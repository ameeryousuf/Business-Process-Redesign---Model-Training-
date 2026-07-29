import copy


def apply_knockout(parsed, gateway_id, check_first_task_id):
    new_parsed = copy.deepcopy(parsed)

    graph = {}
    for flow in new_parsed.flows:
        graph.setdefault(flow["source"], []).append(flow)

    outgoing = graph.get(gateway_id, [])

    for flow in outgoing:
        if flow["target"] == check_first_task_id:
            flow["priority_first"] = True

    task_lookup = {t["id"]: t for t in new_parsed.tasks}
    checked_task = task_lookup[check_first_task_id]
    checked_task["cost"] = round(checked_task["cost"] * 0.9, 2)

    return new_parsed


if __name__ == "__main__":
    from app.bpmn_parser import parse_bpmn
    from app.utils.metrics_calculator import calculate_metrics

    parsed = parse_bpmn("data/sample_process.bpmn")
    print("AS-IS Metrics:", calculate_metrics(parsed))

    new_parsed = apply_knockout(parsed, "Gateway_1", "Task_D")
    print("TO-BE Metrics (after Knock-Out, check Task_D first):", calculate_metrics(new_parsed))