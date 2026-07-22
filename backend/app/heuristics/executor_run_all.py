from app.bpmn_parser import parse_bpmn
from app.metrics_calculator import calculate_metrics

from app.heuristics.executor_parallelism import apply_parallelism
from app.heuristics.executor_elimination import apply_elimination
from app.heuristics.executor_automation import apply_automation
from app.heuristics.executor_composition import apply_composition
from app.heuristics.executor_case_based_work import apply_case_based_work
from app.heuristics.executor_resequencing import apply_resequencing
from app.heuristics.executor_numerical_involvement import apply_numerical_involvement
from app.heuristics.executor_knockout import apply_knockout
from app.heuristics.executor_trusted_party import apply_trusted_party
from app.heuristics.executor_extra_resources import apply_extra_resources


if __name__ == "__main__":
    base_parsed = parse_bpmn("data/sample_process.bpmn")
    as_is = calculate_metrics(base_parsed)
    print("AS-IS Metrics:", as_is)
    print("-" * 60)

    result = calculate_metrics(apply_parallelism(base_parsed, "Task_A", "Task_B"))
    print("Parallelism (Task_A, Task_B):         ", result)

    result = calculate_metrics(apply_elimination(base_parsed, "Task_D"))
    print("Elimination (Task_D):                 ", result)

    result = calculate_metrics(apply_automation(base_parsed, "Task_B"))
    print("Automation (Task_B):                  ", result)

    result = calculate_metrics(apply_composition(base_parsed, "Task_A", "Task_B"))
    print("Composition (Task_A + Task_B):        ", result)

    result = calculate_metrics(apply_case_based_work(base_parsed, "Gateway_1"))
    print("Case-Based Work (Gateway_1):          ", result)

    result = calculate_metrics(apply_resequencing(base_parsed, "Task_A", "Task_B"))
    print("Resequencing (Task_A, Task_B):        ", result)

    result = calculate_metrics(apply_numerical_involvement(base_parsed, "Clerk", "Officer"))
    print("Numerical Involvement (Clerk→Officer):", result)

    result = calculate_metrics(apply_knockout(base_parsed, "Gateway_1", "Task_D"))
    print("Knock-Out (check Task_D first):       ", result)

    result = calculate_metrics(apply_trusted_party(base_parsed, "Task_A"))
    print("Trusted Party (outsource Task_A):     ", result)

    result = calculate_metrics(apply_extra_resources(base_parsed, "Task_A"))
    print("Extra Resources (Task_A):             ", result)