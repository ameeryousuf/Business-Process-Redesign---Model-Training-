import os
import glob

from app.inference import load_q_table, redesign_process

EVAL_DIR = "data/eval_final"


def run_evaluation():
    q_table = load_q_table()
    eval_files = sorted(glob.glob(os.path.join(EVAL_DIR, "*.bpmn")))

    print(f"Evaluating on {len(eval_files)} held-out files...")

    results = []
    failures = []

    for filepath in eval_files:
        try:
            result = redesign_process(filepath, q_table)
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