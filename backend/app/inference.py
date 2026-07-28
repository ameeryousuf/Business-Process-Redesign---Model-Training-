import copy
import pickle

from app.bpmn_parser import parse_bpmn
from app.translator import translate_names
from app.synthetic_metrics import enrich_process
from app.metrics_calculator import calculate_metrics, calculate_theoretical_metrics, calculate_cycle_time_efficiency
from app.state_builder import build_state, HEURISTIC_ORDER
from app.environment import ProcessRedesignEnv, IMPLAUSIBLE_REWARD_THRESHOLD
from app.bpmn_writer import parsed_to_bpmn_xml
from app.heuristics.registry import HEURISTIC_LABELS
from app.critical_path import compute_critical_path

MODEL_PATH = "data/trained_q_table.pkl"
MIN_IMPROVEMENT_THRESHOLD = 0.02
DEFAULT_SEED = 42

RL_HYPERPARAMETERS = {
    "learning_rate_alpha": 0.1,
    "discount_factor_gamma": 0.9,
    "epsilon_start": 1.0,
    "epsilon_end": 0.05,
    "epsilon_decay_fraction_of_episodes": 0.8,
    "training_episodes": 5000
}

RL_REWARD_FUNCTION = {
    "formula": "reward = 0.5 * time_improvement_fraction + 0.5 * cost_improvement_fraction",
    "description": (
        "time_improvement_fraction and cost_improvement_fraction are each "
        "(old - new) / old for total cycle time and total cost respectively -- "
        "positive when the heuristic improves the process, negative when it makes "
        "it worse. The two are weighted equally so the agent doesn't over-optimize "
        "one dimension at the other's expense."
    ),
    "rejection_rule": (
        f"A step is rejected (treated as if it were never applied) if its reward "
        f"would fall below {IMPLAUSIBLE_REWARD_THRESHOLD} -- a small tolerance for "
        f"noise, but anything worse is assumed to be an implausible/incorrect result "
        f"rather than a genuine trade-off worth taking."
    )
}

RL_UPDATE_RULE = "Q(s,a) <- Q(s,a) + alpha * (reward + gamma * max_a' Q(s',a') - Q(s,a))"


def _describe_state(state):
    time_bucket, cost_bucket = state[0], state[1]
    eligibility_bits = state[2:]
    eligible = [
        HEURISTIC_LABELS[name] for name, bit in zip(HEURISTIC_ORDER, eligibility_bits) if bit
    ]
    return {"time_bucket": time_bucket, "cost_bucket": cost_bucket, "eligible_heuristics": eligible}

def _already_has_baked_metrics(parsed):
    if not parsed.tasks:
        return False
    return all(t.get("resource") for t in parsed.tasks)


