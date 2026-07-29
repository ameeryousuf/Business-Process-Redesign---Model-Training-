from app.heuristics.registry import HEURISTIC_ORDER, DETECTORS


def bucket_value(value, low_cutoff, high_cutoff):
    if value <= low_cutoff:
        return "low"
    elif value <= high_cutoff:
        return "medium"
    else:
        return "high"


def get_eligibility(parsed):
    eligibility = {}
    details = {}
    for name in HEURISTIC_ORDER:
        result = DETECTORS[name](parsed)
        eligibility[name] = 1 if result["eligible"] else 0
        details[name] = result["candidates"]
    return eligibility, details


def build_state(parsed, time_value, cost_value, time_low, time_high, cost_low, cost_high):
    time_bucket = bucket_value(time_value, time_low, time_high)
    cost_bucket = bucket_value(cost_value, cost_low, cost_high)

    eligibility, details = get_eligibility(parsed)

    state_tuple = (time_bucket, cost_bucket) + tuple(eligibility[name] for name in HEURISTIC_ORDER)

    return state_tuple, details


if __name__ == "__main__":
    from app.bpmn_parser import parse_bpmn
    from app.utils.metrics_calculator import calculate_metrics

    parsed = parse_bpmn("data/sample_process.bpmn")
    metrics = calculate_metrics(parsed)

    state, details = build_state(
        parsed,
        metrics["total_time_hours"],
        metrics["total_cost_usd"],
        time_low=5, time_high=10,
        cost_low=50, cost_high=100
    )

    print("State:", state)
    print("Eligible candidates detail:", details)