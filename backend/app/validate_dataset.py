import os
import glob
from app.bpmn_parser import parse_bpmn
from app.synthetic_metrics import enrich_process
from app.metrics_calculator import calculate_metrics
from app.state_builder import build_state

DATASET_DIR = "data/training_processes"


def validate_all():
    files = sorted(glob.glob(os.path.join(DATASET_DIR, "*.bpmn")))
    print(f"Validating {len(files)} files...")

    passed = []
    failed = []

    for i, filepath in enumerate(files):
        try:
            parsed = parse_bpmn(filepath)
            enriched = enrich_process(parsed, seed=i)
            metrics = calculate_metrics(enriched)
            state, details = build_state(
                enriched,
                metrics["total_time_hours"],
                metrics["total_cost_usd"],
                time_low=5, time_high=20,
                cost_low=50, cost_high=200
            )
            passed.append(filepath)
        except Exception as e:
            failed.append((filepath, str(e)))

    print(f"Passed: {len(passed)}")
    print(f"Failed: {len(failed)}")

    if failed:
        print("\nSample of failures (first 10):")
        for filepath, error in failed[:10]:
            print(f"  {filepath}: {error}")

    return passed, failed


if __name__ == "__main__":
    validate_all()