def _analysis_snapshot(parsed):
    metrics = calculate_metrics(parsed)
    theoretical = calculate_theoretical_metrics(parsed)
    cte = calculate_cycle_time_efficiency(metrics["total_time_minutes"], theoretical["theoretical_time_minutes"])
    critical_path = compute_critical_path(parsed)

    raci_matrix = [
        {
            "task_id": t["id"],
            "name": t.get("name") or t["id"],
            "is_subprocess": bool(t.get("is_subprocess")),
            "assignments": t.get("raci") or []
        }
        for t in parsed.tasks
    ]

    rework_cost = calculate_metrics(parsed, cost_field="rework_cost")["total_cost_usd"]
    process_cost = round(metrics["total_cost_usd"] - rework_cost, 2)
    cost_distribution = {
        "process_cost": process_cost,
        "rework_cost": rework_cost,
        "waiting_cost": 0.0
    }

    tasks_table = [
        {
            "task_id": t["id"],
            "name": t.get("name") or t["id"],
            "is_subprocess": bool(t.get("is_subprocess")),
            "duration_hours": round(t.get("duration", 0.0), 3),
            "process_time_hours": round(t.get("processing_time", 0.0), 3),
            "rework_time_hours": round(t.get("rework_time_hours", 0.0), 3),
            "waiting_time_hours": round(t.get("waiting_time_hours", 0.0), 3),
            "cost": t.get("cost", 0.0)
        }
        for t in parsed.tasks
    ]

    return {
        "cycle_time_hours": metrics["total_time_hours"],
        "theoretical_cycle_time_hours": theoretical["theoretical_time_hours"],
        "cycle_time_efficiency": cte,
        "critical_path": critical_path["critical_path"],
        "critical_path_hours": critical_path["critical_path_hours"],
        "raci_matrix": raci_matrix,
        "num_tasks": len(parsed.tasks),
        "num_gateways": len(parsed.gateways),
        "cost_distribution": cost_distribution,
        "tasks": tasks_table
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


def _run_redesign(env, enriched, q_table, max_steps, min_improvement_threshold, currency_code="generic_units"):
    as_is_xml = parsed_to_bpmn_xml(enriched, process_id="Process_AsIs")
    as_is_analysis = _analysis_snapshot(enriched)

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

        remaining_candidates = list(eligible_actions)
        applied = False
        best_below_threshold = None

        while remaining_candidates:
            action = pick_best_action(q_table, state, remaining_candidates)
            if action is None:
                break

            pre_step_parsed = copy.deepcopy(env.parsed)
            pre_step_count = env.step_count
            metrics_before = env.current_metrics
            candidates_before = env.current_details[action]
            target_description = _describe_target(action, candidates_before, pre_step_parsed)
            reasoning = _generate_reasoning(action, candidates_before, pre_step_parsed)

            next_state, reward, done, info = env.step(action)

            if info["reason"] == "applied" and reward >= min_improvement_threshold:
                applied = True
                break

            if info["reason"] == "applied" and best_below_threshold is None:
                best_below_threshold = reward

            env.parsed = pre_step_parsed
            env.step_count = pre_step_count
            state = env._get_state()
            remaining_candidates.remove(action)

        if not applied:
            stopping_reason = (
                "Remaining improvements were too small to be worth applying."
                if best_below_threshold is not None
                else "No further eligible heuristics improved the process."
            )
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

        q_values_at_decision = sorted(
            (
                {
                    "action": a,
                    "label": HEURISTIC_LABELS[a],
                    "q_value": round(q_table.get((state, a), 0.0), 4),
                    "chosen": a == action
                }
                for a in eligible_actions
            ),
            key=lambda entry: entry["q_value"],
            reverse=True
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
            "cost_delta_pct": cost_delta_pct,
            "state": _describe_state(state),
            "q_values": q_values_at_decision
        })

        state = next_state

        if done:
            stopping_reason = "No further eligible heuristics improved the process."
            break

    to_be_metrics = env.current_metrics
    to_be_xml = parsed_to_bpmn_xml(env.parsed, process_id="Process_ToBe")
    to_be_analysis = _analysis_snapshot(env.parsed)

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
        "to_be_bpmn_xml": to_be_xml,
        "as_is_analysis": as_is_analysis,
        "to_be_analysis": to_be_analysis,
        "currency": currency_code,
        "rl_details": {
            "algorithm": "Tabular Q-Learning (epsilon-greedy action selection, off-policy TD control)",
            "state_space": {
                "description": (
                    "(time_bucket, cost_bucket, eligibility_bit_1, ..., eligibility_bit_10) -- "
                    "3 time buckets x 3 cost buckets x 2^10 eligibility combinations = 9,216 "
                    "possible states, though only a fraction are ever reached during training."
                ),
                "time_buckets": ["low", "medium", "high"],
                "cost_buckets": ["low", "medium", "high"]
            },
            "action_space": [
                {"action": name, "label": HEURISTIC_LABELS[name]} for name in HEURISTIC_ORDER
            ],
            "reward_function": RL_REWARD_FUNCTION,
            "update_rule": RL_UPDATE_RULE,
            "hyperparameters": RL_HYPERPARAMETERS,
            "q_table_size": len(q_table)
        }
    }


def redesign_process(bpmn_path, q_table, max_steps=10,
                      time_low=5, time_high=20, cost_low=50, cost_high=200,
                      min_improvement_threshold=MIN_IMPROVEMENT_THRESHOLD):

    parsed = parse_bpmn(bpmn_path)

    if _already_has_baked_metrics(parsed):
        enriched = parsed
    else:
        parsed = translate_names(parsed)
        enriched = enrich_process(parsed, seed=DEFAULT_SEED)

    env = ProcessRedesignEnv(bpmn_path, time_low=time_low, time_high=time_high,
                              cost_low=cost_low, cost_high=cost_high, max_steps=max_steps)

    return _run_redesign(env, enriched, q_table, max_steps, min_improvement_threshold,
                          currency_code="generic_units")


def redesign_target_process(data, processes_dir, q_table, max_steps=10,
                             time_low=5, time_high=20, cost_low=50, cost_high=200,
                             min_improvement_threshold=MIN_IMPROVEMENT_THRESHOLD):
    from app.target_schema_parser import parse_target_process

    enriched = parse_target_process(data, processes_dir)

    def _parser_fn(_):
        return parse_target_process(data, processes_dir)

    env = ProcessRedesignEnv(None, time_low=time_low, time_high=time_high,
                              cost_low=cost_low, cost_high=cost_high, max_steps=max_steps,
                              parser_fn=_parser_fn)

    return _run_redesign(env, enriched, q_table, max_steps, min_improvement_threshold,
                          currency_code="USD")


if __name__ == "__main__":
    q_table = load_q_table()

    result = redesign_process("data/eval_final/eval_0001.bpmn", q_table)

    print("AS-IS:", result["as_is"])
    print("TO-BE:", result["to_be"])
    print("Improvement:", result["improvement"])
    print("Stopping reason:", result["stopping_reason"])
    print("\nRedesign Trace:")
    for step in result["redesign_trace"]:
        print(f"  Step {step['step']}: {step['heuristic']} on {step['applied_to']} | Time {step['time_before']}→{step['time_after']} ({step['time_delta_pct']}%) | Cost {step['cost_before']}→{step['cost_after']} ({step['cost_delta_pct']}%)")