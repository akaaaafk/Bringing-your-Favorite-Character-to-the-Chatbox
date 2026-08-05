"""
Central configuration for the Movie Persona project.
Edit CHARACTERS to swap in different Cornell corpus characters.
"""
from pathlib import Path

# ── Paths ───────────────────────────────────────────────────────────────────
ROOT = Path(__file__).parent
DATA_DIR = ROOT / "data"
RAW_DIR = DATA_DIR / "raw"
PROCESSED_DIR = DATA_DIR / "processed"
NEGATIVES_FILE = DATA_DIR / "hard_negatives.jsonl"
CLASSIFIER_DIR = ROOT / "models" / "classifier"
GENERATOR_DIR = ROOT / "models" / "generator"
RESULTS_DIR = ROOT / "results"

for _d in [RAW_DIR, PROCESSED_DIR, CLASSIFIER_DIR, GENERATOR_DIR, RESULTS_DIR]:
    _d.mkdir(parents=True, exist_ok=True)

# Cornell corpus URL
CORPUS_URL = "http://www.cs.cornell.edu/~cristian/data/cornell_movie_dialogs_corpus.zip"

# ── Character selection ──────────────────────────────────────────────────────
# Five characters with distinctive, contrasting speech patterns.
# (character name as it appears in movie_characters_metadata.txt, upper-case)
# Near-pair for stress-test: HANNIBAL LECTER vs CLARICE — both intelligent
# and formal but very different power dynamics and vocabulary.
CHARACTERS = [
    "HANNIBAL LECTER",   # precise, erudite, theatrical
    "CLARICE",           # earnest, formal-professional
    "JOKER",             # chaotic, clipped, dark humour
    "FORREST",           # simple, repetitive, literal
    "JAMES BOND",        # suave, dry-wit, controlled
]
# Map to short label tokens used in prompts
CHARACTER_TAGS = {c: c.replace(" ", "_") for c in CHARACTERS}

# Minimum lines required to include a character
MIN_LINES = 50

# ── Classifier ───────────────────────────────────────────────────────────────
CLASSIFIER_BASE = "roberta-base"
CLASSIFIER_MAX_LEN = 128
CLASSIFIER_EPOCHS = 5
CLASSIFIER_LR = 2e-5
CLASSIFIER_BATCH = 32
CLASSIFIER_WARMUP_RATIO = 0.1
HARD_NEG_WEIGHT = 0.5           # loss weight for synthetic hard-negative examples

# Train / val / test split (fractions of real lines per character)
TRAIN_FRAC = 0.70
VAL_FRAC = 0.15
# TEST_FRAC = 1 - TRAIN_FRAC - VAL_FRAC

# ── Hard negatives ───────────────────────────────────────────────────────────
HARD_NEG_PER_PAIR = 40          # Claude rewrites per (source_char, target_style) pair
CLAUDE_MODEL = "claude-opus-4-5"

# ── Generator ────────────────────────────────────────────────────────────────
GENERATOR_BASE = "TinyLlama/TinyLlama-1.1B-Chat-v1.0"   # ~1.1B, freely accessible
GENERATOR_MAX_NEW = 120
GENERATOR_EPOCHS = 3
GENERATOR_LR = 2e-4
GENERATOR_BATCH = 4
GENERATOR_GRAD_ACCUM = 8
LORA_R = 16
LORA_ALPHA = 32
LORA_DROPOUT = 0.05
LORA_TARGET_MODULES = ["q_proj", "v_proj", "k_proj", "o_proj"]

# ── Reranking ────────────────────────────────────────────────────────────────
BEAM_N = 3                      # candidates generated per prompt
TEMPERATURE = 0.9
TOP_P = 0.95
