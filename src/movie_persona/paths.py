"""Canonical filesystem locations shared by runtime modules."""
import os
from pathlib import Path

PROJECT_ROOT = Path(
    os.environ.get("MOVIE_PERSONA_ROOT", Path(__file__).resolve().parents[2])
).resolve()
CONFIG_DIR = PROJECT_ROOT / "config"
MODELS_DIR = PROJECT_ROOT / "models"
WEB_DIST = PROJECT_ROOT / "web" / "dist"
PERSONAS_PATH = CONFIG_DIR / "personas.json"
