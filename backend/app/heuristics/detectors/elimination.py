def detect_elimination(parsed, threshold_ratio=0.2):
    tasks = [t for t in parsed.tasks if not t.get("is_subprocess")]

    if len(tasks) <= 1:
        return {"eligible": False, "candidates": []}

    classified_tasks = [t for t in tasks if t.get("value_classification")]
    if classified_tasks:
        candidates = [
            {
                "task_id": task["id"],
                "name": task["name"],
                "duration": task["duration"],
                "cost": task["cost"],
                "value_classification": task["value_classification"]
            }
            for task in classified_tasks
            if task["value_classification"] == "NVA"
        ]
        return {
            "eligible": len(candidates) > 0,
            "candidates": candidates
        }

    avg_duration = sum(t["duration"] for t in tasks) / len(tasks)
    avg_cost = sum(t["cost"] for t in tasks) / len(tasks)

    duration_cutoff = avg_duration * threshold_ratio
    cost_cutoff = avg_cost * threshold_ratio

    candidates = []
    for task in tasks:
        if task["duration"] <= duration_cutoff and task["cost"] <= cost_cutoff:
            candidates.append({
                "task_id": task["id"],
                "name": task["name"],
                "duration": task["duration"],
                "cost": task["cost"]
            })

    return {
        "eligible": len(candidates) > 0,
        "candidates": candidates
    }


if __name__ == "__main__":
    from app.bpmn_parser import parse_bpmn

    parsed = parse_bpmn("data/sample_process.bpmn")
    result = detect_elimination(parsed)
    print("Elimination eligibility:", result)