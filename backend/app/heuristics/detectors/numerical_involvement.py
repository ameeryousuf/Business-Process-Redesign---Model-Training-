def detect_numerical_involvement(parsed):
    human_resources = set()

    for task in parsed.tasks:
        resource = task["resource"]
        if resource and resource.lower() != "system":
            human_resources.add(resource)

    return {
        "eligible": len(human_resources) > 1,
        "candidates": sorted(human_resources)
    }


if __name__ == "__main__":
    from app.bpmn_parser import parse_bpmn

    parsed = parse_bpmn("data/sample_process.bpmn")
    result = detect_numerical_involvement(parsed)
    print("Numerical Involvement eligibility:", result)