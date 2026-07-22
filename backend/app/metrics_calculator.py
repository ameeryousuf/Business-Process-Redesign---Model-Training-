from app.bpmn_parser import parse_bpmn


def build_graph(parsed):
    graph = {}
    for flow in parsed.flows:
        graph.setdefault(flow["source"], []).append(flow)
    return graph


def build_task_lookup(parsed):
    return {t["id"]: t for t in parsed.tasks}


def calculate_metrics(parsed):
    graph = build_graph(parsed)
    task_lookup = build_task_lookup(parsed)

    start_id = parsed.start_events[0]["id"]
    visited_parallel_groups = set()

    def traverse(node_id, path_visited):
        if node_id not in graph:
            return 0.0, 0.0

        if node_id in path_visited:
            return 0.0, 0.0

        path_visited = path_visited | {node_id}

        outgoing = graph[node_id]
        total_time = 0.0
        total_cost = 0.0

        for flow in outgoing:
            target_id = flow["target"]
            flow_prob = flow["probability"]

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

                downstream_time, downstream_cost = traverse(group_id, path_visited)

                total_time += flow_prob * (group_time + downstream_time)
                total_cost += flow_prob * (group_cost + downstream_cost)
                continue

            if task:
                task_time = task["duration"]
                task_cost = task["cost"]
            else:
                task_time = 0.0
                task_cost = 0.0

            downstream_time, downstream_cost = traverse(target_id, path_visited)

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