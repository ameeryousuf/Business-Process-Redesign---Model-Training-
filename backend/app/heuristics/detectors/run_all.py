from app.bpmn_parser import parse_bpmn
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

if __name__ == "__main__":
    parsed = parse_bpmn("data/sample_process.bpmn")

    print("Parallelism:", detect_parallelism(parsed))
    print("Elimination:", detect_elimination(parsed))
    print("Automation:", detect_automation(parsed))
    print("Composition:", detect_composition(parsed))
    print("Case-Based Work:", detect_case_based_work(parsed))
    print("Resequencing:", detect_resequencing(parsed))
    print("Numerical Involvement:", detect_numerical_involvement(parsed))
    print("Knock-Out:", detect_knockout(parsed))
    print("Trusted Party:", detect_trusted_party(parsed))
    print("Extra Resources:", detect_extra_resources(parsed))