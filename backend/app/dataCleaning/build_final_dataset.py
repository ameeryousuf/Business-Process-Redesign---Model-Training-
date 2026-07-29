import os
import glob
from concurrent.futures import ProcessPoolExecutor, as_completed

TRAINING_SOURCE_DIR = "data/training_processes"
EVAL_SOURCE_DIR = "data/eval_processes"

TRAINING_FINAL_DIR = "data/training_final"
EVAL_FINAL_DIR = "data/eval_final"

MAX_WORKERS = os.cpu_count() or 4


def process_one_file(args):
    filepath, output_dir, seed = args

    from app.bpmn_parser import parse_bpmn
    from app.dataCleaning.translator import translate_names
    from app.dataCleaning.synthetic_metrics import enrich_process
    from app.bpmn_writer import parsed_to_bpmn_xml

    filename = os.path.basename(filepath)

    try:
        parsed = parse_bpmn(filepath)
        parsed = translate_names(parsed)
        enriched = enrich_process(parsed, seed=seed)

        xml_output = parsed_to_bpmn_xml(enriched, process_id="Process_1", include_metrics=True)

        dest_path = os.path.join(output_dir, filename)
        with open(dest_path, "w", encoding="utf-8") as f:
            f.write(xml_output)

        return (filename, True, None)

    except Exception as e:
        return (filename, False, str(e))


def build_final_set(source_dir, output_dir, seed_offset=0):
    files = sorted(glob.glob(os.path.join(source_dir, "*.bpmn")))
    os.makedirs(output_dir, exist_ok=True)

    already_done = {os.path.basename(f) for f in glob.glob(os.path.join(output_dir, "*.bpmn"))}
    remaining = [(f, output_dir, i + seed_offset) for i, f in enumerate(files) if os.path.basename(f) not in already_done]

    print(f"{len(already_done)} already built, {len(remaining)} remaining out of {len(files)} total")
    print(f"Using {MAX_WORKERS} worker processes")

    succeeded = 0
    failed = []
    completed = 0

    with ProcessPoolExecutor(max_workers=MAX_WORKERS) as executor:
        futures = {executor.submit(process_one_file, args): args for args in remaining}

        for future in as_completed(futures):
            filename, success, error = future.result()
            completed += 1

            if success:
                succeeded += 1
            else:
                failed.append((filename, error))

            if completed % 50 == 0:
                print(f"  {completed}/{len(remaining)} done")

    print(f"\n{output_dir}: Succeeded this run: {succeeded}, Failed: {len(failed)}")

    if failed:
        print("Sample failures:")
        for filename, error in failed[:5]:
            print(f"  {filename}: {error}")

    return succeeded, failed


if __name__ == "__main__":
    print("Building final training dataset (translated + baked metrics)...")
    build_final_set(TRAINING_SOURCE_DIR, TRAINING_FINAL_DIR, seed_offset=0)

    print("\nBuilding final eval dataset (translated + baked metrics)...")
    build_final_set(EVAL_SOURCE_DIR, EVAL_FINAL_DIR, seed_offset=100000)
