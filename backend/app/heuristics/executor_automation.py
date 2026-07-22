import copy


def apply_automation(parsed, task_id, new_duration_ratio=0.3, new_cost_ratio=0.5):
    new_parsed = copy.deepcopy(parsed)

    task_lookup = {t["id"]: t for t in new_parsed.tasks}
    task = task_lookup[task_id]

    task["duration"] = round(task["duration"] * new_duration_ratio, 2)
    task["cost"] = round(task["cost"] * new_cost_ratio, 2)
    task["resource"] = "System"

    return new_parsed


if __name__ == "__main__":
    from app.bpmn_parser import parse_bpmn
    from app.metrics_calculator import calculate_metrics

    parsed = parse_bpmn("data/sample_process.bpmn")
    print("AS-IS Metrics:", calculate_metrics(parsed))

    new_parsed = apply_automation(parsed, "Task_B")
    print("TO-BE Metrics (after Automating Task_B):", calculate_metrics(new_parsed))