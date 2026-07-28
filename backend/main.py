from fastapi import FastAPI, UploadFile, File, Body
from fastapi.middleware.cors import CORSMiddleware
import shutil
import os
import uuid

from app.inference import load_q_table, redesign_process, redesign_target_process
from app.target_schema_parser import SubprocessNotFoundError, CircularSubprocessError

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

q_table = load_q_table()

TARGET_SCHEMA_MODEL_PATH = "data/trained_q_table_target_schema.pkl"
target_schema_q_table = (
    load_q_table(TARGET_SCHEMA_MODEL_PATH) if os.path.exists(TARGET_SCHEMA_MODEL_PATH) else None
)

UPLOAD_DIR = "data/uploads"
PROCESSES_DIR = "data/processes"
os.makedirs(UPLOAD_DIR, exist_ok=True)
os.makedirs(PROCESSES_DIR, exist_ok=True)


@app.get("/")
def read_root():
    return {"message": "BPM Redesign Engine is running"}


@app.post("/redesign")
async def redesign(file: UploadFile = File(...)):
    temp_filename = f"{uuid.uuid4()}.bpmn"
    temp_path = os.path.join(UPLOAD_DIR, temp_filename)

    with open(temp_path, "wb") as buffer:
        shutil.copyfileobj(file.file, buffer)

    try:
        result = redesign_process(temp_path, q_table)
        return result
    except Exception as e:
        return {"error": str(e)}
    finally:
        if os.path.exists(temp_path):
            os.remove(temp_path)


@app.post("/redesign/process")
async def redesign_process_json(body: dict = Body(...)):
    """Accepts a process in the SaaS's own relational JSON schema. Two request shapes
    are supported:

    1. Bundle shape (used by the live-fetching frontend): {"process": {...},
       "subprocesses": {"<child_process_id>": {...}, ...}} -- every child_process_id
       the main process references (recursively) is pre-fetched by the caller and
       bundled here, so no backend API credentials are needed for subprocess resolution.
    2. Flat shape (local dev / testing): the process dict directly, matching
       processes/<id>.json -- subprocess references fall back to looking up
       <PROCESSES_DIR>/<id>.json on disk.
    """
    if target_schema_q_table is None:
        return {"error": "Target-schema model is not trained yet (missing trained_q_table_target_schema.pkl)."}

    if "process" in body and "subprocesses" in body:
        data = body["process"]
        subprocess_source = {int(k): v for k, v in body["subprocesses"].items()}
    else:
        data = body
        subprocess_source = PROCESSES_DIR

    try:
        result = redesign_target_process(data, subprocess_source, target_schema_q_table)
        return result
    except SubprocessNotFoundError as e:
        return {"error": str(e)}
    except CircularSubprocessError as e:
        return {"error": str(e)}
    except Exception as e:
        return {"error": str(e)}