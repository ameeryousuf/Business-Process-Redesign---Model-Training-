import glob
import os
import xml.etree.ElementTree as ET

from app.bpmn_parser import parse_bpmn, BPMN_NS

RAW_DATASET_DIR = "data/raw_dataset"
SAMPLE_SIZE = 15


def inspect_orphan_references():
    pattern = os.path.join(RAW_DATASET_DIR, "**", "*.bpmn")
    all_files = glob.glob(pattern, recursive=True)

    checked = 0
    orphan_examples = []

    for filepath in all_files:
        if checked >= SAMPLE_SIZE:
            break

        try:
            parsed = parse_bpmn(filepath)
        except Exception:
            continue

        known_ids = set()
        for t in parsed.tasks:
            known_ids.add(t["id"])
        for g in parsed.gateways:
            known_ids.add(g["id"])
        for s in parsed.start_events:
            known_ids.add(s["id"])
        for e in parsed.end_events:
            known_ids.add(e["id"])

        bad_flows = [f for f in parsed.flows if f["source"] not in known_ids or f["target"] not in known_ids]

        if not bad_flows:
            continue

        tree = ET.parse(filepath)
        root = tree.getroot()
        process = root.find("bpmn:process", BPMN_NS)

        all_element_ids_in_file = {}
        for elem in process.iter():
            elem_id = elem.get("id")
            if elem_id:
                tag_name = elem.tag.split("}")[-1]
                all_element_ids_in_file[elem_id] = tag_name

        checked += 1
        bad_flow = bad_flows[0]
        missing_id = bad_flow["source"] if bad_flow["source"] not in known_ids else bad_flow["target"]
        actual_tag = all_element_ids_in_file.get(missing_id, "ID_NOT_FOUND_ANYWHERE")

        orphan_examples.append((os.path.basename(filepath), missing_id, actual_tag))

    print(f"Inspected {checked} files with orphan flow references\n")
    for filename, missing_id, actual_tag in orphan_examples:
        print(f"  {filename}")
        print(f"    Missing ID: {missing_id}")
        print(f"    Actual element type: <{actual_tag}>\n")


if __name__ == "__main__":
    inspect_orphan_references()