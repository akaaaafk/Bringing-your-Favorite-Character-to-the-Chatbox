"""
Modal deployment for the Movie Persona Chat FastAPI backend.

Deploy:
    modal deploy deploy/modal.py

Dev (hot reload URL):
    modal serve deploy/modal.py

Requires: `modal token new` once (browser login).
"""
from __future__ import annotations

from pathlib import Path

import modal

ROOT = Path(__file__).resolve().parent.parent

app = modal.App("movie-persona-api")

# Persist Hugging Face downloads so cold starts don't re-fetch Qwen every time.
hf_cache = modal.Volume.from_name("movie-persona-hf-cache", create_if_missing=True)

image = (
    modal.Image.debian_slim(python_version="3.12")
    .pip_install(
        "torch",
        index_url="https://download.pytorch.org/whl/cpu",
    )
    .pip_install_from_pyproject(str(ROOT / "pyproject.toml"))
    .env(
        {
            "PRELOAD_PIPELINE": "1",
            "MOVIE_PERSONA_ROOT": "/app",
            "PYTHONPATH": "/app/src",
            "HF_HOME": "/cache/hf",
            "HF_HUB_CACHE": "/cache/hf",
            "TRANSFORMERS_CACHE": "/cache/hf",
        }
    )
    .add_local_dir(str(ROOT / "src"), remote_path="/app/src")
    .add_local_dir(str(ROOT / "models"), remote_path="/app/models")
    .add_local_dir(str(ROOT / "config"), remote_path="/app/config")
)


@app.function(
    image=image,
    memory=16384,
    timeout=600,
    # Keep one container warm so chats don't pay full cold-start each time.
    min_containers=1,
    # Modal max idle window is 20 minutes.
    scaledown_window=20 * 60,
    volumes={"/cache/hf": hf_cache},
)
@modal.concurrent(max_inputs=4)
@modal.asgi_app()
def fastapi_app():
    import sys

    sys.path.insert(0, "/app/src")
    from movie_persona.api import app as web_app

    return web_app
