from app.heuristics.detectors.parallelism import detect_parallelism
from app.heuristics.detectors.elimination import detect_elimination
from app.heuristics.detectors.automation import detect_automation
from app.heuristics.detectors.composition import detect_composition
from app.heuristics.detectors.case_based_work import detect_case_based_work
from app.heuristics.detectors.resequencing import detect_resequencing
from app.heuristics.detectors.numerical_involvement import detect_numerical_involvement
from app.heuristics.detectors.knockout import detect_knockout
from app.heuristics.detectors.trusted_party import detect_trusted_party
from app.heuristics.detectors.extra_resources import detect_extra_resources

from app.heuristics.executors.executor_parallelism import apply_parallelism
from app.heuristics.executors.executor_elimination import apply_elimination
from app.heuristics.executors.executor_automation import apply_automation
from app.heuristics.executors.executor_composition import apply_composition
from app.heuristics.executors.executor_case_based_work import apply_case_based_work
from app.heuristics.executors.executor_resequencing import apply_resequencing
from app.heuristics.executors.executor_numerical_involvement import apply_numerical_involvement
from app.heuristics.executors.executor_knockout import apply_knockout
from app.heuristics.executors.executor_trusted_party import apply_trusted_party
from app.heuristics.executors.executor_extra_resources import apply_extra_resources

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

HEURISTIC_LABELS = {
    "parallelism": "Parallelism",
    "elimination": "Elimination",
    "automation": "Automation",
    "composition": "Composition",
    "case_based_work": "Case-Based Work",
    "resequencing": "Resequencing",
    "numerical_involvement": "Numerical Involvement",
    "knockout": "Knock-Out",
    "trusted_party": "Trusted Party / Outsourcing",
    "extra_resources": "Extra Resources",
}

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

# Executors below assume they receive a SINGLE candidate dict, except
# "numerical_involvement" which receives the full candidates list (a list of role names).
EXECUTORS = {
    "parallelism": lambda parsed, c: apply_parallelism(parsed, c["task_a"], c["task_b"]),
    "elimination": lambda parsed, c: apply_elimination(parsed, c["task_id"]),
    "automation": lambda parsed, c: apply_automation(parsed, c["task_id"]),
    "composition": lambda parsed, c: apply_composition(parsed, c["task_a"], c["task_b"]),
    "case_based_work": lambda parsed, c: apply_case_based_work(parsed, c["gateway_id"]),
    "resequencing": lambda parsed, c: apply_resequencing(parsed, c["expensive_task"], c["cheaper_task"]),
    "numerical_involvement": lambda parsed, roles: apply_numerical_involvement(parsed, roles[0], roles[1]) if len(roles) >= 2 else None,
    "knockout": lambda parsed, c: apply_knockout(parsed, c["gateway_id"], c["check_first"]),
    "trusted_party": lambda parsed, c: apply_trusted_party(parsed, c["task_id"]),
    "extra_resources": lambda parsed, c: apply_extra_resources(parsed, c["task_id"]),
}