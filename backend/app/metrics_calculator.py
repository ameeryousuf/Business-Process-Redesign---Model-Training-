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


def calculate_metrics(parsed):
    graph = build_graph(parsed)
    task_lookup = build_task_lookup(parsed)
    gateway_type_lookup = build_gateway_type_lookup(parsed)

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
                    t_time = task["duration"] if task else 0.0
                    t_cost = task["cost"] if task else 0.0

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

                group_time = max(t["duration"] for t in sibling_tasks)
                group_cost = sum(t["cost"] for t in sibling_tasks)

                downstream_time, downstream_cost = traverse(group_id, path_visited, stop_id=stop_id)

                total_time += flow_prob * (group_time + downstream_time)
                total_cost += flow_prob * (group_cost + downstream_cost)
                continue

            if task:
                task_time = task["duration"]
                task_cost = task["cost"]
            else:
                task_time = 0.0
                task_cost = 0.0

            downstream_time, downstream_cost = traverse(target_id, path_visited, stop_id=stop_id)

            total_time += flow_prob * (task_time + downstream_time)
            total_cost += flow_prob * (task_cost + downstream_cost)

        return total_time, total_cost

    total_time, total_cost = traverse(start_id, frozenset())

    return {
        "total_time_hours": round(total_time, 2),
        "total_cost_usd": round(total_cost, 2)
    }


if __name__ == "__main__":
    parsed = parse_bpmn("data/sample_process.bpmn")
    metrics = calculate_metrics(parsed)
    print("AS-IS Metrics:", metrics)