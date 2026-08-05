"""
Synthesize "hard negative" examples with Claude.

For each ordered pair (source_char, target_style), we take HARD_NEG_PER_PAIR
lines from source_char and ask Claude to rewrite each line in target_style.
The result is a line that looks like target_style but originated elsewhere —
forcing the classifier to learn genuine stylistic signal rather than topic.

Output: data/hard_negatives.jsonl
Each record: {"text": "...", "label": <int>, "character": "...", "is_hard_neg": true,
              "source_character": "..."}

Usage:
    python generate_hard_negatives.py              # uses config.py
    ANTHROPIC_API_KEY=sk-... python generate_hard_negatives.py
"""
import itertools
import json
import os
import random
import time
from pathlib import Path

import anthropic
from datasets import load_from_disk

from config import (
    CLAUDE_MODEL, HARD_NEG_PER_PAIR, NEGATIVES_FILE, PROCESSED_DIR,
)


SYSTEM_PROMPT = """\
You are a creative writer and linguist specialising in film character voices.
When asked to rewrite a line, you produce ONLY the rewritten dialogue — no
explanations, no quotes, no stage directions, no attribution.
Keep the core meaning but transform vocabulary, sentence rhythm, idiom, and
register to match the target character's established speech patterns exactly.
Output exactly one line of dialogue."""


def build_user_prompt(text: str, target: str) -> str:
    # Include a brief style note for each character to ground Claude's output.
    style_notes = {
        "HANNIBAL LECTER": (
            "Hannibal Lecter: precise, erudite, theatrical. Uses elevated vocabulary, "
            "classical allusions, and speaks with calm menace. Sentences are well-formed "
            "and never rushed."
        ),
        "CLARICE": (
            "Clarice Starling: earnest, professional, plain-spoken. "
            "Direct and to the point; no flourishes. Slight Southern pragmatism."
        ),
        "JOKER": (
            "The Joker (Dark Knight): chaotic, clipped, darkly comic. "
            "Short sentences, abrupt shifts, rhetorical questions, nihilistic humour."
        ),
        "FORREST": (
            "Forrest Gump: simple, literal, repetitive. Uses 'Mama said…', "
            "'I'm not a smart man', 'and that's all I have to say about that'. "
            "Child-like sincerity; no irony."
        ),
        "JAMES BOND": (
            "James Bond: suave, dry, controlled. Laconic quips, confident understatement, "
            "never shows surprise. Speaks in smooth, complete sentences with wry wit."
        ),
    }
    note = style_notes.get(target, f"{target}: maintain their distinctive film speech style.")
    return f"Rewrite the following line in the voice of {target}.\n{note}\n\nLine to rewrite:\n{text}"


def generate_negatives(
    client: anthropic.Anthropic,
    source_lines: list[str],
    source_char: str,
    target_char: str,
    label: int,
    n: int,
) -> list[dict]:
    samples = random.sample(source_lines, min(n, len(source_lines)))
    records = []
    for text in samples:
        try:
            resp = client.messages.create(
                model=CLAUDE_MODEL,
                max_tokens=200,
                system=SYSTEM_PROMPT,
                messages=[{"role": "user", "content": build_user_prompt(text, target_char)}],
            )
            rewritten = resp.content[0].text.strip()
            if rewritten:
                records.append({
                    "text": rewritten,
                    "label": label,
                    "character": target_char,
                    "is_hard_neg": True,
                    "source_character": source_char,
                })
        except anthropic.APIError as e:
            print(f"  [warn] API error for ({source_char}→{target_char}): {e}")
            time.sleep(5)
    return records


def run(resume: bool = True) -> None:
    meta_path = PROCESSED_DIR / "meta.json"
    if not meta_path.exists():
        raise FileNotFoundError("Run data_pipeline.py first to build the dataset.")

    meta = json.loads(meta_path.read_text())
    characters: list[str] = meta["characters"]
    label2id: dict[str, int] = meta["label2id"]

    dataset = load_from_disk(str(PROCESSED_DIR / "splits"))
    train_ds = dataset["train"]

    char_lines: dict[str, list[str]] = {
        c: [row["text"] for row in train_ds if row["character"] == c]
        for c in characters
    }

    api_key = os.environ.get("ANTHROPIC_API_KEY")
    if not api_key:
        raise EnvironmentError("Set ANTHROPIC_API_KEY before running this script.")
    client = anthropic.Anthropic(api_key=api_key)

    existing: list[dict] = []
    done_pairs: set[tuple[str, str]] = set()
    if resume and NEGATIVES_FILE.exists():
        with open(NEGATIVES_FILE) as f:
            existing = [json.loads(l) for l in f if l.strip()]
        done_pairs = {(r["source_character"], r["character"]) for r in existing}
        print(f"[neg] resuming — {len(existing)} existing records, {len(done_pairs)} pairs done")

    new_records: list[dict] = []
    pairs = list(itertools.permutations(characters, 2))
    for i, (src, tgt) in enumerate(pairs):
        if (src, tgt) in done_pairs:
            print(f"[neg] skip {src} → {tgt} (already done)")
            continue
        print(f"[neg] [{i+1}/{len(pairs)}] {src} → {tgt} …")
        records = generate_negatives(
            client,
            char_lines[src],
            source_char=src,
            target_char=tgt,
            label=label2id[tgt],
            n=HARD_NEG_PER_PAIR,
        )
        new_records.extend(records)
        print(f"  generated {len(records)} examples")
        time.sleep(1)  # gentle rate-limit buffer

    all_records = existing + new_records
    with open(NEGATIVES_FILE, "w") as f:
        for r in all_records:
            f.write(json.dumps(r) + "\n")

    print(f"\n[neg] total hard negatives saved: {len(all_records)} → {NEGATIVES_FILE}")


if __name__ == "__main__":
    import argparse
    p = argparse.ArgumentParser()
    p.add_argument("--no-resume", action="store_true",
                   help="overwrite existing negatives file")
    args = p.parse_args()
    run(resume=not args.no_resume)
