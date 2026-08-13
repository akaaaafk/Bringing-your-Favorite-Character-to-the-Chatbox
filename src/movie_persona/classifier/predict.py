"""
Persona classifier inference interface.

Reranking code should import from this module's package interface:
    from movie_persona.classifier import predict_persona, predict_persona_batch

Auto-detects a trained checkpoint at models/classifier/. If found, uses the
real model. Otherwise falls back to a stub that returns correctly-shaped fake
predictions, so downstream code can be built/tested before training finishes.
"""

import hashlib
import json

from ..paths import MODELS_DIR, PERSONAS_PATH

MODEL_DIR = MODELS_DIR / "classifier"

_STUB_PERSONA_TAGS = ["alvy", "bateman", "ben", "erin", "jack"]


def _load_persona_tags() -> list[str]:
    if PERSONAS_PATH.exists():
        with open(PERSONAS_PATH) as f:
            characters = json.load(f)
        return [c["persona_tag"] for c in characters]
    return list(_STUB_PERSONA_TAGS)


PERSONA_TAGS: list[str] = _load_persona_tags()

_tokenizer = None
_model = None
_USING_REAL_MODEL = (MODEL_DIR / "config.json").exists()

if _USING_REAL_MODEL:
    import torch
    from transformers import AutoModelForSequenceClassification, AutoTokenizer

    try:
        _tokenizer = AutoTokenizer.from_pretrained(str(MODEL_DIR))
        _model = AutoModelForSequenceClassification.from_pretrained(str(MODEL_DIR))
        _model.eval()
        PERSONA_TAGS = [
            _model.config.id2label[i] for i in range(len(_model.config.id2label))
        ]
        print(f"[persona_classifier] loaded {MODEL_DIR} labels={PERSONA_TAGS}")
    except Exception as e:
        print(f"[persona_classifier] failed to load {MODEL_DIR}: {e}; using stub")
        _USING_REAL_MODEL = False
        _tokenizer = None
        _model = None


def _stub_score(text: str, tag: str) -> float:
    h = hashlib.sha256(f"{text}::{tag}".encode()).hexdigest()
    return int(h[:8], 16) / 0xFFFFFFFF


def predict_persona_batch(texts: list[str]) -> list[dict[str, float]]:
    if _USING_REAL_MODEL:
        import torch

        inputs = _tokenizer(
            texts,
            return_tensors="pt",
            padding=True,
            truncation=True,
            max_length=128,
        )
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
        total = sum(raw_scores.values()) or 1.0
        results.append({tag: score / total for tag, score in raw_scores.items()})
    return results


def predict_persona(text: str) -> dict[str, float]:
    return predict_persona_batch([text])[0]
