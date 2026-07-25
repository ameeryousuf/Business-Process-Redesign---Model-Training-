def detect_knockout(parsed, skew_threshold=0.2):
    task_ids = {t["id"] for t in parsed.tasks if not t.get("is_subprocess")}

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

        probs = [(f["target"], f["probability"]) for f in task_targets]
        max_prob = max(p for _, p in probs)
        min_prob = min(p for _, p in probs)

        if (max_prob - min_prob) >= skew_threshold:
            least_likely = min(probs, key=lambda x: x[1])
            candidates.append({
                "gateway_id": gw_id,
                "check_first": least_likely[0],
                "probability": least_likely[1]
            })

    return {
        "eligible": len(candidates) > 0,
        "candidates": candidates
    }


if __name__ == "__main__":
    from app.bpmn_parser import parse_bpmn

    parsed = parse_bpmn("data/sample_process.bpmn")
    result = detect_knockout(parsed)
    print("Knock-Out eligibility:", result)