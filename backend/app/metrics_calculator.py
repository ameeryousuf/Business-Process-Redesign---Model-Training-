from collections import deque

from app.bpmn_parser import parse_bpmn


def build_graph(parsed):
    graph = {}
    for flow in parsed.flows:
        graph.setdefault(flow["source"], []).append(flow)
    return graph


def build_task_lookup(parsed):
    return {t["id"]: t for t in parsed.tasks}


def build_gateway_type_lookup(parsed):
    return {g["id"]: g.get("type", "exclusive") for g in parsed.gateways}


def find_parallel_join(split_id, graph, gateway_type_lookup):
    branches = [f["target"] for f in graph.get(split_id, [])]
    if len(branches) < 2:
        return None

    dist_maps = []
    for branch_start in branches:
        dist = {branch_start: 0}
        queue = deque([(branch_start, 0)])
        while queue:
            node, d = queue.popleft()
            for flow in graph.get(node, []):
                target = flow["target"]
                if target not in dist:
                    dist[target] = d + 1
                    queue.append((target, d + 1))
        dist_maps.append(dist)

    common = set(dist_maps[0].keys())
    for dm in dist_maps[1:]:
        common &= set(dm.keys())

    gateway_common = {n for n in common if n in gateway_type_lookup}

    if not gateway_common:
        return None

    best = min(gateway_common, key=lambda n: max(dm.get(n, float("inf")) for dm in dist_maps))
    return best


MAX_INCLUSIVE_SUBSET_ENUMERATION_BRANCHES = 16

USE_TRUE_OR_SEMANTICS_FOR_INCLUSIVE = False


def _task_cost(task, cost_field):
    return task.get(cost_field, 0.0) if task else 0.0


def _expected_inclusive_group(branch_times, branch_costs, branch_probs):
    n = len(branch_probs)

    if n == 0:
        return 0.0, 0.0

    if n > MAX_INCLUSIVE_SUBSET_ENUMERATION_BRANCHES:
        total_prob = sum(branch_probs) or 1.0
        weighted_time = sum(p * t for p, t in zip(branch_probs, branch_times)) / total_prob
        weighted_cost = sum(p * c for p, c in zip(branch_probs, branch_costs))
        return weighted_time, weighted_cost

    expected_time = 0.0
    expected_cost = 0.0

    for mask in range(2 ** n):
        subset_prob = 1.0
        active_indices = []

        for i in range(n):
            if mask & (1 << i):
                subset_prob *= branch_probs[i]
                active_indices.append(i)
            else:
                subset_prob *= (1.0 - branch_probs[i])

        if subset_prob == 0.0:
            continue

        if active_indices:
            subset_time = max(branch_times[i] for i in active_indices)
            subset_cost = sum(branch_costs[i] for i in active_indices)
        else:
            subset_time = 0.0
            subset_cost = 0.0

        expected_time += subset_prob * subset_time
        expected_cost += subset_prob * subset_cost

    return expected_time, expected_cost


