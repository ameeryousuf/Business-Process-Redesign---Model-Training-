import os
import glob
import random

from app.bpmn_parser import parse_bpmn
from app.inference import load_q_table, redesign_process

RAW_DATASET_DIR = "data/raw_dataset"
TRAINING_DIR = "data/training_processes"
NUM_EVAL_FILES = 50


def find_all_raw_bpmn_files():
    pattern = os.path.join(RAW_DATASET_DIR, "**", "*.bpmn")
    return glob.glob(pattern, recursive=True)


def is_valid_process(filepath):
    try:
        parsed = parse_bpmn(filepath)
    except Exception:
        return False

    if len(parsed.tasks) < 2:
        return False
    if len(parsed.start_events) == 0 or len(parsed.end_events) == 0:
        return False
    if len(parsed.flows) == 0:
        return False

    return True


def select_held_out_files(seed=123):
    all_raw_files = find_all_raw_bpmn_files()

    valid_files = [f for f in all_raw_files if is_valid_process(f)]

    rng = random.Random(seed)
    rng.shuffle(valid_files)

    held_out = []
    for filepath in valid_files:
        if len(held_out) >= NUM_EVAL_FILES:
            break
        held_out.append(filepath)

    return held_out


def run_evaluation():
    q_table = load_q_table()
    held_out_files = select_held_out_files()

    print(f"Evaluating on {len(held_out_files)} held-out files...")

    results = []
    failures = []

    for i, filepath in enumerate(held_out_files):
        try:
            result = redesign_process(filepath, q_table, seed=i)
            results.append({
                "file": os.path.basename(filepath),
                "time_reduction": result["improvement"]["time_reduction_percent"],
                "cost_reduction": result["improvement"]["cost_reduction_percent"],
                "steps_applied": len(result["redesign_trace"]),
                "stopping_reason": result["stopping_reason"]
            })
        except Exception as e:
            failures.append((os.path.basename(filepath), str(e)))

    return results, failures


if __name__ == "__main__":
    results, failures = run_evaluation()

    print(f"\nSuccessful evaluations: {len(results)}")
    print(f"Failures: {len(failures)}")

    if results:
        avg_time_reduction = sum(r["time_reduction"] for r in results) / len(results)
        avg_cost_reduction = sum(r["cost_reduction"] for r in results) / len(results)
        avg_steps = sum(r["steps_applied"] for r in results) / len(results)

        zero_improvement = [r for r in results if r["steps_applied"] == 0]

        print(f"\nAverage Time Reduction: {avg_time_reduction:.2f}%")
        print(f"Average Cost Reduction: {avg_cost_reduction:.2f}%")
        print(f"Average Steps Applied: {avg_steps:.2f}")
        print(f"Processes with NO improvement found: {len(zero_improvement)}/{len(results)}")

        if zero_improvement:
            print("\nStopping reasons for zero-improvement cases:")
            for r in zero_improvement:
                print(f"  {r['file']}: {r['stopping_reason']}")

    if failures:
        print("\nSample failures (first 5):")
        for filename, error in failures[:5]:
            print(f"  {filename}: {error}")