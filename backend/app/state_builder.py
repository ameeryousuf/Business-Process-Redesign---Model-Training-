from app.heuristics.parallelism import detect_parallelism
from app.heuristics.elimination import detect_elimination
from app.heuristics.automation import detect_automation
from app.heuristics.composition import detect_composition
from app.heuristics.case_based_work import detect_case_based_work
from app.heuristics.resequencing import detect_resequencing
from app.heuristics.numerical_involvement import detect_numerical_involvement
from app.heuristics.knockout import detect_knockout
from app.heuristics.trusted_party import detect_trusted_party
from app.heuristics.extra_resources import detect_extra_resources

HEURISTIC_ORDER = [
    "parallelism",
    "elimination",
    "automation",
    "composition",
    "case_based_work",
    "resequencing",
    "numerical_involvement",
    "knockout",
    "trusted_party",
    "extra_resources",
]

DETECTORS = {
    "parallelism": detect_parallelism,
    "elimination": detect_elimination,
    "automation": detect_automation,
    "composition": detect_composition,
    "case_based_work": detect_case_based_work,
    "resequencing": detect_resequencing,
    "numerical_involvement": detect_numerical_involvement,
    "knockout": detect_knockout,
    "trusted_party": detect_trusted_party,
    "extra_resources": detect_extra_resources,
}


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
    from app.metrics_calculator import calculate_metrics

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