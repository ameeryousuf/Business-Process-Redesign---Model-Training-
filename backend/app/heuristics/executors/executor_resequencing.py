import copy


def apply_resequencing(parsed, expensive_task_id, cheaper_task_id):
    new_parsed = copy.deepcopy(parsed)

    flows = new_parsed.flows

    incoming_flows = [f for f in flows if f["target"] == expensive_task_id]
    middle_flows = [f for f in flows if f["source"] == expensive_task_id and f["target"] == cheaper_task_id]
    outgoing_flows = [f for f in flows if f["source"] == cheaper_task_id]

    if len(incoming_flows) != 1 or len(middle_flows) != 1 or len(outgoing_flows) != 1:
        return None

    incoming_to_expensive = incoming_flows[0]
    middle_flow = middle_flows[0]
    outgoing_from_cheaper = outgoing_flows[0]

    flows.remove(incoming_to_expensive)
    flows.remove(middle_flow)
    flows.remove(outgoing_from_cheaper)

    flows.append({"id": f"{incoming_to_expensive['id']}_new", "source": incoming_to_expensive["source"], "target": cheaper_task_id, "probability": incoming_to_expensive["probability"]})
    flows.append({"id": f"{middle_flow['id']}_new", "source": cheaper_task_id, "target": expensive_task_id, "probability": middle_flow["probability"]})
    flows.append({"id": f"{outgoing_from_cheaper['id']}_new", "source": expensive_task_id, "target": outgoing_from_cheaper["target"], "probability": outgoing_from_cheaper["probability"]})

    return new_parsed


if __name__ == "__main__":
    from app.bpmn_parser import parse_bpmn
    from app.metrics_calculator import calculate_metrics

    parsed = parse_bpmn("data/sample_process.bpmn")
    print("AS-IS Metrics:", calculate_metrics(parsed))

    new_parsed = apply_resequencing(parsed, "Task_A", "Task_B")
    print("TO-BE Metrics (after Resequencing Task_A/Task_B):", calculate_metrics(new_parsed))