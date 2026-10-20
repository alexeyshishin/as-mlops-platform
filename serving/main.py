import json
import logging
import sys
import time
from contextlib import asynccontextmanager
from datetime import datetime, timezone

from fastapi import FastAPI, HTTPException, Response
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

import history
from model import model

logging.basicConfig(stream=sys.stdout, level=logging.INFO)
logger = logging.getLogger("serving")

with open("intent_actions.json") as f:
    ACTION_BY_INTENT = json.load(f)["actions"]


@asynccontextmanager
async def lifespan(app: FastAPI):
    try:
        model.load()
    except Exception:
        logger.exception("model load failed, staying not-ready")
    yield


app = FastAPI(lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["https://app.alexshishin.ru"],
    allow_methods=["GET", "POST", "DELETE"],
    allow_headers=["Content-Type"],
    allow_credentials=False,
)


class HistoryTurn(BaseModel):
    role: str = "user"
    content: str


class ClassifyRequest(BaseModel):
    session_id: str | None = None
    user_id: str | None = None
    history: list[HistoryTurn] | None = None
    text: str


@app.get("/health")
def health():
    return {"status": "ok"}


@app.get("/ready")
def ready(response: Response):
    if not model.loaded:
        response.status_code = 503
        return {"status": "not-ready"}
    return {"status": "ready"}


@app.post("/classify")
def classify(request: ClassifyRequest):
    start = time.monotonic()

    try:
        history.append(request.session_id, request.text, request.user_id)

        history_payload = [turn.model_dump() for turn in request.history] if request.history else []
        result_list = model.predict(request.text, history_payload)
        result = result_list[0] if isinstance(result_list, list) and result_list else result_list

        intent = result.get("intent") if isinstance(result, dict) else None
        confidence = result.get("confidence") if isinstance(result, dict) else None
        route = ACTION_BY_INTENT.get(intent) if intent else None
        history.track_intent(request.session_id, intent)

        response = {k: v for k, v in {
            "intent": intent,
            "confidence": confidence,
            "needs_clarification": result.get("needs_clarification") if isinstance(result, dict) else None,
            "route": route,
        }.items() if v is not None}

        latency_ms = (time.monotonic() - start) * 1000
        log_line = {
            "intent": intent,
            "confidence": confidence,
            "model_version": model.model_version,
            "dataset_version": model.dataset_version,
            "ts": datetime.now(timezone.utc).isoformat(),
            "latency_ms": round(latency_ms, 2),
        }
        logger.info(json.dumps(log_line))
    except Exception:
        logger.exception("classify failed")
        raise HTTPException(status_code=500, detail="classification failed")

    return response


@app.get("/dialogs")
def list_dialogs(user_id: str | None = None):
    return {"dialogs": history.list_recent_dialogs(limit=20, user_id=user_id)}


@app.get("/dialogs/{session_id}")
def get_dialog(session_id: str):
    meta = history.get_dialog_meta(session_id)
    if meta is None:
        raise HTTPException(status_code=404, detail="dialog not found")
    return meta


@app.get("/dialogs/{session_id}/turns")
def get_dialog_turns(session_id: str):
    turns = history.get_dialog_turns(session_id)
    if turns is None:
        raise HTTPException(status_code=404, detail="dialog not found")
    return {"session_id": session_id, "turns": turns}


@app.delete("/dialogs/{session_id}", status_code=204)
def delete_dialog(session_id: str, user_id: str | None = None):
    deleted = history.delete_dialog(session_id, user_id=user_id)
    if not deleted:
        raise HTTPException(status_code=404, detail="dialog not found")
    return Response(status_code=204)
