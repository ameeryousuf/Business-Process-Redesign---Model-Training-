import glob
import os

from app.bpmn_parser import parse_bpmn
from app.synthetic_metrics import enrich_process
from app.metrics_calculator import calculate_metrics
from app.heuristics.detectors.parallelism import detect_parallelism
from app.heuristics.executors.executor_parallelism import apply_parallelism

DATASET_DIR = "data/training_processes_en"


def scan_all_files():
    files = sorted(glob.glob(os.path.join(DATASET_DIR, "*.bpmn")))

    failing_cases = []
    checked = 0

    for i, filepath in enumerate(files):
        try:
            parsed = parse_bpmn(filepath)
            enriched = enrich_process(parsed, seed=i)

            result = detect_parallelism(enriched)
            if not result["eligible"]:
                continue

            for candidate in result["candidates"]:
                checked += 1
                before_metrics = calculate_metrics(enriched)

                new_parsed = apply_parallelism(enriched, candidate["task_a"], candidate["task_b"])
                if new_parsed is None:
                    continue

                after_metrics = calculate_metrics(new_parsed)

                time_improvement = (before_metrics["total_time_hours"] - after_metrics["total_time_hours"]) / before_metrics["total_time_hours"] if before_metrics["total_time_hours"] > 0 else 0
                cost_improvement = (before_metrics["total_cost_usd"] - after_metrics["total_cost_usd"]) / before_metrics["total_cost_usd"] if before_metrics["total_cost_usd"] > 0 else 0
                reward = 0.5 * time_improvement + 0.5 * cost_improvement

                if reward < -0.02:
                    failing_cases.append((os.path.basename(filepath), candidate, reward))

        except Exception:
            continue

    print(f"Checked {checked} parallelism applications across {len(files)} files")
    print(f"Failing cases (reward < -0.02): {len(failing_cases)}")

    if failing_cases:
        print("\nFirst 10 failing cases:")
        for filename, candidate, reward in failing_cases[:10]:
            print(f"  {filename}: reward={reward:.4f}, candidate={candidate}")


if __name__ == "__main__":
    scan_all_files()