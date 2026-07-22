import os
import glob
import random
from app.bpmn_parser import parse_bpmn

RAW_DATASET_DIR = "data/raw_dataset"
OUTPUT_DIR = "data/training_processes"
TARGET_COUNT = 500


def find_all_bpmn_files(root_dir):
    pattern = os.path.join(root_dir, "**", "*.bpmn")
    return glob.glob(pattern, recursive=True)


def is_valid_process(filepath):
    try:
        parsed = parse_bpmn(filepath)
    except Exception:
        return False

    if len(parsed.tasks) < 2:
        return False
    if len(parsed.start_events) == 0 or len(parsed.end_events) == 0:
        return False
    if len(parsed.flows) == 0:
        return False

    return True


def build_filtered_dataset():
    all_files = find_all_bpmn_files(RAW_DATASET_DIR)
    print(f"Found {len(all_files)} total .bpmn files")

    valid_files = []
    for filepath in all_files:
        if is_valid_process(filepath):
            valid_files.append(filepath)

    print(f"Found {len(valid_files)} valid, parseable files")

    if len(valid_files) < TARGET_COUNT:
        print(f"WARNING: only {len(valid_files)} valid files available, using all of them")
        selected = valid_files
    else:
        random.seed(42)
        selected = random.sample(valid_files, TARGET_COUNT)

    os.makedirs(OUTPUT_DIR, exist_ok=True)

    for i, filepath in enumerate(selected):
        dest_path = os.path.join(OUTPUT_DIR, f"process_{i:04d}.bpmn")
        with open(filepath, "r", encoding="utf-8") as src:
            content = src.read()
        with open(dest_path, "w", encoding="utf-8") as dst:
            dst.write(content)

    print(f"Copied {len(selected)} files into {OUTPUT_DIR}")


if __name__ == "__main__":
    build_filtered_dataset()