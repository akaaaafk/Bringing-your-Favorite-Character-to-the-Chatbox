# Movie Persona Chat API
#
# CPU (portable):
#   docker build -t movie-persona-api .
#
# NVIDIA GPU (requires NVIDIA Container Toolkit on the host):
#   docker build --build-arg TORCH_INDEX_URL=https://download.pytorch.org/whl/cu130 \
#     -t movie-persona-api:cuda .
FROM node:20-alpine AS web-build

WORKDIR /web
COPY web/package.json web/package-lock.json ./
RUN npm ci
COPY web/ ./
RUN npm run build


FROM python:3.12-slim

ARG TORCH_INDEX_URL=https://download.pytorch.org/whl/cpu

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    HF_HOME=/home/app/.cache/huggingface \
    HF_HUB_CACHE=/home/app/.cache/huggingface/hub \
    PRELOAD_PIPELINE=0 \
    PORT=8000

WORKDIR /app

RUN python -m pip install --no-cache-dir --upgrade pip \
    && python -m pip install --no-cache-dir torch --index-url "${TORCH_INDEX_URL}"

COPY requirements-space.txt .
RUN python -m pip install --no-cache-dir -r requirements-space.txt

COPY api_server.py inference.py tts_edge.py ./
COPY persona_classifier ./persona_classifier
COPY data/processed/selected_characters.json ./data/processed/selected_characters.json
COPY models ./models
COPY --from=web-build /web/dist ./web/dist

# Fail during the build instead of silently using the classifier stub or the
# untuned base generator. These files are intentionally required artifacts.
RUN test -f models/classifier/model.safetensors \
    && test -f models/generator/adapter_model.safetensors

RUN useradd --create-home app \
    && mkdir -p "${HF_HOME}" \
    && chown -R app:app /app /home/app

USER app

EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=5s --start-period=30s --retries=3 \
    CMD python -c "import os, urllib.request; urllib.request.urlopen('http://127.0.0.1:' + os.environ.get('PORT', '8000') + '/api/health', timeout=4)"

CMD ["sh", "-c", "exec uvicorn api_server:app --host 0.0.0.0 --port \"${PORT}\""]
