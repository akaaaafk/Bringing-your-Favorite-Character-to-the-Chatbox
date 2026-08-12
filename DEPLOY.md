# Deploy: Vercel (frontend) + Modal (API)

> **Note (2026):** Hugging Face free accounts can no longer host Gradio/Docker
> Spaces on `cpu-basic` without PRO. This project uses **Modal** for the API
> instead. The `Dockerfile` / `README_SPACE.md` remain if you later get HF PRO.

## Architecture

```
Browser  →  Vercel (Vite/React static)
                │
                │  VITE_API_BASE=https://<your-modal-url>.modal.run
                ▼
         Modal (FastAPI + LoRA + classifier + Edge TTS)
```

Locally, leave `VITE_API_BASE` empty so Vite still proxies `/api` → `:8000`.

## 1. API — Modal

```bash
cd final_project
# activate your venv first
pip install modal
modal token new          # browser login, once
modal deploy modal_app.py
```

Modal prints a public URL like:

`https://akaaafk--movie-persona-api-fastapi-app.modal.run`

Smoke test:

```bash
curl https://<that-url>/api/health
```

Optional: set Modal secret / env `CORS_ORIGINS` to your custom Vercel domain.
`*.vercel.app` is already allowed in code.

CPU cold start will download Qwen2.5-1.5B on first boot — first request can take a few minutes.
Subsequent boots reuse a Modal Volume cache. `min_containers=1` keeps one container warm
(costs idle compute; set to `0` in `modal_app.py` if you want scale-to-zero).

## 2. Frontend — Vercel

```bash
cd web
npx vercel login
npx vercel link
```

Environment variables (Production **and** Preview):

| Name | Value |
|------|--------|
| `VITE_API_BASE` | `https://<your-modal-url>.modal.run` |

Then:

```bash
npx vercel --prod
```

Dashboard alternative: import the GitHub repo, set **Root Directory** to `final_project/web`, Framework Vite, same env var.

## 3. Wire check

1. Open the Vercel URL  
2. Unmute TTS, send a chat turn  
3. In DevTools → Network, `/api/chat` and `/api/tts` should hit `*.modal.run`, not the Vercel host  

## HF Spaces (optional, needs PRO)

If you subscribe to HF PRO later:

```bash
hf repo create <user>/movie-persona-api --repo-type space --space_sdk docker --exist-ok
# upload Dockerfile + code + models (see older notes / README_SPACE.md)
```

Set Space env `CORS_ORIGINS` to your Vercel origin.
