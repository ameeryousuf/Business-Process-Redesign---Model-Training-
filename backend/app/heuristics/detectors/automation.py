JUDGMENT_KEYWORDS = ["approve", "review", "decide", "evaluate", "authorize", "assess"]


def detect_automation(parsed):
    candidates = []

    for task in parsed.tasks:
        resource = task["resource"]
        name = (task["name"] or "").lower()

        if resource is None or resource.lower() == "system":
            continue

        requires_judgment = any(keyword in name for keyword in JUDGMENT_KEYWORDS)
        if requires_judgment:
            continue

        candidates.append({
            "task_id": task["id"],
            "name": task["name"],
            "resource": resource
        })

    return {
        "eligible": len(candidates) > 0,
        "candidates": candidates
    }


if __name__ == "__main__":
    from app.bpmn_parser import parse_bpmn

    parsed = parse_bpmn("data/sample_process.bpmn")
    result = detect_automation(parsed)
    print("Automation eligibility:", result)