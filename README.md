# Movie Persona Chat

<!-- markdownlint-disable MD033 -->
<div align="center">

**Five film voices. Your cue.**

A React and FastAPI chat application powered by a LoRA-tuned Qwen generator,
a RoBERTa persona classifier, and optional Best-of-N reranking.

[![Live Demo](https://img.shields.io/badge/Live_Demo-Enter_the_projection_room-E9A83B?style=for-the-badge&logo=vercel&logoColor=1F1710)](https://web-nine-bice-uqkujgnxqk.vercel.app)
[![API](https://img.shields.io/badge/FastAPI-Live-3D8C78?style=for-the-badge&logo=fastapi&logoColor=white)](https://akaaaafk--movie-persona-api-fastapi-app.modal.run/docs)
[![Weights](https://img.shields.io/badge/Hugging_Face-Model_artifacts-FFD21E?style=for-the-badge&logo=huggingface&logoColor=111111)](https://huggingface.co/datasets/akaaafk/Bringing-your-Favorite-Character-to-the-Chatbox/tree/main/models)

</div>
<!-- markdownlint-enable MD033 -->

![Movie Persona Chat projection-room landing page](docs/web-preview.png)

> Columbia COMS 5910 Deep Learning — Summer 2026 final project

## Find your way around

The repository is divided by purpose. You should only need one area for most
tasks:

```text
final_project/
├── web/                       # React user interface
├── src/movie_persona/         # production Python backend
│   ├── api.py                 # FastAPI routes
│   ├── pipeline.py            # generation, memory, grounding, reranking
│   ├── speech.py              # Edge TTS
│   ├── paths.py               # shared filesystem locations
│   └── classifier/            # persona classifier inference
├── experiments/
│   ├── scripts/               # data prep, training, and evaluation
│   └── notebooks/             # exploratory notebooks
├── deploy/
│   ├── modal.py               # hosted API deployment
│   └── docker/Dockerfile      # portable full-stack container
├── tools/preflight.py         # artifact and deployment checks
├── config/                    # canonical persona metadata
├── data/                      # downloaded and generated datasets
├── models/                    # local weights plus tracked manifest
├── results/published/         # curated report evidence
├── docs/                      # interfaces and deployment guides
└── pyproject.toml             # Python package and dependencies
```

- To change the interface, work in `web/`.
- To change production inference or API behavior, work in
  `src/movie_persona/`.
- To reproduce training or evaluation, use `experiments/`.
- To publish or containerize the app, use `deploy/` and
  `docs/deployment/`.
- Do not commit generated datasets or weights. Their expected locations and
  checksums are recorded in `models/manifest.json`.

## How it works

```text
message + recent history + persona
                |
                v
       Qwen2.5-1.5B + LoRA
                |
         candidate replies
                |
                v
       RoBERTa persona scorer
                |
       optional Best-of-N pick
                |
                v
        React UI + Edge TTS
```

The app supports Jack (*Fight Club*), Patrick Bateman (*American Psycho*),
Alvy Singer (*Annie Hall*), Benjamin Braddock (*The Graduate*), and Erin
Brockovich (*Erin Brockovich*). `config/personas.json` is the canonical
metadata source.

## Local setup

Requirements:

- Python 3.11 or 3.12
- Node.js 20+
- The two model artifacts listed below
- NVIDIA GPU recommended; CPU inference is supported but slow

From `final_project/`, create an environment and install the package:

```bash
python -m venv .venv
# Windows: .\.venv\Scripts\Activate.ps1
# macOS/Linux: source .venv/bin/activate
python -m pip install --upgrade pip
python -m pip install -e .
python tools/preflight.py --target local
```

For experiments, install the training dependencies:

```bash
python -m pip install -e ".[training]"
```

If needed, install the PyTorch build appropriate for your NVIDIA driver before
installing the package.

Start the API:

```bash
movie-persona-api
```

Start the client in a second terminal:

```bash
cd web
npm install
npm run dev
```

Open `http://localhost:5173`. Vite proxies `/api` to
`http://127.0.0.1:8000`. Direct command-line generation is also available:

```bash
movie-persona --character jack \
  --prompt "What do you think about modern life?" --n 3 --all
```

## Model artifacts

Running the finished app does not require retraining. It does require:

```text
models/classifier/model.safetensors
models/generator/adapter_model.safetensors
```

Download them from
[Hugging Face](https://huggingface.co/datasets/akaaafk/Bringing-your-Favorite-Character-to-the-Chatbox/tree/main/models):

```bash
hf download akaaafk/Bringing-your-Favorite-Character-to-the-Chatbox \
  --repo-type dataset --include "models/**" --local-dir .
```

The generator artifact is a LoRA adapter. Transformers downloads and caches
the `Qwen/Qwen2.5-1.5B-Instruct` base model on first use.

## Reproduce the experiments

Run all commands from `final_project/`:

```bash
# Data
python experiments/scripts/download_data.py
python experiments/scripts/preprocess.py

# Optional hard-negative synthesis; requires ANTHROPIC_API_KEY
python experiments/scripts/generate_hard_negatives.py

# Classifier
python experiments/scripts/train_classifier.py

# Generator
python experiments/scripts/build_training_pairs.py
python experiments/scripts/train_generator.py

# Best-of-N evaluation
python experiments/scripts/evaluate_bon_rerank.py --n 3 --seeds 42 43 44
```

The notebooks under `experiments/notebooks/` also assume the repository root
as their working directory. Generated datasets remain under `data/`; model
outputs remain under `models/`; curated evaluation outputs belong in
`results/published/`.

## Evaluation summary

The persona classifier reached 0.587 accuracy and 0.577 macro-F1. Best-of-N
was evaluated on 120 paired generations (5 personas × 8 prompts × 3 seeds,
`N=3`). Mean target-persona classifier probability rose from 0.213 to 0.422;
the independent local judge rose from 2.050 to 2.217 on a five-point scale.

The classifier result is partly circular because that classifier selects the
winner. The smaller independent gain does not establish a strong, reliable
improvement in persona consistency. Full outputs are in `results/published/`.

## API and deployment

The production ASGI target is `movie_persona.api:app`.

- `GET /api/health` — service and model-load status
- `GET /api/characters` — persona metadata
- `POST /api/chat` — generation with optional Best-of-N
- `POST /api/tts` — streamed MP3 speech

The public architecture uses Vercel for `web/` and Modal for the API. See
`docs/deployment/README.md` for the hosted procedure and
`docs/deployment/docker.md` for the portable container.

## Limitations and usage notes

- Best-of-N increases latency and compute with the number of candidates.
- The classifier has moderate held-out accuracy; its score is not a human
  preference guarantee.
- Identity questions use deterministic grounding rules.
- Edge TTS voices are synthetic and are not licensed actor voice likenesses.
- The Cornell Movie-Dialogs Corpus and character names remain subject to their
  original terms and rights holders. This project is intended for coursework
  and research.
