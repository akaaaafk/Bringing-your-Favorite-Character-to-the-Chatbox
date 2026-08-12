"""
Build prompt-response training pairs for the persona generator.

Pairs each selected-character line with the preceding line in the same
Cornell conversation. Output is used by scripts/train_generator.py.

Reads:
    data/processed/selected_characters.json
    data/processed/lines.csv          (from scripts/preprocess.py)
    data/raw/movie_conversations.txt
    data/processed/filtered_lines.csv (optional; count print only)

Writes:
    data/processed/training_pairs.csv

Usage:
    python scripts/build_training_pairs.py
"""

from __future__ import annotations

import ast
import json
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parent.parent
RAW_DIR = ROOT / "data" / "raw"
PROCESSED_DIR = ROOT / "data" / "processed"
SEP = " +++$+++ "


def main() -> None:
    selected_path = PROCESSED_DIR / "selected_characters.json"
    lines_path = PROCESSED_DIR / "lines.csv"
    conv_path = RAW_DIR / "movie_conversations.txt"
    out_path = PROCESSED_DIR / "training_pairs.csv"

    with open(selected_path) as f:
        selected_characters = json.load(f)

    filtered_path = PROCESSED_DIR / "filtered_lines.csv"
    if filtered_path.exists():
        filtered = pd.read_csv(filtered_path)
        print(f"Loaded {len(filtered):,} filtered lines")
        print(filtered.groupby("persona_tag").size())

    if not lines_path.exists():
        raise FileNotFoundError(
            f"{lines_path} not found. Run scripts/preprocess.py first."
        )
    if not conv_path.exists():
        raise FileNotFoundError(
            f"{conv_path} not found. Run scripts/download_data.py first."
        )

    char_ids = {c["character_id"] for c in selected_characters}
    tag_lookup = {c["character_id"]: c["persona_tag"] for c in selected_characters}

    full_lines = pd.read_csv(lines_path)
    line_text = dict(zip(full_lines["line_id"], full_lines["text"]))
    line_char = dict(zip(full_lines["line_id"], full_lines["character_id"]))

    conversations = []
    with open(conv_path, encoding="latin-1") as f:
        for raw in f:
            fields = raw.split(SEP)
            if len(fields) < 4:
                continue
            line_ids = ast.literal_eval(fields[3].strip())
            conversations.append(line_ids)

    training_pairs = []
    for conv in conversations:
        for i in range(len(conv) - 1):
            prompt_id, reply_id = conv[i], conv[i + 1]
            reply_char_id = line_char.get(reply_id)
            if reply_char_id not in char_ids:
                continue
            prompt_text = line_text.get(prompt_id, "")
            reply_text = line_text.get(reply_id, "")
            if prompt_text and reply_text:
                training_pairs.append(
                    {
                        "persona_tag": tag_lookup[reply_char_id],
                        "prompt": prompt_text,
                        "response": reply_text,
                    }
                )

    pairs_df = pd.DataFrame(training_pairs)
    print(f"Built {len(pairs_df):,} training pairs")
    print(pairs_df.groupby("persona_tag").size())

    PROCESSED_DIR.mkdir(parents=True, exist_ok=True)
    pairs_df.to_csv(out_path, index=False)
    print(f"\nSaved to {out_path}")


if __name__ == "__main__":
    main()
