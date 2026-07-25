import copy
from app.bpmn_parser import parse_bpmn
from app.metrics_calculator import calculate_metrics
from app.state_builder import build_state, HEURISTIC_ORDER
from app.heuristics.registry import EXECUTORS

IMPLAUSIBLE_REWARD_THRESHOLD = -0.02


class ProcessRedesignEnv:
    def __init__(self, bpmn_path, time_low=5, time_high=10, cost_low=50, cost_high=100, max_steps=10,
                 parser_fn=None):
        self.bpmn_path = bpmn_path
        self.time_low = time_low
        self.time_high = time_high
        self.cost_low = cost_low
        self.cost_high = cost_high
        self.max_steps = max_steps
        self.parser_fn = parser_fn or parse_bpmn

    def reset(self):
        self.parsed = self.parser_fn(self.bpmn_path)
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

        if action == "numerical_involvement":
            return EXECUTORS[action](self.parsed, candidates)

        return EXECUTORS[action](self.parsed, candidates[0])

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

        # Heuristic executors only mutate `duration` (they predate the target schema's
        # finer process/waiting/rework breakdown). processing_time can never legitimately
        # exceed total duration, so clamp it down whenever an executor reduces duration
        # below the stored processing_time -- keeps Theoretical Cycle Time structurally
        # valid even though it can't track the true waiting-vs-processing split per heuristic.
        for task in new_parsed.tasks:
            if "processing_time" in task:
                task["processing_time"] = min(task["processing_time"], task["duration"])

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

        if reward < IMPLAUSIBLE_REWARD_THRESHOLD:
            done = self.step_count >= self.max_steps
            return self._get_state(), -1.0, done, {"reason": "implausible_reward_rejected"}

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