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

INTERMEDIATE_EVENT_TAGS = [
    "intermediateCatchEvent",
    "intermediateThrowEvent",
    "boundaryEvent",
]

SUBPROCESS_TAGS = [
    "subProcess",
    "transaction",
    "adHocSubProcess",
]


class ParsedProcess:
    def __init__(self):
        self.tasks = []
        self.gateways = []
        self.flows = []
        self.start_events = []
        self.end_events = []
        self.other_elements = []


# Optional per-task keys used by the target-schema pipeline (app/target_schema_parser.py):
#   value_classification: "VA" | "BVA" | "NVA" | None  -- real value-add taxonomy when available
#   is_subprocess: bool  -- True for tasks resolved from a child_process_id reference;
#                           these are frozen (excluded from all heuristic detectors)
# bpmn_parser.py never sets these; callers should treat their absence as None / False.


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
    return _parse_root(root)


def parse_bpmn_string(xml_string):
    root = ET.fromstring(xml_string)
    return _parse_root(root)


def _parse_root(root):
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

    for tag in INTERMEDIATE_EVENT_TAGS:
        for elem in process.findall(f"bpmn:{tag}", BPMN_NS):
            result.other_elements.append({
                "id": elem.get("id"),
                "name": elem.get("name"),
                "kind": tag
            })

    for tag in SUBPROCESS_TAGS:
        for elem in process.findall(f"bpmn:{tag}", BPMN_NS):
            result.other_elements.append({
                "id": elem.get("id"),
                "name": elem.get("name"),
                "kind": tag
            })
            for sub_task_tag in TASK_TAGS:
                for sub_task in elem.findall(f"bpmn:{sub_task_tag}", BPMN_NS):
                    sub_id = sub_task.get("id")
                    if sub_id in seen_task_ids:
                        continue
                    seen_task_ids.add(sub_id)
                    metrics = _extract_metrics(sub_task)
                    result.tasks.append({
                        "id": sub_id,
                        "name": sub_task.get("name"),
                        "duration": metrics["duration"],
                        "cost": metrics["cost"],
                        "resource": metrics["resource"]
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

    print("Other elements (intermediate events, subprocesses):")
    for o in parsed.other_elements:
        print(" ", o)