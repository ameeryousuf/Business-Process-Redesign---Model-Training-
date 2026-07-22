import copy


def apply_elimination(parsed, task_id):
    new_parsed = copy.deepcopy(parsed)

    flows = new_parsed.flows

    incoming_flow = next((f for f in flows if f["target"] == task_id), None)
    outgoing_flow = next((f for f in flows if f["source"] == task_id), None)

    if incoming_flow is None or outgoing_flow is None:
        return None

    new_parsed.tasks = [t for t in new_parsed.tasks if t["id"] != task_id]

    flows.remove(incoming_flow)
    flows.remove(outgoing_flow)

    flows.append({
        "id": f"{incoming_flow['id']}_bypass",
        "source": incoming_flow["source"],
        "target": outgoing_flow["target"],
        "probability": incoming_flow["probability"]
    })

    return new_parsed


if __name__ == "__main__":
    from app.bpmn_parser import parse_bpmn
    from app.metrics_calculator import calculate_metrics

    parsed = parse_bpmn("data/sample_process.bpmn")
    print("AS-IS Metrics:", calculate_metrics(parsed))

    new_parsed = apply_elimination(parsed, "Task_D")
    print("TO-BE Metrics (after Eliminating Task_D):", calculate_metrics(new_parsed))