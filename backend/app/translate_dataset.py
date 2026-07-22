import os
import glob
import time
from concurrent.futures import ThreadPoolExecutor, as_completed

from app.bpmn_parser import parse_bpmn
from app.translator import translate_names
from app.bpmn_writer import parsed_to_bpmn_xml

SOURCE_DIR = "data/training_processes"
OUTPUT_DIR = "data/training_processes_en"
MAX_WORKERS = 3
MAX_RETRIES = 3


def translate_one_file(filepath):
    filename = os.path.basename(filepath)

    for attempt in range(MAX_RETRIES + 1):
        try:
            parsed = parse_bpmn(filepath)
            parsed = translate_names(parsed)
            xml_output = parsed_to_bpmn_xml(parsed, process_id="Process_1")

            dest_path = os.path.join(OUTPUT_DIR, filename)
            with open(dest_path, "w", encoding="utf-8") as f:
                f.write(xml_output)

            return (filename, True, None)

        except Exception as e:
            if attempt < MAX_RETRIES:
                time.sleep(3 * (attempt + 1))
                continue
            return (filename, False, str(e))


def translate_all_files():
    files = sorted(glob.glob(os.path.join(SOURCE_DIR, "*.bpmn")))
    os.makedirs(OUTPUT_DIR, exist_ok=True)

    already_done = {os.path.basename(f) for f in glob.glob(os.path.join(OUTPUT_DIR, "*.bpmn"))}
    remaining = [f for f in files if os.path.basename(f) not in already_done]

    print(f"{len(already_done)} already translated, {len(remaining)} remaining")
    print(f"Translating with {MAX_WORKERS} workers...")

    succeeded = 0
    failed = []
    completed = 0

    with ThreadPoolExecutor(max_workers=MAX_WORKERS) as executor:
        futures = {executor.submit(translate_one_file, f): f for f in remaining}

        for future in as_completed(futures):
            filename, success, error = future.result()
            completed += 1

            if success:
                succeeded += 1
            else:
                failed.append((filename, error))

            if completed % 50 == 0:
                print(f"  {completed}/{len(remaining)} done")

    print(f"\nSucceeded this run: {succeeded}")
    print(f"Failed: {len(failed)}")

    if failed:
        print("\nSample failures:")
        for filename, error in failed[:5]:
            print(f"  {filename}: {error}")


if __name__ == "__main__":
    translate_all_files()