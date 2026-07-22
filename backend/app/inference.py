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


def _generate_reasoning(action, candidates, parsed):
    task_lookup = {t["id"]: t for t in parsed.tasks}

    if not candidates:
        return "This action was identified as beneficial for the process."

    if action == "parallelism":
        c = candidates[0]
        task_a = task_lookup.get(c["task_a"], {})
        task_b = task_lookup.get(c["task_b"], {})
        name_a = task_a.get("name", c["task_a"])
        name_b = task_b.get("name", c["task_b"])
        res_a = task_a.get("resource", "an unspecified role")
        res_b = task_b.get("resource", "an unspecified role")
        return (
            f"\"{name_a}\" ({res_a}) and \"{name_b}\" ({res_b}) run one after another "
            f"but don't depend on each other's output, and are handled by different resources. "
            f"Running them at the same time removes the wait between them."
        )

    if action == "automation":
        c = candidates[0]
        task = task_lookup.get(c["task_id"], {})
        resource = task.get("resource", "a person")
        name = task.get("name", c["task_id"])
        return (
            f"\"{name}\" is currently handled by {resource} and its name doesn't indicate "
            f"a step that requires human judgment (e.g. approving, reviewing, or deciding). "
            f"Routine, judgment-free steps like this are good automation candidates — "
            f"they typically get faster and cheaper once handled by a system instead of a person."
        )

    if action == "elimination":
        c = candidates[0]
        task = task_lookup.get(c["task_id"], {})
        duration = task.get("duration", 0)
        cost = task.get("cost", 0)
        return (
            f"\"{task.get('name', c['task_id'])}\" has a notably low duration ({duration}h) and cost "
            f"(${cost}) compared to the rest of the process, suggesting it adds little value relative "
            f"to its footprint — a candidate for removal rather than optimization."
        )

    if action == "composition":
        c = candidates[0]
        task_a = task_lookup.get(c["task_a"], {})
        task_b = task_lookup.get(c["task_b"], {})
        res_a = task_a.get("resource", "?")
        res_b = task_b.get("resource", "?")
        return (
            f"\"{task_a.get('name', c['task_a'])}\" and \"{task_b.get('name', c['task_b'])}\" are "
            f"consecutive steps both handled by {res_a}. Since the same resource does both, merging "
            f"them into one step avoids handoff and setup overhead between them."
        )

    if action == "case_based_work":
        c = candidates[0]
        costs = c.get("branch_costs", [])
        return (
            f"The branches at this decision point have noticeably different costs ({costs}), "
            f"suggesting some cases are simpler than others. Routing them differently lets simple "
            f"cases skip the overhead that only complex cases need."
        )

    if action == "resequencing":
        c = candidates[0]
        expensive = task_lookup.get(c["expensive_task"], {})
        cheaper = task_lookup.get(c["cheaper_task"], {})
        return (
            f"\"{cheaper.get('name', c['cheaper_task'])}\" (${cheaper.get('cost', 0)}) currently runs "
            f"after \"{expensive.get('name', c['expensive_task'])}\" (${expensive.get('cost', 0)}), "
            f"which costs more. Doing the cheaper check first avoids paying for the expensive step "
            f"on cases that would fail the cheaper check anyway."
        )

    if action == "numerical_involvement":
        roles = candidates
        return (
            f"The process currently involves multiple distinct human roles ({', '.join(roles)}). "
            f"Consolidating these into fewer roles reduces handoffs and waiting time between people."
        )

    if action == "knockout":
        c = candidates[0]
        task = task_lookup.get(c["check_first"], {})
        prob = c.get("probability", 0)
        return (
            f"\"{task.get('name', c['check_first'])}\" is the less likely outcome at this decision "
            f"point (probability {prob}). Checking it first means cases likely to fail this check "
            f"are caught early, before money is spent on the more expensive path."
        )

    if action == "trusted_party":
        c = candidates[0]
        task = task_lookup.get(c["task_id"], {})
        return (
            f"\"{task.get('name', c['task_id'])}\" has an unusually high cost per hour compared to "
            f"the rest of the process, suggesting it may be cheaper to hand off to a specialized "
            f"external party rather than keep handling it in-house."
        )

    if action == "extra_resources":
        c = candidates[0]
        task = task_lookup.get(c["task_id"], {})
        duration = task.get("duration", 0)
        return (
            f"\"{task.get('name', c['task_id'])}\" takes noticeably longer ({duration}h) than the "
            f"average step in this process, making it a likely bottleneck. Adding resources here "
            f"reduces the time spent waiting on this step, at the cost of higher spend."
        )

    return "This action was identified as beneficial based on the process's current structure."


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
        reasoning = _generate_reasoning(action, candidates_before, pre_step_parsed)

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
            "reason": reasoning,
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

    result = redesign_process("data/training_processes_en/process_0000.bpmn", q_table, seed=1)

    print("AS-IS:", result["as_is"])
    print("TO-BE:", result["to_be"])
    print("Improvement:", result["improvement"])
    print("Stopping reason:", result["stopping_reason"])
    print("\nRedesign Trace:")
    for step in result["redesign_trace"]:
        print(f"\nStep {step['step']}: {step['heuristic']} on {step['applied_to']}")
        print(f"  Reason: {step['reason']}")
        print(f"  Time {step['time_before']}→{step['time_after']} ({step['time_delta_pct']}%) | Cost {step['cost_before']}→{step['cost_after']} ({step['cost_delta_pct']}%)")