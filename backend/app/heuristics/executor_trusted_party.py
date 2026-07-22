import copy


def apply_trusted_party(parsed, task_id, cost_reduction_ratio=0.7):
    new_parsed = copy.deepcopy(parsed)

    task_lookup = {t["id"]: t for t in new_parsed.tasks}
    task = task_lookup[task_id]

    task["cost"] = round(task["cost"] * cost_reduction_ratio, 2)
    task["resource"] = "Trusted Partner"

    return new_parsed


if __name__ == "__main__":
    from app.bpmn_parser import parse_bpmn
    from app.metrics_calculator import calculate_metrics

    parsed = parse_bpmn("data/sample_process.bpmn")
    print("AS-IS Metrics:", calculate_metrics(parsed))

    new_parsed = apply_trusted_party(parsed, "Task_A")
    print("TO-BE Metrics (after outsourcing Task_A):", calculate_metrics(new_parsed))