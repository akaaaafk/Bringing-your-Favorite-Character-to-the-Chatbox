"""
REST API for the Movie Persona Chat React UI.

Run (from final_project/):
    pip install fastapi uvicorn
    uvicorn api_server:app --reload --port 8000

Then in another terminal:
    cd web && npm run dev
"""
from __future__ import annotations

import argparse
from typing import Any

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

from config import BEAM_N, CHARACTERS

app = FastAPI(title="Movie Persona Chat API", version="1.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

_pipeline: Any = None
_load_error: str | None = None


class ChatRequest(BaseModel):
    message: str = Field(..., min_length=1)
    character: str
    n_candidates: int = Field(default=BEAM_N, ge=1, le=8)
    use_rerank: bool = True


class ChatResponse(BaseModel):
    reply: str
    persona_score: float | None = None
    n_candidates: int = 1
    mode: str = "live"


def get_pipeline():
    global _pipeline, _load_error
    if _pipeline is not None:
        return _pipeline
    if _load_error:
        raise RuntimeError(_load_error)
    try:
        from inference import PersonaPipeline

        _pipeline = PersonaPipeline()
        return _pipeline
    except Exception as e:
        _load_error = str(e)
        raise


@app.get("/api/health")
def health():
    return {
        "ok": True,
        "pipeline_loaded": _pipeline is not None,
        "load_error": _load_error,
        "characters": CHARACTERS,
    }


@app.get("/api/characters")
def list_characters():
    return {"characters": CHARACTERS}


@app.post("/api/chat", response_model=ChatResponse)
def chat(req: ChatRequest):
    char = req.character.strip().upper()

    try:
        pipe = get_pipeline()
    except Exception as e:
        raise HTTPException(
            status_code=503,
            detail=f"Models not available: {e}. Train models or use demo mode in the UI.",
        ) from e

    try:
        if req.use_rerank:
            results = pipe.chat(
                req.message, char, n=req.n_candidates, return_all=True
            )
            best = results[0]
            return ChatResponse(
                reply=best.text,
                persona_score=float(best.persona_score),
                n_candidates=len(results),
                mode="live",
            )
        reply = pipe.plain_generate(req.message, char)
        return ChatResponse(
            reply=reply,
            persona_score=None,
            n_candidates=1,
            mode="live",
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e)) from e


if __name__ == "__main__":
    import uvicorn

    parser = argparse.ArgumentParser()
    parser.add_argument("--port", type=int, default=8000)
    args = parser.parse_args()
    uvicorn.run("api_server:app", host="127.0.0.1", port=args.port, reload=True)
