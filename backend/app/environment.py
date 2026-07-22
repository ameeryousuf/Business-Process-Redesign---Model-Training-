import copy
from app.bpmn_parser import parse_bpmn
from app.metrics_calculator import calculate_metrics
from app.state_builder import build_state, HEURISTIC_ORDER

from app.heuristics.executor_parallelism import apply_parallelism
from app.heuristics.executor_elimination import apply_elimination
from app.heuristics.executor_automation import apply_automation
from app.heuristics.executor_composition import apply_composition
from app.heuristics.executor_case_based_work import apply_case_based_work
from app.heuristics.executor_resequencing import apply_resequencing
from app.heuristics.executor_numerical_involvement import apply_numerical_involvement
from app.heuristics.executor_knockout import apply_knockout
from app.heuristics.executor_trusted_party import apply_trusted_party
from app.heuristics.executor_extra_resources import apply_extra_resources


class ProcessRedesignEnv:
    def __init__(self, bpmn_path, time_low=5, time_high=10, cost_low=50, cost_high=100, max_steps=10):
        self.bpmn_path = bpmn_path
        self.time_low = time_low
        self.time_high = time_high
        self.cost_low = cost_low
        self.cost_high = cost_high
        self.max_steps = max_steps

    def reset(self):
        self.parsed = parse_bpmn(self.bpmn_path)
        self.step_count = 0
        self.baseline_metrics = calculate_metrics(self.parsed)
        return self._get_state()

    def _get_state(self):
        metrics = calculate_metrics(self.parsed)
        state, details = build_state(
            self.parsed,
            metrics["total_time_hours"],
            metrics["total_cost_usd"],
            self.time_low, self.time_high,
            self.cost_low, self.cost_high
        )
        self.current_metrics = metrics
        self.current_details = details
        return state

    def _apply_action(self, action):
        candidates = self.current_details[action]

        if not candidates:
            return None

        if action == "parallelism":
            c = candidates[0]
            return apply_parallelism(self.parsed, c["task_a"], c["task_b"])

        if action == "elimination":
            c = candidates[0]
            return apply_elimination(self.parsed, c["task_id"])

        if action == "automation":
            c = candidates[0]
            return apply_automation(self.parsed, c["task_id"])

        if action == "composition":
            c = candidates[0]
            return apply_composition(self.parsed, c["task_a"], c["task_b"])

        if action == "case_based_work":
            c = candidates[0]
            return apply_case_based_work(self.parsed, c["gateway_id"])

        if action == "resequencing":
            c = candidates[0]
            return apply_resequencing(self.parsed, c["expensive_task"], c["cheaper_task"])

        if action == "numerical_involvement":
            roles = candidates
            if len(roles) < 2:
                return None
            return apply_numerical_involvement(self.parsed, roles[0], roles[1])

        if action == "knockout":
            c = candidates[0]
            return apply_knockout(self.parsed, c["gateway_id"], c["check_first"])

        if action == "trusted_party":
            c = candidates[0]
            return apply_trusted_party(self.parsed, c["task_id"])

        if action == "extra_resources":
            c = candidates[0]
            return apply_extra_resources(self.parsed, c["task_id"])

        return None

    def step(self, action):
        self.step_count += 1

        eligible_actions = [name for name in HEURISTIC_ORDER if self.current_details[name]]

        if action not in eligible_actions:
            done = self.step_count >= self.max_steps
            return self._get_state(), -1.0, done, {"reason": "invalid_action"}

        new_parsed = self._apply_action(action)

        if new_parsed is None:
            done = self.step_count >= self.max_steps
            return self._get_state(), -1.0, done, {"reason": "execution_failed"}

        old_metrics = self.current_metrics
        new_metrics = calculate_metrics(new_parsed)

        if old_metrics["total_time_hours"] > 0:
            time_improvement = (old_metrics["total_time_hours"] - new_metrics["total_time_hours"]) / old_metrics["total_time_hours"]
        else:
            time_improvement = 0

        if old_metrics["total_cost_usd"] > 0:
            cost_improvement = (old_metrics["total_cost_usd"] - new_metrics["total_cost_usd"]) / old_metrics["total_cost_usd"]
        else:
            cost_improvement = 0

        reward = 0.5 * time_improvement + 0.5 * cost_improvement

        self.parsed = new_parsed
        next_state = self._get_state()

        eligible_now = [name for name in HEURISTIC_ORDER if self.current_details[name]]
        done = (len(eligible_now) == 0) or (self.step_count >= self.max_steps)

        return next_state, reward, done, {"reason": "applied", "new_metrics": new_metrics}


if __name__ == "__main__":
    env = ProcessRedesignEnv("data/sample_process.bpmn")
    state = env.reset()
    print("Initial state:", state)

    next_state, reward, done, info = env.step("parallelism")
    print("After Parallelism -> reward:", round(reward, 4), "done:", done, "info:", info)

    next_state, reward, done, info = env.step("automation")
    print("After Automation -> reward:", round(reward, 4), "done:", done, "info:", info)