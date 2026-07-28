def _dominant_path_flows(parsed):
    graph = {}
    for flow in parsed.flows:
        graph.setdefault(flow["source"], []).append(flow)

    gateway_type_lookup = {g["id"]: g.get("type", "exclusive") for g in parsed.gateways}

    kept = []
    for source_id, flows in graph.items():
        gtype = gateway_type_lookup.get(source_id)
        if gtype == "parallel" or len(flows) <= 1:
            kept.extend(flows)
        else:
            best = max(flows, key=lambda f: f["probability"])
            kept.append(best)

    return kept


def _drop_cycles(flows, start_id):
    graph = {}
    for flow in flows:
        graph.setdefault(flow["source"], []).append(flow)

    on_stack, visited, kept = set(), set(), []

    def dfs(node_id):
        if node_id in on_stack or node_id in visited:
            return
        visited.add(node_id)
        on_stack.add(node_id)
        for flow in graph.get(node_id, []):
            if flow["target"] in on_stack:
                continue
            kept.append(flow)
            dfs(flow["target"])
        on_stack.discard(node_id)

    dfs(start_id)
    return kept


def compute_critical_path(parsed):
    if not parsed.start_events:
        return {"critical_path": [], "critical_path_hours": 0.0}

    start_id = parsed.start_events[0]["id"]

    flows = _dominant_path_flows(parsed)
    flows = _drop_cycles(flows, start_id)

    successors = {}
    predecessors = {}
    for flow in flows:
        successors.setdefault(flow["source"], []).append(flow["target"])
        predecessors.setdefault(flow["target"], []).append(flow["source"])

    reachable = set()
    stack = [start_id]
    while stack:
        node = stack.pop()
        if node in reachable:
            continue
        reachable.add(node)
        stack.extend(successors.get(node, []))

    in_degree = {n: 0 for n in reachable}
    for flow in flows:
        if flow["source"] in reachable and flow["target"] in reachable:
            in_degree[flow["target"]] = in_degree.get(flow["target"], 0) + 1

    queue = [n for n in reachable if in_degree.get(n, 0) == 0]
    topo_order = []
    while queue:
        node = queue.pop(0)
        topo_order.append(node)
        for target in successors.get(node, []):
            if target not in reachable:
                continue
            in_degree[target] -= 1
            if in_degree[target] == 0:
                queue.append(target)

    time_lookup = {t["id"]: t.get("processing_time", t.get("duration", 0.0)) for t in parsed.tasks}
    name_lookup = {t["id"]: t.get("name") or t["id"] for t in parsed.tasks}

    es, ef = {}, {}
    for node in topo_order:
        preds = [p for p in predecessors.get(node, []) if p in ef]
        es[node] = max((ef[p] for p in preds), default=0.0)
        ef[node] = es[node] + time_lookup.get(node, 0.0)

    if not topo_order:
        return {"critical_path": [], "critical_path_hours": 0.0}

    end_node = topo_order[-1]
    total_hours = ef[end_node]

    lf, ls = {}, {}
    for node in reversed(topo_order):
        succs = [s for s in successors.get(node, []) if s in reachable]
        lf[node] = min((ls[s] for s in succs), default=total_hours)
        ls[node] = lf[node] - time_lookup.get(node, 0.0)

    critical_path = []
    for node in topo_order:
        if node not in time_lookup:
            continue

        slack = round(ls[node] - es[node], 4)
        critical_path.append({
            "task_id": node,
            "name": name_lookup.get(node, node),
            "processing_time_hours": round(time_lookup[node], 2),
            "early_start": round(es[node], 2),
            "early_finish": round(ef[node], 2),
            "late_start": round(ls[node], 2),
            "late_finish": round(lf[node], 2),
            "slack": slack,
            "is_critical": abs(slack) < 1e-6
        })

    return {
        "critical_path": critical_path,
        "critical_path_hours": round(total_hours, 2)
    }


if __name__ == "__main__":
    from app.bpmn_parser import parse_bpmn

    parsed = parse_bpmn("data/sample_process.bpmn")
    result = compute_critical_path(parsed)
    print("Critical path hours:", result["critical_path_hours"])
    for step in result["critical_path"]:
        marker = "*" if step["is_critical"] else " "
        print(f" {marker} {step['name']}: ES={step['early_start']} EF={step['early_finish']} "
              f"LS={step['late_start']} LF={step['late_finish']} slack={step['slack']}")
