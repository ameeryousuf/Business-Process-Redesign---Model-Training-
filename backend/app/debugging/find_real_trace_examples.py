import glob
import os

from app.bpmn_parser import parse_bpmn
from app.metrics_calculator import calculate_metrics
from app.environment import ProcessRedesignEnv
from app.inference import load_q_table, pick_best_action
from app.state_builder import HEURISTIC_ORDER

EVAL_DIR = "data/eval_final"
MIN_IMPROVEMENT_THRESHOLD = 0.02

HEURISTIC_LABEL_TO_KEY = {
    "parallelism": "parallelism",
    "elimination": "elimination",
    "automation": "automation",
    "composition": "composition",
    "case_based_work": "case_based_work",
    "resequencing": "resequencing",
    "numerical_involvement": "numerical_involvement",
    "knockout": "knockout",
    "trusted_party": "trusted_party",
    "extra_resources": "extra_resources",
}


def redesign_final_file(filepath, q_table, max_steps=10):
    parsed = parse_bpmn(filepath)

    env = ProcessRedesignEnv(filepath, time_low=5, time_high=20, cost_low=50, cost_high=200, max_steps=max_steps)
    env.parsed = parsed
    env.step_count = 0
    env.baseline_metrics = calculate_metrics(parsed)

    state = env._get_state()
    trace = []
    step_num = 0

    while True:
        eligible_actions = [name for name in HEURISTIC_ORDER if env.current_details[name]]
        if not eligible_actions or step_num >= max_steps:
            break

        action = pick_best_action(q_table, state, eligible_actions)
        if action is None:
            break

        next_state, reward, done, info = env.step(action)

        if info["reason"] != "applied":
            break
        if reward < MIN_IMPROVEMENT_THRESHOLD:
            break

        step_num += 1
        trace.append({"step": step_num, "heuristic": action})
        state = next_state

        if done:
            break

    return trace


def find_examples_in_real_traces():
    q_table = load_q_table()
    files = sorted(glob.glob(os.path.join(EVAL_DIR, "*.bpmn")))

    found = {name: None for name in HEURISTIC_ORDER}

    for i, filepath in enumerate(files):
        if (i + 1) % 25 == 0:
            remaining = [name for name in HEURISTIC_ORDER if found[name] is None]
            print(f"{i + 1}/{len(files)} done | still missing: {', '.join(remaining) if remaining else 'none - all found!'}")

        if all(found.values()):
            print(f"\nAll heuristics found by file {i + 1}/{len(files)}, stopping early.")
            break

        try:
            trace = redesign_final_file(filepath, q_table)

            for step in trace:
                key = step["heuristic"]
                if found[key] is None:
                    found[key] = (os.path.basename(filepath), step["step"])

        except Exception:
            continue

    print(f"\n{'Heuristic':<25}{'File':<20}{'Step #':<8}")
    print("-" * 55)
    for name in HEURISTIC_ORDER:
        if found[name]:
            filename, step_num = found[name]
            print(f"{name:<25}{filename:<20}{step_num:<8}")
        else:
            print(f"{name:<25}NEVER appears in any real redesign trace across the eval set")


if __name__ == "__main__":
    find_examples_in_real_traces()