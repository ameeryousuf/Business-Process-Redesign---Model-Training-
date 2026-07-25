def detect_extra_resources(parsed, ratio_threshold=1.5):
    tasks = [t for t in parsed.tasks if not t.get("is_subprocess")]

    if not tasks:
        return {"eligible": False, "candidates": []}

    avg_duration = sum(t["duration"] for t in tasks) / len(tasks)
    cutoff = avg_duration * ratio_threshold

    candidates = []
    for task in tasks:
        if task["duration"] >= cutoff:
            candidates.append({
                "task_id": task["id"],
                "name": task["name"],
                "duration": task["duration"]
            })

    return {
        "eligible": len(candidates) > 0,
        "candidates": candidates
    }


if __name__ == "__main__":
    from app.bpmn_parser import parse_bpmn

    parsed = parse_bpmn("data/sample_process.bpmn")
    result = detect_extra_resources(parsed)
    print("Extra Resources eligibility:", result)