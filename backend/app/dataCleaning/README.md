# Data Cleaning Pipeline

Reproduces the final training/evaluation dataset (`data/target_training/`, `data/target_eval/`)
from the raw Camunda BPMN dataset. Run from `backend/` with the project's virtualenv active,
in this exact order:

## 1. Get the raw dataset

Clone/download the source repository into `data/raw_dataset/`:

```
git clone https://github.com/camunda/bpmn-for-research data/raw_dataset
```

Academic/research use only — credit Camunda as the source.

## 2. Validate and split — `dataset_builder.py`

```
python -m app.dataCleaning.dataset_builder
```

Scans every `.bpmn` file under `data/raw_dataset/`, keeps only structurally valid ones (has
tasks/start/end/flows, no orphan flow references, fully connected, end reachable from start),
shuffles with a fixed seed (42), and splits them:

- `data/eval_processes/` — 300 files, permanently held out, never used in training
- `data/training_processes/` — remaining files (capped at 3,000)

## 3. Translate to English — `translator.py`

Used internally by step 4, not run standalone. Uses `argostranslate` (offline, DE->EN) to
translate task/gateway/event names. Requires the `translate-de_en` argos-translate package to be
installed in the venv.

## 4. Enrich with synthetic metrics — `synthetic_metrics.py`

Also used internally by step 4. Assigns each task a random resource (Officer/Clerk/Manager/
Analyst/System), a duration and cost derived from that resource, and normalizes gateway branch
probabilities.

## 5. Bake the final BPMN corpus — `build_final_dataset.py`

```
python -m app.dataCleaning.build_final_dataset
```

For every file in `data/training_processes/` and `data/eval_processes/`: parse -> translate
(step 3) -> enrich (step 4) -> re-serialize back to BPMN 2.0 XML with the computed metrics baked
in as extension data. Parallelized across CPU cores. Produces:

- `data/training_final/`
- `data/eval_final/`

## 6. Convert to the target relational schema — `convert_to_target_schema.py`

```
python -m app.dataCleaning.convert_to_target_schema
```

Converts each baked BPMN file into the Digital Twin SaaS's relational JSON schema (the same
shape the live `/redesign/process` endpoint consumes): collapses pass-through nodes, detects and
collapses rework loops into `expected_rework_time`, relabels task ids, assigns synthetic PKR
hourly rates per resource, and builds `process_task[]`/`gateways[]` arrays. Produces the final
dataset:

- `data/target_training/` (id offset 0)
- `data/target_eval/` (id offset 100000)

## 7. Train the agent

Once the final dataset exists, train the live Q-table with `app/rl/train_target_schema.py` (see
the main backend documentation) — this is a separate step, not part of this folder.
