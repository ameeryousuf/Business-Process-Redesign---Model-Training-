import random

RESOURCE_POOL = ["Officer", "Clerk", "Manager", "Analyst", "System"]
RESOURCE_HOURLY_RATE = {
    "Officer": 10,
    "Clerk": 8,
    "Manager": 15,
    "Analyst": 12,
    "System": 2
}


def assign_synthetic_task_metrics(parsed, seed=None):
    rng = random.Random(seed)

    for task in parsed.tasks:
        resource = rng.choice(RESOURCE_POOL)
        rate = RESOURCE_HOURLY_RATE[resource]

        if resource == "System":
            duration = round(rng.uniform(0.1, 1.0), 2)
        else:
            duration = round(rng.uniform(1, 8), 2)

        cost = round(duration * rate, 2)

        task["resource"] = resource
        task["duration"] = duration
        task["cost"] = cost

    return parsed


def assign_synthetic_probabilities(parsed, seed=None):
    rng = random.Random(seed)

    gateway_type_lookup = {g["id"]: g.get("type", "exclusive") for g in parsed.gateways}

    graph = {}
    for flow in parsed.flows:
        graph.setdefault(flow["source"], []).append(flow)

    for source_id, outgoing_flows in graph.items():
        if len(outgoing_flows) <= 1:
            for flow in outgoing_flows:
                flow["probability"] = 1.0
            continue

        if gateway_type_lookup.get(source_id) == "parallel":
            for flow in outgoing_flows:
                flow["probability"] = 1.0
            continue

        raw_weights = [rng.uniform(0.1, 1.0) for _ in outgoing_flows]
        total = sum(raw_weights)
        normalized = [round(w / total, 3) for w in raw_weights]

        diff = round(1.0 - sum(normalized), 3)
        normalized[0] = round(normalized[0] + diff, 3)

        for flow, prob in zip(outgoing_flows, normalized):
            flow["probability"] = prob

    return parsed


def enrich_process(parsed, seed=None):
    parsed = assign_synthetic_task_metrics(parsed, seed=seed)
    parsed = assign_synthetic_probabilities(parsed, seed=seed)
    return parsed


if __name__ == "__main__":
    from app.bpmn_parser import parse_bpmn
    from app.utils.metrics_calculator import calculate_metrics

    parsed = parse_bpmn("data/training_processes_en/process_0000.bpmn")
    print("Tasks BEFORE enrichment:", parsed.tasks[:2])

    enriched = enrich_process(parsed, seed=42)
    print("Tasks AFTER enrichment:", enriched.tasks[:2])

    metrics = calculate_metrics(enriched)
    print("Metrics:", metrics)
