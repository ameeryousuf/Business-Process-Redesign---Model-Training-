import os
import glob
import random
from collections import deque

from app.bpmn_parser import parse_bpmn

RAW_DATASET_DIR = "data/raw_dataset"
OUTPUT_DIR = "data/training_processes"
EVAL_OUTPUT_DIR = "data/eval_processes"
TARGET_COUNT = 3000
EVAL_HOLDOUT_COUNT = 300

MIN_TASKS = 2


def _get_all_node_ids(parsed):
    all_ids = set()
    for t in parsed.tasks:
        all_ids.add(t["id"])
    for g in parsed.gateways:
        all_ids.add(g["id"])
    for e in parsed.end_events:
        all_ids.add(e["id"])
    for o in parsed.other_elements:
        all_ids.add(o["id"])
    return all_ids


def _check_connectivity(parsed):
    graph_out = {}
    for flow in parsed.flows:
        graph_out.setdefault(flow["source"], []).append(flow["target"])

    all_ids = _get_all_node_ids(parsed)

    reachable = set()
    queue = deque()
    for s in parsed.start_events:
        reachable.add(s["id"])
        queue.append(s["id"])

    while queue:
        node = queue.popleft()
        for target in graph_out.get(node, []):
            if target not in reachable:
                reachable.add(target)
                queue.append(target)

    unreachable = all_ids - reachable
    total = len(all_ids)
    unreachable_count = len(unreachable)

    is_fully_connected = unreachable_count == 0
    return is_fully_connected, unreachable_count, total


def _check_end_reachability(parsed):
    graph_out = {}
    for flow in parsed.flows:
        graph_out.setdefault(flow["source"], []).append(flow["target"])

    reachable = set()
    queue = deque()
    for s in parsed.start_events:
        reachable.add(s["id"])
        queue.append(s["id"])

    while queue:
        node = queue.popleft()
        for target in graph_out.get(node, []):
            if target not in reachable:
                reachable.add(target)
                queue.append(target)

    end_ids = {e["id"] for e in parsed.end_events}
    return len(reachable & end_ids) > 0


def _check_no_orphan_flows(parsed):
    known_ids = _get_all_node_ids(parsed)
    for s in parsed.start_events:
        known_ids.add(s["id"])

    for flow in parsed.flows:
        if flow["source"] not in known_ids or flow["target"] not in known_ids:
            return False

    return True


def is_valid_process(filepath):
    try:
        parsed = parse_bpmn(filepath)
    except Exception:
        return False, "parse_error"

    if len(parsed.tasks) < MIN_TASKS:
        return False, "too_few_tasks"

    if len(parsed.start_events) == 0:
        return False, "no_start_event"

    if len(parsed.end_events) == 0:
        return False, "no_end_event"

    if len(parsed.flows) == 0:
        return False, "no_flows"

    if not _check_no_orphan_flows(parsed):
        return False, "orphan_flow_reference"

    is_connected, unreachable_count, total_count = _check_connectivity(parsed)
    if not is_connected:
        return False, "disconnected_nodes"

    if not _check_end_reachability(parsed):
        return False, "end_not_reachable"

    return True, "valid"


def find_all_bpmn_files(root_dir):
    pattern = os.path.join(root_dir, "**", "*.bpmn")
    return glob.glob(pattern, recursive=True)


def build_filtered_dataset():
    all_files = find_all_bpmn_files(RAW_DATASET_DIR)
    print(f"Found {len(all_files)} total .bpmn files")

    valid_files = []
    rejection_counts = {}

    for filepath in all_files:
        is_valid, reason = is_valid_process(filepath)
        if is_valid:
            valid_files.append(filepath)
        else:
            rejection_counts[reason] = rejection_counts.get(reason, 0) + 1

    print(f"Found {len(valid_files)} valid, structurally sound files")
    print("\nRejection breakdown:")
    for reason, count in sorted(rejection_counts.items(), key=lambda x: -x[1]):
        print(f"  {reason}: {count}")

    random.seed(42)
    random.shuffle(valid_files)

    if len(valid_files) <= EVAL_HOLDOUT_COUNT:
        print(f"\nWARNING: not enough valid files to reserve {EVAL_HOLDOUT_COUNT} for evaluation")
        eval_files = valid_files
        train_pool = []
    else:
        eval_files = valid_files[:EVAL_HOLDOUT_COUNT]
        train_pool = valid_files[EVAL_HOLDOUT_COUNT:]

    if len(train_pool) > TARGET_COUNT:
        train_selected = random.sample(train_pool, TARGET_COUNT)
    else:
        train_selected = train_pool

    os.makedirs(OUTPUT_DIR, exist_ok=True)
    for i, filepath in enumerate(train_selected):
        dest_path = os.path.join(OUTPUT_DIR, f"process_{i:04d}.bpmn")
        with open(filepath, "r", encoding="utf-8") as src:
            content = src.read()
        with open(dest_path, "w", encoding="utf-8") as dst:
            dst.write(content)

    os.makedirs(EVAL_OUTPUT_DIR, exist_ok=True)
    for i, filepath in enumerate(eval_files):
        dest_path = os.path.join(EVAL_OUTPUT_DIR, f"eval_{i:04d}.bpmn")
        with open(filepath, "r", encoding="utf-8") as src:
            content = src.read()
        with open(dest_path, "w", encoding="utf-8") as dst:
            dst.write(content)

    print(f"\nCopied {len(train_selected)} files into {OUTPUT_DIR} (training)")
    print(f"Copied {len(eval_files)} files into {EVAL_OUTPUT_DIR} (held-out evaluation, never used in training)")


if __name__ == "__main__":
    build_filtered_dataset()
