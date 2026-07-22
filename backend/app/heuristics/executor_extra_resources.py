import copy


def apply_extra_resources(parsed, task_id, duration_reduction_ratio=0.5, cost_increase_ratio=1.3):
    new_parsed = copy.deepcopy(parsed)

    task_lookup = {t["id"]: t for t in new_parsed.tasks}
    task = task_lookup[task_id]

    task["duration"] = round(task["duration"] * duration_reduction_ratio, 2)
    task["cost"] = round(task["cost"] * cost_increase_ratio, 2)

    return new_parsed


if __name__ == "__main__":
    from app.bpmn_parser import parse_bpmn
    from app.metrics_calculator import calculate_metrics

    parsed = parse_bpmn("data/sample_process.bpmn")
    print("AS-IS Metrics:", calculate_metrics(parsed))

    new_parsed = apply_extra_resources(parsed, "Task_A")
    print("TO-BE Metrics (after adding resources to Task_A):", calculate_metrics(new_parsed))