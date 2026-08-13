"""
FastAPI bridge for the React Movie Persona Chat UI.

Run (from repo root):
    movie-persona-api
    # or: uvicorn movie_persona.api:app --reload --port 8000

Then in another terminal:
    cd web && npm run dev

Frontend proxies /api → http://127.0.0.1:8000
"""
from __future__ import annotations

import argparse
import json
import os
from functools import lru_cache
from typing import Any, Literal

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field, field_validator

from .paths import PERSONAS_PATH, WEB_DIST

# Fallback if the checked-in persona manifest is missing.
DEFAULT_TAGS = ["jack", "bateman", "alvy", "ben", "erin"]
BEAM_N = 3  # default Best-of-N candidates per prompt

# Comma-separated origins for the React UI (local Vite + custom domains).
# Vercel preview/prod URLs are also matched via allow_origin_regex below.
_DEFAULT_CORS = "http://localhost:5173,http://127.0.0.1:5173"


def _cors_origins() -> list[str]:
    raw = os.environ.get("CORS_ORIGINS", _DEFAULT_CORS)
    return [o.strip() for o in raw.split(",") if o.strip()]


app = FastAPI(
    title="Movie Persona Chat API",
    version="1.0.0",
    description="Best-of-N persona chat for the React frontend.",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=_cors_origins(),
    allow_origin_regex=r"https://.*\.(vercel\.app|modal\.run)",
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

_pipeline: Any = None
_load_error: str | None = None


# ── Characters ────────────────────────────────────────────────────────────────

@lru_cache(maxsize=1)
def load_characters() -> list[dict]:
    """Return selected-character records (persona_tag, name, film, …)."""
    if PERSONAS_PATH.exists():
        return json.loads(PERSONAS_PATH.read_text(encoding="utf-8"))
    return [
        {
            "persona_tag": tag,
            "character_name": tag.upper(),
            "movie_title": "",
        }
        for tag in DEFAULT_TAGS
    ]


def persona_tags() -> list[str]:
    return [c["persona_tag"] for c in load_characters()]


def normalize_character(raw: str) -> str:
    """Map web IDs like 'ALVY' / 'Alvy' → inference tag 'alvy'."""
    tag = raw.strip().lower().replace(" ", "_")
    tags = persona_tags()
    if tag not in tags:
        raise HTTPException(
            status_code=400,
            detail=f"Unknown character '{raw}'. Available: {tags}",
        )
    return tag


# ── Schemas ───────────────────────────────────────────────────────────────────

class HistoryTurn(BaseModel):
    role: Literal["user", "assistant"]
    text: str = Field(..., min_length=1, max_length=4000)

    @field_validator("text")
    @classmethod
    def strip_text(cls, v: str) -> str:
        t = v.strip()
        if not t:
            raise ValueError("history text must be non-empty")
        return t


class ChatRequest(BaseModel):
    message: str = Field(..., min_length=1)
    character: str = Field(
        ...,
        description="Persona tag or display id, e.g. 'alvy' or 'ALVY'",
    )
    n_candidates: int = Field(default=BEAM_N, ge=1, le=8)
    use_rerank: bool = True
    history: list[HistoryTurn] = Field(
        default_factory=list,
        max_length=20,
        description="Prior user/assistant turns (oldest first), excluding message",
    )


class ChatResponse(BaseModel):
    reply: str
    persona_score: float | None = None
    n_candidates: int = 1
    mode: str = "live"


class CharacterOut(BaseModel):
    persona_tag: str
    character_name: str
    movie_title: str = ""
    line_count: int | None = None


class TtsRequest(BaseModel):
    text: str = Field(..., min_length=1, max_length=4000)
    character: str = Field(
        ...,
        description="Persona tag or display id, e.g. 'alvy' or 'ALVY'",
    )

    @field_validator("text")
    @classmethod
    def strip_tts_text(cls, v: str) -> str:
        t = v.strip()
        if not t:
            raise ValueError("text must be non-empty")
        return t


# ── Pipeline (lazy) ───────────────────────────────────────────────────────────

def get_pipeline():
    """Load PersonaPipeline once; surface load failures as 503."""
    global _pipeline, _load_error
    if _pipeline is not None:
        return _pipeline
    if _load_error is not None:
        raise RuntimeError(_load_error)
    try:
        from .pipeline import PersonaPipeline

        _pipeline = PersonaPipeline()
        return _pipeline
    except Exception as e:
        _load_error = str(e)
        raise


@app.on_event("startup")
def preload_pipeline() -> None:
    """Warm models on Space boot so the first chat is not a cold miss."""
    flag = os.environ.get("PRELOAD_PIPELINE", "").strip().lower()
    if flag not in {"1", "true", "yes"}:
        return
    try:
        get_pipeline()
        print("[startup] pipeline preloaded")
    except Exception as e:
        print(f"[startup] pipeline preload failed: {e}")


# ── Routes ────────────────────────────────────────────────────────────────────

@app.get("/api/health")
def health():
    edge_ok = False
    try:
        import edge_tts  # noqa: F401

        edge_ok = True
    except Exception:
        edge_ok = False
    return {
        "ok": True,
        "pipeline_loaded": _pipeline is not None,
        "load_error": _load_error,
        "characters": persona_tags(),
        "tts": "edge" if edge_ok else None,
    }


@app.get("/api/characters", response_model=list[CharacterOut])
def list_characters():
    out: list[CharacterOut] = []
    for c in load_characters():
        out.append(
            CharacterOut(
                persona_tag=c["persona_tag"],
                character_name=c.get("character_name", c["persona_tag"].upper()),
                movie_title=c.get("movie_title", ""),
                line_count=c.get("line_count"),
            )
        )
    return out


@app.post("/api/chat", response_model=ChatResponse)
def chat(req: ChatRequest):
    tag = normalize_character(req.character)

    try:
        pipe = get_pipeline()
    except Exception as e:
        raise HTTPException(
            status_code=503,
            detail=(
                f"Models not available: {e}. "
                "Train/load generator + classifier, or use demo mode in the UI."
            ),
        ) from e

    try:
        history = [{"role": t.role, "text": t.text} for t in req.history]
        if req.use_rerank:
            results = pipe.chat(
                req.message,
                tag,
                n=req.n_candidates,
                return_all=True,
                history=history,
            )
            best = results[0]
            return ChatResponse(
                reply=best.text,
                persona_score=float(best.persona_score),
                n_candidates=len(results),
                mode="live",
            )

        reply = pipe.plain_generate(req.message, tag, history=history)
        return ChatResponse(
            reply=reply,
            persona_score=None,
            n_candidates=1,
            mode="live",
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e)) from e


