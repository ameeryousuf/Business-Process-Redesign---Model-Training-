import glob
import os
import random

from app.bpmn_parser import parse_bpmn
from app.synthetic_metrics import enrich_process
from app.environment import ProcessRedesignEnv
from app.state_builder import HEURISTIC_ORDER

DATASET_DIR = "data/training_processes_en"
SAMPLE_SIZE = 300


def diagnose():
    files = sorted(glob.glob(os.path.join(DATASET_DIR, "*.bpmn")))
    rng = random.Random(7)
    sample_files = rng.sample(files, min(SAMPLE_SIZE, len(files)))

    eligibility_count = {name: 0 for name in HEURISTIC_ORDER}
    reward_sum = {name: 0.0 for name in HEURISTIC_ORDER}
    reward_count = {name: 0 for name in HEURISTIC_ORDER}

    for i, filepath in enumerate(sample_files):
        try:
            parsed = parse_bpmn(filepath)
            enriched = enrich_process(parsed, seed=i)

            env = ProcessRedesignEnv(filepath, time_low=5, time_high=20, cost_low=50, cost_high=200)
            env.parsed = enriched
            env.step_count = 0
            env.baseline_metrics = None
            env._get_state()

            eligible_here = [name for name in HEURISTIC_ORDER if env.current_details[name]]
            for name in eligible_here:
                eligibility_count[name] += 1

            for name in eligible_here:
                trial_env = ProcessRedesignEnv(filepath, time_low=5, time_high=20, cost_low=50, cost_high=200)
                trial_env.parsed = enriched
                trial_env.step_count = 0
                trial_env.baseline_metrics = None
                trial_env._get_state()

                _, reward, _, info = trial_env.step(name)
                if info["reason"] == "applied":
                    reward_sum[name] += reward
                    reward_count[name] += 1

        except Exception:
            continue

    print(f"Diagnosed {len(sample_files)} files\n")
    print(f"{'Heuristic':<25}{'Eligible in':<18}{'Avg Reward When Applied':<25}")
    print("-" * 68)

    for name in HEURISTIC_ORDER:
        pct_eligible = (eligibility_count[name] / len(sample_files)) * 100
        avg_reward = reward_sum[name] / reward_count[name] if reward_count[name] > 0 else 0.0
        print(f"{name:<25}{pct_eligible:>6.1f}% of files    {avg_reward:>10.4f}")


if __name__ == "__main__":
    diagnose()