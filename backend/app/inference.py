import copy
import pickle

from app.bpmn_parser import parse_bpmn
from app.translator import translate_names
from app.synthetic_metrics import enrich_process
from app.metrics_calculator import calculate_metrics
from app.state_builder import build_state, HEURISTIC_ORDER
from app.environment import ProcessRedesignEnv
from app.bpmn_writer import parsed_to_bpmn_xml

MODEL_PATH = "data/trained_q_table.pkl"
MIN_IMPROVEMENT_THRESHOLD = 0.02

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
    "extra_resources": "Extra Resources"
}


def _describe_target(action, candidates, parsed):
    task_lookup = {t["id"]: t.get("name") or t["id"] for t in parsed.tasks}

    if not candidates:
        return "Process"

    if action in ("parallelism", "composition"):
        c = candidates[0]
        name_a = task_lookup.get(c["task_a"], c["task_a"])
        name_b = task_lookup.get(c["task_b"], c["task_b"])
        return f"{name_a} & {name_b}"

    if action in ("elimination", "automation", "trusted_party", "extra_resources"):
        c = candidates[0]
        return task_lookup.get(c["task_id"], c["task_id"])

    if action == "resequencing":
        c = candidates[0]
        name_expensive = task_lookup.get(c["expensive_task"], c["expensive_task"])
        name_cheaper = task_lookup.get(c["cheaper_task"], c["cheaper_task"])
        return f"{name_cheaper} moved before {name_expensive}"

    if action == "case_based_work":
        return "Case routing at decision point"

    if action == "numerical_involvement":
        return f"{candidates[0]} role consolidated"

    if action == "knockout":
        c = candidates[0]
        name = task_lookup.get(c["check_first"], c["check_first"])
        return f"{name} checked first"

    return "Process"


def load_q_table(path=MODEL_PATH):
    with open(path, "rb") as f:
        return pickle.load(f)


def pick_best_action(q_table, state, eligible_actions):
    if not eligible_actions:
        return None

    q_values = [(a, q_table.get((state, a), 0.0)) for a in eligible_actions]
    max_q = max(q for _, q in q_values)
    best = [a for a, q in q_values if q == max_q]
    return best[0]


def redesign_process(bpmn_path, q_table, max_steps=10, seed=0,
                      time_low=5, time_high=20, cost_low=50, cost_high=200,
                      min_improvement_threshold=MIN_IMPROVEMENT_THRESHOLD):

    parsed = parse_bpmn(bpmn_path)
    parsed = translate_names(parsed)
    enriched = enrich_process(parsed, seed=seed)

    as_is_xml = parsed_to_bpmn_xml(enriched, process_id="Process_AsIs")

    env = ProcessRedesignEnv(bpmn_path, time_low=time_low, time_high=time_high,
                              cost_low=cost_low, cost_high=cost_high, max_steps=max_steps)
    env.parsed = enriched
    env.step_count = 0
    env.baseline_metrics = calculate_metrics(enriched)

    as_is_metrics = dict(env.baseline_metrics)

    state = env._get_state()
    trace = []
    step_num = 0
    stopping_reason = "No further eligible heuristics improved the process."

    while True:
        eligible_actions = [name for name in HEURISTIC_ORDER if env.current_details[name]]

        if not eligible_actions:
            stopping_reason = "No further eligible heuristics improved the process."
            break

        if step_num >= max_steps:
            stopping_reason = "Reached maximum step limit."
            break

        action = pick_best_action(q_table, state, eligible_actions)

        if action is None:
            stopping_reason = "No further eligible heuristics improved the process."
            break

        pre_step_parsed = copy.deepcopy(env.parsed)
        pre_step_count = env.step_count
        metrics_before = env.current_metrics
        candidates_before = env.current_details[action]
        target_description = _describe_target(action, candidates_before, pre_step_parsed)

        next_state, reward, done, info = env.step(action)

        if info["reason"] != "applied":
            env.parsed = pre_step_parsed
            env.step_count = pre_step_count
            state = env._get_state()
            stopping_reason = "No further eligible heuristics improved the process."
            break

        if reward < min_improvement_threshold:
            env.parsed = pre_step_parsed
            env.step_count = pre_step_count
            state = env._get_state()
            stopping_reason = "Remaining improvements were too small to be worth applying."
            break

        step_num += 1
        metrics_after = info["new_metrics"]

        time_delta_pct = 0.0
        cost_delta_pct = 0.0
        if metrics_before["total_time_hours"] > 0:
            time_delta_pct = round(
                (metrics_before["total_time_hours"] - metrics_after["total_time_hours"]) / metrics_before["total_time_hours"] * 100, 1
            )
        if metrics_before["total_cost_usd"] > 0:
            cost_delta_pct = round(
                (metrics_before["total_cost_usd"] - metrics_after["total_cost_usd"]) / metrics_before["total_cost_usd"] * 100, 1
            )

        trace.append({
            "step": step_num,
            "heuristic": HEURISTIC_LABELS[action],
            "applied_to": target_description,
            "reason": f"Applying {HEURISTIC_LABELS[action]} improved the process based on learned patterns.",
            "time_before": metrics_before["total_time_hours"],
            "time_after": metrics_after["total_time_hours"],
            "cost_before": metrics_before["total_cost_usd"],
            "cost_after": metrics_after["total_cost_usd"],
            "time_delta_pct": time_delta_pct,
            "cost_delta_pct": cost_delta_pct
        })

        state = next_state

        if done:
            stopping_reason = "No further eligible heuristics improved the process."
            break

    to_be_metrics = env.current_metrics
    to_be_xml = parsed_to_bpmn_xml(env.parsed, process_id="Process_ToBe")

    time_reduction_pct = 0.0
    cost_reduction_pct = 0.0

    if as_is_metrics["total_time_hours"] > 0:
        time_reduction_pct = round(
            (as_is_metrics["total_time_hours"] - to_be_metrics["total_time_hours"]) / as_is_metrics["total_time_hours"] * 100, 2
        )

    if as_is_metrics["total_cost_usd"] > 0:
        cost_reduction_pct = round(
            (as_is_metrics["total_cost_usd"] - to_be_metrics["total_cost_usd"]) / as_is_metrics["total_cost_usd"] * 100, 2
        )

    return {
        "as_is": as_is_metrics,
        "to_be": to_be_metrics,
        "improvement": {
            "time_reduction_percent": time_reduction_pct,
            "cost_reduction_percent": cost_reduction_pct
        },
        "redesign_trace": trace,
        "stopping_reason": stopping_reason,
        "as_is_bpmn_xml": as_is_xml,
        "to_be_bpmn_xml": to_be_xml
    }


if __name__ == "__main__":
    q_table = load_q_table()

    result = redesign_process("data/training_processes/process_0000.bpmn", q_table, seed=1)

    print("AS-IS:", result["as_is"])
    print("TO-BE:", result["to_be"])
    print("Improvement:", result["improvement"])
    print("Stopping reason:", result["stopping_reason"])
    print("\nRedesign Trace:")
    for step in result["redesign_trace"]:
        print(f"  Step {step['step']}: {step['heuristic']} on {step['applied_to']} | Time {step['time_before']}→{step['time_after']} ({step['time_delta_pct']}%) | Cost {step['cost_before']}→{step['cost_after']} ({step['cost_delta_pct']}%)")