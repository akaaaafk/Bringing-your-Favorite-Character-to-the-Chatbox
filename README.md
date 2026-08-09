# Integrate Personas from Famous Movies into LLMs Chatbox

Converse with fine-tuned movie-character personas. A LoRA generator produces candidate replies; a RoBERTa classifier scores persona consistency and picks the best (Best-of-N).

## How it works

```
User selects character + prompt
            │
            ▼
   LoRA persona generator ──► N candidate replies
            │                        │
            │              RoBERTa persona classifier
            │                        │
            └──────── Best-of-N ─────┘
                         │
                   Final reply → Gradio chat
```

1. **Persona classifier** — fine-tune `roberta-base` over 5 characters (real lines + Claude hard-negative rewrites).
2. **Persona generator** — LoRA-fine-tune a small chat LM conditioned on a character tag.
3. **Reranking** — generate 3 completions; classifier scores each; return the highest-scoring one.

## Dataset

[Cornell Movie-Dialogs Corpus](http://www.cs.cornell.edu/~cristian/Cornell_Movie-Dialogs_Corpus.html) — 220k+ conversations across 617 movies. Downloaded by `data_pipeline.py`.

| Character | Style |
|---|---|
| HANNIBAL LECTER | Precise, erudite, theatrically menacing |
| CLARICE | Earnest, formal-professional |
| JOKER | Chaotic, clipped, darkly comic |
| FORREST | Simple, literal, heartfelt |
| JAMES BOND | Suave, dry-witted, controlled |

HANNIBAL LECTER and CLARICE are a **near-pair** (both intelligent / formal) to stress-test the classifier.

Hard negatives: Claude rewrites character-A lines in character-B’s style so the classifier must learn stylistic signal, not topic.

## Research questions

1. How well does the classifier distinguish speech styles? Which features drive correct classification?
2. Which characters are most confused — and does that match intuition about who “sounds alike”?
3. Does Best-of-N reranking improve persona-consistency vs plain LoRA generation?

## Project layout

```
.
├── app.py                       # Gradio chat UI
├── api_server.py                # FastAPI for React UI
├── config.py                    # Characters, paths, hyperparameters
├── data_pipeline.py             # Download Cornell → HF Dataset splits
├── generate_hard_negatives.py   # Claude hard-negative synthesis
├── train_classifier.py          # RoBERTa multi-class fine-tune
├── evaluate_classifier.py       # Report, confusion matrix, token analysis
├── train_generator.py           # LoRA SFT (TRL)
├── inference.py                 # Best-of-N pipeline
├── requirements.txt
├── design-system/               # UI design tokens
├── web/                         # React + Tailwind cinematic chat UI
├── data/
│   ├── raw/                     # Cornell zip (gitignored)
│   └── processed/               # splits + meta.json (gitignored)
├── models/
│   ├── classifier/              # Fine-tuned RoBERTa (gitignored)
│   └── generator/               # LoRA / merged generator (gitignored)
└── results/                     # Metrics & plots (gitignored)
```

## Pipeline

```bash
pip install -r requirements.txt

python data_pipeline.py
python data_pipeline.py --list-top 30          # inspect line counts

# Optional hard negatives (needs ANTHROPIC_API_KEY)
python generate_hard_negatives.py

python train_classifier.py
python evaluate_classifier.py

python train_generator.py

python app.py
# python inference.py --character "JOKER" --prompt "Why so serious?" --all
```

### React web UI

```bash
# Terminal 1 — API (loads trained models; UI uses demo replies if API is down)
python api_server.py

# Terminal 2 — frontend
cd web
npm install
npm run dev
```

Open http://localhost:5173

Edit `CHARACTERS` in `config.py` to swap personas, then re-run from `data_pipeline.py`.

## License

Code in this repository is for coursework / research use. Cornell Movie-Dialogs Corpus remains under its original terms.
