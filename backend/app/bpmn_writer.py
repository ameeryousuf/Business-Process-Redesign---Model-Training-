import xml.etree.ElementTree as ET
from collections import deque

BPMN_NS = "http://www.omg.org/spec/BPMN/20100524/MODEL"
BPMNDI_NS = "http://www.omg.org/spec/BPMN/20100524/DI"
DC_NS = "http://www.omg.org/spec/DD/20100524/DC"
DI_NS = "http://www.omg.org/spec/DD/20100524/DI"
COLOR_NS = "http://www.omg.org/spec/BPMN/non-normative/color/1.0"

ET.register_namespace("bpmn", BPMN_NS)
ET.register_namespace("bpmndi", BPMNDI_NS)
ET.register_namespace("dc", DC_NS)
ET.register_namespace("di", DI_NS)
ET.register_namespace("color", COLOR_NS)

NODE_SIZES = {
    "event": (36, 36),
    "gateway": (50, 50),
    "task": (110, 80),
}

COLUMN_SPACING = 220
ROW_SPACING = 80
MARGIN_X = 80
MARGIN_Y = 80
DETOUR_MARGIN = 50
MAX_DETOUR_ATTEMPTS = 6

NODE_COLORS = {
    "start_event": ("#e8f8ee", "#2f9e5e"),
    "end_event": ("#fdecec", "#d64545"),
    "task": ("#eaf2fd", "#3b7dd8"),
    "exclusive": ("#fff6e5", "#d99a1f"),
    "parallel": ("#f1ecfb", "#7c53c9"),
    "inclusive": ("#fff6e5", "#d99a1f"),
    "event_based": ("#fff6e5", "#d99a1f"),
    "complex": ("#fff6e5", "#d99a1f"),
}


def _build_node_type_map(parsed):
    node_types = {}
    node_categories = {}

    for s in parsed.start_events:
        node_types[s["id"]] = "event"
        node_categories[s["id"]] = "start_event"
    for e in parsed.end_events:
        node_types[e["id"]] = "event"
        node_categories[e["id"]] = "end_event"
    for g in parsed.gateways:
        node_types[g["id"]] = "gateway"
        node_categories[g["id"]] = g.get("type", "exclusive")
    for t in parsed.tasks:
        node_types[t["id"]] = "task"
        node_categories[t["id"]] = "task"

    return node_types, node_categories


def _compute_levels(all_node_ids, flows):
    graph_out = {}
    incoming_count = {node_id: 0 for node_id in all_node_ids}

    for flow in flows:
        graph_out.setdefault(flow["source"], []).append(flow["target"])
        if flow["target"] in incoming_count:
            incoming_count[flow["target"]] += 1

    roots = [node_id for node_id in all_node_ids if incoming_count.get(node_id, 0) == 0]
    if not roots and all_node_ids:
        roots = [all_node_ids[0]]

    levels = {}
    visited = set()
    queue = deque()

    for root_id in roots:
        levels[root_id] = 0
        visited.add(root_id)
        queue.append(root_id)

    while queue:
        node = queue.popleft()
        for target in graph_out.get(node, []):
            new_level = levels[node] + 1
            if target not in levels or new_level > levels[target]:
                levels[target] = new_level
            if target not in visited:
                visited.add(target)
                queue.append(target)

    for node_id in all_node_ids:
        if node_id not in levels:
            levels[node_id] = 0

    return levels


def _order_within_levels(all_node_ids, flows, levels):
    nodes_by_level = {}
    for node_id in all_node_ids:
        nodes_by_level.setdefault(levels[node_id], []).append(node_id)

    incoming_map = {}
    for flow in flows:
        incoming_map.setdefault(flow["target"], []).append(flow["source"])

    ordered_position = {}

    for level in sorted(nodes_by_level.keys()):
        node_ids = nodes_by_level[level]

        if level == 0:
            node_ids.sort()
        else:
            def barycenter(node_id):
                preds = incoming_map.get(node_id, [])
                positions = [ordered_position.get(p, 0) for p in preds]
                return sum(positions) / len(positions) if positions else 0
            node_ids.sort(key=barycenter)

        for index, node_id in enumerate(node_ids):
            ordered_position[node_id] = index

        nodes_by_level[level] = node_ids

    return nodes_by_level


