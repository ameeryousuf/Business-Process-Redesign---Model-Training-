import copy


def apply_case_based_work(parsed, gateway_id, cost_reduction_ratio=0.85):
    new_parsed = copy.deepcopy(parsed)

    task_lookup = {t["id"]: t for t in new_parsed.tasks}

    graph = {}
    for flow in new_parsed.flows:
        graph.setdefault(flow["source"], []).append(flow)

    outgoing = graph.get(gateway_id, [])
    task_ids = {t["id"] for t in new_parsed.tasks}
    branch_targets = [f["target"] for f in outgoing if f["target"] in task_ids]

    for target_id in branch_targets:
        task = task_lookup[target_id]
        task["cost"] = round(task["cost"] * cost_reduction_ratio, 2)

    return new_parsed


if __name__ == "__main__":
    from app.bpmn_parser import parse_bpmn
    from app.metrics_calculator import calculate_metrics

    parsed = parse_bpmn("data/sample_process.bpmn")
    print("AS-IS Metrics:", calculate_metrics(parsed))

    new_parsed = apply_case_based_work(parsed, "Gateway_1")
    print("TO-BE Metrics (after Case-Based routing at Gateway_1):", calculate_metrics(new_parsed))