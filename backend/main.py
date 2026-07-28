from fastapi import FastAPI, Body
from fastapi.middleware.cors import CORSMiddleware
import os

from app.inference import load_q_table, redesign_target_process
from app.target_schema_parser import SubprocessNotFoundError, CircularSubprocessError

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

TARGET_SCHEMA_MODEL_PATH = "data/trained_q_table_target_schema.pkl"
target_schema_q_table = (
    load_q_table(TARGET_SCHEMA_MODEL_PATH) if os.path.exists(TARGET_SCHEMA_MODEL_PATH) else None
)

PROCESSES_DIR = "data/processes"
os.makedirs(PROCESSES_DIR, exist_ok=True)


@app.get("/")
def read_root():
    return {"message": "BPM Redesign Engine is running"}


@app.post("/redesign/process")
async def redesign_process_json(body: dict = Body(...)):
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
