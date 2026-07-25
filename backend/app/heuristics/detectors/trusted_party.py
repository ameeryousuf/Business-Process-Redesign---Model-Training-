def detect_trusted_party(parsed, ratio_threshold=1.5):
    tasks = [t for t in parsed.tasks if t["duration"] > 0 and not t.get("is_subprocess")]

    if not tasks:
        return {"eligible": False, "candidates": []}

    ratios = [t["cost"] / t["duration"] for t in tasks]
    avg_ratio = sum(ratios) / len(ratios)
    cutoff = avg_ratio * ratio_threshold

    candidates = []
    for task in tasks:
        ratio = task["cost"] / task["duration"]
        if ratio >= cutoff:
            candidates.append({
                "task_id": task["id"],
                "name": task["name"],
                "cost_per_hour": round(ratio, 2)
            })

    return {
        "eligible": len(candidates) > 0,
        "candidates": candidates
    }


if __name__ == "__main__":
    from app.bpmn_parser import parse_bpmn

    parsed = parse_bpmn("data/sample_process.bpmn")
    result = detect_trusted_party(parsed)
    print("Trusted Party eligibility:", result)