@app.post("/api/tts")
async def tts(req: TtsRequest):
    """Stream Edge neural TTS as audio/mpeg (chunked) for low time-to-first-audio."""
    tag = normalize_character(req.character)
    try:
        from .speech import iter_mp3_chunks

        # Probe first chunk so we can 4xx/5xx before headers are committed.
        stream = iter_mp3_chunks(req.text, tag)
        first = await stream.__anext__()

        async def body():
            yield first
            async for piece in stream:
                yield piece

        return StreamingResponse(
            body(),
            media_type="audio/mpeg",
            headers={
                "Cache-Control": "no-store",
                "X-Accel-Buffering": "no",
            },
        )
    except StopAsyncIteration:
        raise HTTPException(status_code=503, detail="TTS unavailable: empty audio")
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e
    except Exception as e:
        raise HTTPException(
            status_code=503,
            detail=f"TTS unavailable: {e}",
        ) from e


# Serve the production React build when present (Docker). In local development,
# Vite serves the UI separately and this fallback remains an API landing page.
if WEB_DIST.exists():
    app.mount("/", StaticFiles(directory=str(WEB_DIST), html=True), name="web")
else:
    @app.get("/")
    def root():
        return {
            "service": "Movie Persona Chat API",
            "docs": "/docs",
            "health": "/api/health",
            "characters": "/api/characters",
            "chat": "POST /api/chat",
        }


# ── Entrypoint ────────────────────────────────────────────────────────────────

def main() -> None:
    import uvicorn

    parser = argparse.ArgumentParser()
    parser.add_argument("--port", type=int, default=8000)
    parser.add_argument("--host", default="127.0.0.1")
    args = parser.parse_args()
    uvicorn.run(
        "movie_persona.api:app",
        host=args.host,
        port=args.port,
        reload=True,
    )


if __name__ == "__main__":
    main()
