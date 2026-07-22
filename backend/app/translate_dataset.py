import os
import glob

from app.bpmn_parser import parse_bpmn
from app.translator import translate_names
from app.bpmn_writer import parsed_to_bpmn_xml

SOURCE_DIR = "data/training_processes"
OUTPUT_DIR = "data/training_processes_en"


def translate_all_files():
    files = sorted(glob.glob(os.path.join(SOURCE_DIR, "*.bpmn")))
    os.makedirs(OUTPUT_DIR, exist_ok=True)

    print(f"Translating {len(files)} files...")

    succeeded = 0
    failed = []

    for i, filepath in enumerate(files):
        filename = os.path.basename(filepath)
        try:
            parsed = parse_bpmn(filepath)
            parsed = translate_names(parsed)
            xml_output = parsed_to_bpmn_xml(parsed, process_id="Process_1")

            dest_path = os.path.join(OUTPUT_DIR, filename)
            with open(dest_path, "w", encoding="utf-8") as f:
                f.write(xml_output)

            succeeded += 1

            if (i + 1) % 50 == 0:
                print(f"  {i + 1}/{len(files)} done")

        except Exception as e:
            failed.append((filename, str(e)))

    print(f"\nSucceeded: {succeeded}")
    print(f"Failed: {len(failed)}")

    if failed:
        print("\nSample failures:")
        for filename, error in failed[:5]:
            print(f"  {filename}: {error}")


if __name__ == "__main__":
    translate_all_files()