def _assign_positions(node_types, nodes_by_level):
    positions = {}

    for level, node_ids in nodes_by_level.items():
        y_cursor = MARGIN_Y
        for node_id in node_ids:
            node_type = node_types.get(node_id, "task")
            width, height = NODE_SIZES[node_type]
            x = MARGIN_X + level * COLUMN_SPACING
            positions[node_id] = {
                "x": x, "y": y_cursor, "width": width, "height": height
            }
            y_cursor += height + ROW_SPACING

    return positions


def _segment_hits_rect(x1, y1, x2, y2, rect):
    rx1, ry1, rx2, ry2 = rect

    if y1 == y2:
        lo_x, hi_x = min(x1, x2), max(x1, x2)
        return lo_x < rx2 and hi_x > rx1 and ry1 < y1 < ry2
    if x1 == x2:
        lo_y, hi_y = min(y1, y2), max(y1, y2)
        return rx1 < x1 < rx2 and lo_y < ry2 and hi_y > ry1
    return False


def _path_collides(path, all_rects, exclude_ids):
    for i in range(len(path) - 1):
        x1, y1 = path[i]
        x2, y2 = path[i + 1]
        for node_id, rect in all_rects.items():
            if node_id in exclude_ids:
                continue
            if _segment_hits_rect(x1, y1, x2, y2, rect):
                return True
    return False


def _build_waypoints(source_id, target_id, positions, levels, all_rects):
    source_pos = positions[source_id]
    target_pos = positions[target_id]
    source_level = levels[source_id]
    target_level = levels[target_id]
    exclude = {source_id, target_id}

    source_x = source_pos["x"] + source_pos["width"]
    source_y = source_pos["y"] + source_pos["height"] // 2
    target_x = target_pos["x"]
    target_y = target_pos["y"] + target_pos["height"] // 2

    level_gap = target_level - source_level

    if level_gap == 1:
        if source_y == target_y:
            path = [(source_x, source_y), (target_x, target_y)]
        else:
            mid_x = source_x + (target_x - source_x) // 2
            path = [
                (source_x, source_y),
                (mid_x, source_y),
                (mid_x, target_y),
                (target_x, target_y),
            ]

        if not _path_collides(path, all_rects, exclude):
            return path

    lo_level = min(source_level, target_level)
    hi_level = max(source_level, target_level)

    relevant_rects = {
        nid: rect for nid, rect in all_rects.items()
        if levels.get(nid) is not None and lo_level <= levels[nid] <= hi_level
        and nid not in exclude
    }

    base_bottom = MARGIN_Y
    for rect in relevant_rects.values():
        base_bottom = max(base_bottom, rect[3])

    target_center_x = target_pos["x"] + target_pos["width"] // 2
    target_bottom_y = target_pos["y"] + target_pos["height"]
    exit_x = source_x + 30

    for attempt in range(MAX_DETOUR_ATTEMPTS):
        detour_y = base_bottom + DETOUR_MARGIN + attempt * DETOUR_MARGIN

        path = [
            (source_x, source_y),
            (exit_x, source_y),
            (exit_x, detour_y),
            (target_center_x, detour_y),
            (target_center_x, target_bottom_y),
        ]

        if not _path_collides(path, all_rects, exclude):
            return path

    return path


