def detect_parallelism(parsed):
    gateway_ids = {g["id"] for g in parsed.gateways}
    task_ids = {t["id"] for t in parsed.tasks}
    task_lookup = {t["id"]: t for t in parsed.tasks}

    graph = {}
    for flow in parsed.flows:
        graph.setdefault(flow["source"], []).append(flow)

    candidates = []

    for flow in parsed.flows:
        source_id = flow["source"]
        target_id = flow["target"]

        if source_id not in task_ids or target_id not in task_ids:
            continue

        outgoing_from_source = graph.get(source_id, [])
        if len(outgoing_from_source) != 1:
            continue

        source_task = task_lookup[source_id]
        target_task = task_lookup[target_id]

        if source_task["resource"] != target_task["resource"]:
            candidates.append({
                "task_a": source_id,
                "task_b": target_id,
                "flow_id": flow["id"]
            })

    return {
        "eligible": len(candidates) > 0,
        "candidates": candidates
    }


if __name__ == "__main__":
    from app.bpmn_parser import parse_bpmn

    parsed = parse_bpmn("data/sample_process.bpmn")
    result = detect_parallelism(parsed)
    print("Parallelism eligibility:", result)