def calculate_metrics(parsed, time_field="duration", cost_field="cost"):
    graph = build_graph(parsed)
    task_lookup = build_task_lookup(parsed)
    gateway_type_lookup = build_gateway_type_lookup(parsed)

    def task_time(task):
        if time_field in task:
            return task[time_field]
        if time_field == "processing_time":
            return task.get("duration", 0.0)
        return 0.0

    def task_cost(task):
        return _task_cost(task, cost_field)

    start_id = parsed.start_events[0]["id"]
    visited_parallel_groups = set()
    visited_real_splits = set()

    def traverse(node_id, path_visited, stop_id=None):
        if node_id == stop_id:
            return 0.0, 0.0

        if node_id not in graph:
            return 0.0, 0.0

        if node_id in path_visited:
            return 0.0, 0.0

        path_visited = path_visited | {node_id}

        outgoing = graph[node_id]
        gtype = gateway_type_lookup.get(node_id)

        if gtype == "parallel" and len(outgoing) > 1 and node_id not in visited_real_splits:
            join_id = find_parallel_join(node_id, graph, gateway_type_lookup)

            if join_id is not None:
                visited_real_splits.add(node_id)

                branch_times = []
                branch_costs = []

                for flow in outgoing:
                    target_id = flow["target"]
                    task = task_lookup.get(target_id)
                    t_time = task_time(task) if task else 0.0
                    t_cost = task_cost(task) if task else 0.0

                    if target_id == join_id:
                        down_t, down_c = 0.0, 0.0
                    else:
                        down_t, down_c = traverse(target_id, path_visited, stop_id=join_id)

                    branch_times.append(t_time + down_t)
                    branch_costs.append(t_cost + down_c)

                group_time = max(branch_times) if branch_times else 0.0
                group_cost = sum(branch_costs)

                down_time, down_cost = traverse(join_id, path_visited, stop_id=stop_id)

                return group_time + down_time, group_cost + down_cost

        if (USE_TRUE_OR_SEMANTICS_FOR_INCLUSIVE and gtype == "inclusive"
                and len(outgoing) > 1 and node_id not in visited_real_splits):
            join_id = find_parallel_join(node_id, graph, gateway_type_lookup)

            if join_id is not None:
                visited_real_splits.add(node_id)

                branch_times = []
                branch_costs = []
                branch_probs = []

                for flow in outgoing:
                    target_id = flow["target"]
                    task = task_lookup.get(target_id)
                    t_time = task_time(task) if task else 0.0
                    t_cost = task_cost(task) if task else 0.0

                    if target_id == join_id:
                        down_t, down_c = 0.0, 0.0
                    else:
                        down_t, down_c = traverse(target_id, path_visited, stop_id=join_id)

                    branch_times.append(t_time + down_t)
                    branch_costs.append(t_cost + down_c)
                    branch_probs.append(min(max(flow["probability"], 0.0), 1.0))

                group_time, group_cost = _expected_inclusive_group(branch_times, branch_costs, branch_probs)

                down_time, down_cost = traverse(join_id, path_visited, stop_id=stop_id)

                return group_time + down_time, group_cost + down_cost

        total_time = 0.0
        total_cost = 0.0

        for flow in outgoing:
            target_id = flow["target"]
            flow_prob = flow["probability"]

            if target_id == stop_id:
                continue

            task = task_lookup.get(target_id)

            if task and task.get("parallel_group"):
                group_id = task["parallel_group"]

                if group_id in visited_parallel_groups:
                    continue

                visited_parallel_groups.add(group_id)

                sibling_tasks = [
                    t for t in parsed.tasks
                    if t.get("parallel_group") == group_id
                ]

                group_time = max(task_time(t) for t in sibling_tasks)
                group_cost = sum(task_cost(t) for t in sibling_tasks)

                downstream_time, downstream_cost = traverse(group_id, path_visited, stop_id=stop_id)

                total_time += flow_prob * (group_time + downstream_time)
                total_cost += flow_prob * (group_cost + downstream_cost)
                continue

            if task:
                t_time = task_time(task)
                t_cost = task_cost(task)
            else:
                t_time = 0.0
                t_cost = 0.0

            downstream_time, downstream_cost = traverse(target_id, path_visited, stop_id=stop_id)

            total_time += flow_prob * (t_time + downstream_time)
            total_cost += flow_prob * (t_cost + downstream_cost)

        return total_time, total_cost

    total_time, total_cost = traverse(start_id, frozenset())

    return {
        "total_time_hours": round(total_time, 2),
        "total_time_minutes": round(total_time * 60, 2),
        "total_cost_usd": round(total_cost, 2)
    }


def calculate_theoretical_metrics(parsed):
    result = calculate_metrics(parsed, time_field="processing_time")
    return {
        "theoretical_time_hours": result["total_time_hours"],
        "theoretical_time_minutes": result["total_time_minutes"]
    }


def calculate_cycle_time_efficiency(cycle_time_minutes, theoretical_time_minutes):
    if cycle_time_minutes <= 0:
        return 0.0
    return round(theoretical_time_minutes / cycle_time_minutes, 4)


if __name__ == "__main__":
    parsed = parse_bpmn("data/sample_process.bpmn")
    metrics = calculate_metrics(parsed)
    print("AS-IS Metrics:", metrics)