def parsed_to_bpmn_xml(parsed, process_id="Process_1"):
    definitions = ET.Element(f"{{{BPMN_NS}}}definitions", {
        "id": "Definitions_1",
        "targetNamespace": "http://bpmn.io/schema/bpmn"
    })

    process = ET.SubElement(definitions, f"{{{BPMN_NS}}}process", {
        "id": process_id,
        "isExecutable": "true"
    })

    known_ids = set()

    for start in parsed.start_events:
        ET.SubElement(process, f"{{{BPMN_NS}}}startEvent", {
            "id": start["id"],
            "name": start.get("name") or ""
        })
        known_ids.add(start["id"])

    for task in parsed.tasks:
        ET.SubElement(process, f"{{{BPMN_NS}}}task", {
            "id": task["id"],
            "name": task.get("name") or ""
        })
        known_ids.add(task["id"])

    for gateway in parsed.gateways:
        gw_type = gateway.get("type", "exclusive")
        tag = "parallelGateway" if gw_type == "parallel" else "exclusiveGateway"
        ET.SubElement(process, f"{{{BPMN_NS}}}{tag}", {
            "id": gateway["id"],
            "name": gateway.get("name") or ""
        })
        known_ids.add(gateway["id"])

    for end in parsed.end_events:
        ET.SubElement(process, f"{{{BPMN_NS}}}endEvent", {
            "id": end["id"],
            "name": end.get("name") or ""
        })
        known_ids.add(end["id"])

    valid_flows = [
        f for f in parsed.flows
        if f["source"] in known_ids and f["target"] in known_ids
    ]

    for flow in valid_flows:
        ET.SubElement(process, f"{{{BPMN_NS}}}sequenceFlow", {
            "id": flow["id"],
            "sourceRef": flow["source"],
            "targetRef": flow["target"]
        })

    node_types, node_categories = _build_node_type_map(parsed)
    all_node_ids = list(known_ids)

    levels = _compute_levels(all_node_ids, valid_flows)
    nodes_by_level = _order_within_levels(all_node_ids, valid_flows, levels)
    positions = _assign_positions(node_types, nodes_by_level)

    all_rects = {
        node_id: (pos["x"], pos["y"], pos["x"] + pos["width"], pos["y"] + pos["height"])
        for node_id, pos in positions.items()
    }

    diagram = ET.SubElement(definitions, f"{{{BPMNDI_NS}}}BPMNDiagram", {"id": "Diagram_1"})
    plane = ET.SubElement(diagram, f"{{{BPMNDI_NS}}}BPMNPlane", {
        "id": "Plane_1",
        "bpmnElement": process_id
    })

    for node_id, pos in positions.items():
        category = node_categories.get(node_id, "task")
        fill, stroke = NODE_COLORS.get(category, NODE_COLORS["task"])

        shape = ET.SubElement(plane, f"{{{BPMNDI_NS}}}BPMNShape", {
            "id": f"{node_id}_di",
            "bpmnElement": node_id,
            f"{{{COLOR_NS}}}background-color": fill,
            f"{{{COLOR_NS}}}border-color": stroke,
        })
        ET.SubElement(shape, f"{{{DC_NS}}}Bounds", {
            "x": str(pos["x"]),
            "y": str(pos["y"]),
            "width": str(pos["width"]),
            "height": str(pos["height"])
        })

    for flow in valid_flows:
        if flow["source"] not in positions or flow["target"] not in positions:
            continue

        edge = ET.SubElement(plane, f"{{{BPMNDI_NS}}}BPMNEdge", {
            "id": f"{flow['id']}_di",
            "bpmnElement": flow["id"],
            f"{{{COLOR_NS}}}border-color": "#8a97a8",
        })

        waypoints = _build_waypoints(flow["source"], flow["target"], positions, levels, all_rects)

        for wx, wy in waypoints:
            ET.SubElement(edge, f"{{{DI_NS}}}waypoint", {"x": str(wx), "y": str(wy)})

    xml_bytes = ET.tostring(definitions, encoding="utf-8", xml_declaration=True)
    return xml_bytes.decode("utf-8")


if __name__ == "__main__":
    from app.bpmn_parser import parse_bpmn

    parsed = parse_bpmn("data/sample_process.bpmn")
    xml_output = parsed_to_bpmn_xml(parsed)
    print(xml_output)