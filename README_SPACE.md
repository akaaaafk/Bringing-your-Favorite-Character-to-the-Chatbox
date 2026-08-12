---
title: Movie Persona Chat API
emoji: 🎬
colorFrom: yellow
colorTo: gray
sdk: docker
pinned: false
license: mit
short_description: FastAPI Best-of-N persona chat + Edge TTS
startup_duration_timeout: 1h
app_port: 7860
---

# Movie Persona Chat API (HF Space Dockerfile)

> Free HF accounts currently need **PRO** for Docker Spaces. Prefer **Modal**
> (`modal_app.py`) unless you have PRO — see `DEPLOY.md`.

FastAPI backend for the React Movie Persona Chat UI:

- LoRA Qwen2.5-1.5B persona generator + RoBERTa reranker
- Free Edge neural TTS (`/api/tts`)
- Conversation history + name grounding

## Endpoints

- `GET /api/health`
- `GET /api/characters`
- `POST /api/chat`
- `POST /api/tts`
