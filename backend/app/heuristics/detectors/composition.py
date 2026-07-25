def detect_composition(parsed):
    task_ids = {t["id"] for t in parsed.tasks}
    task_lookup = {t["id"]: t for t in parsed.tasks}

    outgoing_graph = {}
    incoming_count = {}

    for flow in parsed.flows:
        outgoing_graph.setdefault(flow["source"], []).append(flow)
        incoming_count[flow["target"]] = incoming_count.get(flow["target"], 0) + 1

    candidates = []

    for flow in parsed.flows:
        source_id = flow["source"]
        target_id = flow["target"]

        if source_id not in task_ids or target_id not in task_ids:
            continue

        outgoing_from_source = outgoing_graph.get(source_id, [])
        if len(outgoing_from_source) != 1:
            continue

        if incoming_count.get(target_id, 0) != 1:
            continue

        source_task = task_lookup[source_id]
        target_task = task_lookup[target_id]

        if source_task.get("parallel_group") or target_task.get("parallel_group"):
            continue

        if source_task.get("is_subprocess") or target_task.get("is_subprocess"):
            continue

        if source_task["resource"] == target_task["resource"]:
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
    result = detect_composition(parsed)
    print("Composition eligibility:", result)