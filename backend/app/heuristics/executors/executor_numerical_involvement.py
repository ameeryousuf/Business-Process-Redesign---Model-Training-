import copy

COORDINATION_REDUCTION_RATIO = 0.1


def apply_numerical_involvement(parsed, from_resource, to_resource):
    new_parsed = copy.deepcopy(parsed)

    for task in new_parsed.tasks:
        if task["resource"] == from_resource:
            task["resource"] = to_resource
            task["duration"] = round(task["duration"] * (1 - COORDINATION_REDUCTION_RATIO), 2)

    return new_parsed


if __name__ == "__main__":
    from app.bpmn_parser import parse_bpmn
    from app.utils.metrics_calculator import calculate_metrics

    parsed = parse_bpmn("data/sample_process.bpmn")
    print("AS-IS Metrics:", calculate_metrics(parsed))

    new_parsed = apply_numerical_involvement(parsed, "Clerk", "Officer")
    print("TO-BE Metrics (after consolidating Clerk into Officer):", calculate_metrics(new_parsed))