"""
Persona classifier inference interface.

Phase 3 (reranking) should only ever import from this file:
    from persona_classifier import predict_persona, predict_persona_batch

Auto-detects a trained checkpoint at MODEL_DIR. If found, uses the real
model. Otherwise falls back to a stub that returns correctly-shaped fake
predictions, so downstream code can be built/tested before training finishes.
"""

from pathlib import Path
import hashlib
import json

MODEL_DIR = Path(__file__).resolve().parent.parent / "models" / "persona_classifier"
SELECTED_CHARACTERS_PATH = (
    Path(__file__).resolve().parent.parent / "data" / "processed" / "selected_characters.json"
)

_STUB_PERSONA_TAGS = ["dante", "alvy", "ace", "jack", "gittes"]


def _load_persona_tags() -> list[str]:
    if SELECTED_CHARACTERS_PATH.exists():
        with open(SELECTED_CHARACTERS_PATH) as f:
            characters = json.load(f)
        return [c["persona_tag"] for c in characters]
    return _STUB_PERSONA_TAGS


PERSONA_TAGS: list[str] = _load_persona_tags()

_USING_REAL_MODEL = MODEL_DIR.exists() and any(MODEL_DIR.iterdir())

if _USING_REAL_MODEL:
    import torch
    from transformers import AutoTokenizer, AutoModelForSequenceClassification

    _tokenizer = AutoTokenizer.from_pretrained(MODEL_DIR)
    _model = AutoModelForSequenceClassification.from_pretrained(MODEL_DIR)
    _model.eval()
    PERSONA_TAGS = [_model.config.id2label[i] for i in range(len(_model.config.id2label))]


def _stub_score(text: str, tag: str) -> float:
    h = hashlib.sha256(f"{text}::{tag}".encode()).hexdigest()
    return int(h[:8], 16) / 0xFFFFFFFF


def predict_persona_batch(texts: list[str]) -> list[dict[str, float]]:
    if _USING_REAL_MODEL:
        inputs = _tokenizer(texts, return_tensors="pt", padding=True, truncation=True)
        with torch.no_grad():
            logits = _model(**inputs).logits
            probs = torch.softmax(logits, dim=-1)
        return [
            {PERSONA_TAGS[i]: float(p[i]) for i in range(len(PERSONA_TAGS))}
            for p in probs
        ]

    results = []
    for text in texts:
        raw_scores = {tag: _stub_score(text, tag) for tag in PERSONA_TAGS}
        total = sum(raw_scores.values())
        results.append({tag: score / total for tag, score in raw_scores.items()})
    return results


def predict_persona(text: str) -> dict[str, float]:
    return predict_persona_batch([text])[0]
