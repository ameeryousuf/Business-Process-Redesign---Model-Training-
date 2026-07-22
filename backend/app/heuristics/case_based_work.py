def detect_case_based_work(parsed, ratio_threshold=1.5):
    task_ids = {t["id"] for t in parsed.tasks}
    task_lookup = {t["id"]: t for t in parsed.tasks}

    graph = {}
    for flow in parsed.flows:
        graph.setdefault(flow["source"], []).append(flow)

    candidates = []

    for gateway in parsed.gateways:
        gw_id = gateway["id"]
        outgoing = graph.get(gw_id, [])
        task_targets = [f for f in outgoing if f["target"] in task_ids]

        if len(task_targets) < 2:
            continue

        costs = [task_lookup[f["target"]]["cost"] for f in task_targets]
        if min(costs) == 0:
            continue

        ratio = max(costs) / min(costs)
        if ratio >= ratio_threshold:
            candidates.append({
                "gateway_id": gw_id,
                "branch_costs": costs
            })

    return {
        "eligible": len(candidates) > 0,
        "candidates": candidates
    }


if __name__ == "__main__":
    from app.bpmn_parser import parse_bpmn

    parsed = parse_bpmn("data/sample_process.bpmn")
    result = detect_case_based_work(parsed)
    print("Case-Based Work eligibility:", result)