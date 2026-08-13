# Archived: Hugging Face Docker Spaces

This deployment path is not maintained. Free Hugging Face accounts currently
require PRO for Docker Spaces, so the live project uses Modal for FastAPI and
Vercel for the React client. See `docs/deployment/README.md`.

The former Space metadata was:

```yaml
title: Movie Persona Chat API
sdk: docker
license: mit
startup_duration_timeout: 1h
app_port: 7860
```

The portable `deploy/docker/Dockerfile` defaults to port `8000`. Anyone
reviving the Space must set `PORT=7860`, verify the current Hugging Face Docker
requirements, provide both model artifacts, and configure `CORS_ORIGINS` for
the frontend origin.

Supported endpoints:

- `GET /api/health`
- `GET /api/characters`
- `POST /api/chat`
- `POST /api/tts`
