import xml.etree.ElementTree as ET

BPMN_NS = {
    "bpmn": "http://www.omg.org/spec/BPMN/20100524/MODEL",
    "meta": "http://bpm-redesign-engine/schema/meta"
}

TASK_TAGS = [
    "task", "userTask", "serviceTask", "manualTask",
    "scriptTask", "businessRuleTask", "sendTask", "receiveTask", "callActivity"
]

GATEWAY_TAG_TYPES = {
    "exclusiveGateway": "exclusive",
    "parallelGateway": "parallel",
    "inclusiveGateway": "inclusive",
    "eventBasedGateway": "event_based",
    "complexGateway": "complex"
}


class ParsedProcess:
    def __init__(self):
        self.tasks = []
        self.gateways = []
        self.flows = []
        self.start_events = []
        self.end_events = []


def _extract_metrics(task_element):
    ext = task_element.find("bpmn:extensionElements", BPMN_NS)
    if ext is None:
        return {"duration": 0.0, "cost": 0.0, "resource": None}

    metrics = ext.find("meta:metrics", BPMN_NS)
    if metrics is None:
        return {"duration": 0.0, "cost": 0.0, "resource": None}

    return {
        "duration": float(metrics.get("duration", 0)),
        "cost": float(metrics.get("cost", 0)),
        "resource": metrics.get("resource")
    }


def _extract_probability(flow_element):
    ext = flow_element.find("bpmn:extensionElements", BPMN_NS)
    if ext is None:
        return 1.0

    prob_el = ext.find("meta:probability", BPMN_NS)
    if prob_el is None:
        return 1.0

    return float(prob_el.get("value", 1.0))


def parse_bpmn(filepath):
    tree = ET.parse(filepath)
    root = tree.getroot()
    process = root.find("bpmn:process", BPMN_NS)

    result = ParsedProcess()
    seen_task_ids = set()

    for tag in TASK_TAGS:
        for task in process.findall(f"bpmn:{tag}", BPMN_NS):
            task_id = task.get("id")
            if task_id in seen_task_ids:
                continue
            seen_task_ids.add(task_id)

            metrics = _extract_metrics(task)
            result.tasks.append({
                "id": task_id,
                "name": task.get("name"),
                "duration": metrics["duration"],
                "cost": metrics["cost"],
                "resource": metrics["resource"]
            })

    for tag, gw_type in GATEWAY_TAG_TYPES.items():
        for gateway in process.findall(f"bpmn:{tag}", BPMN_NS):
            result.gateways.append({
                "id": gateway.get("id"),
                "name": gateway.get("name"),
                "type": gw_type
            })

    for flow in process.findall("bpmn:sequenceFlow", BPMN_NS):
        result.flows.append({
            "id": flow.get("id"),
            "source": flow.get("sourceRef"),
            "target": flow.get("targetRef"),
            "probability": _extract_probability(flow)
        })

    for start in process.findall("bpmn:startEvent", BPMN_NS):
        result.start_events.append({
            "id": start.get("id"),
            "name": start.get("name")
        })

    for end in process.findall("bpmn:endEvent", BPMN_NS):
        result.end_events.append({
            "id": end.get("id"),
            "name": end.get("name")
        })

    return result


if __name__ == "__main__":
    parsed = parse_bpmn("data/sample_process.bpmn")

    print("Tasks:")
    for t in parsed.tasks:
        print(" ", t)

    print("Gateways:")
    for g in parsed.gateways:
        print(" ", g)

    print("Flows:")
    for f in parsed.flows:
        print(" ", f)