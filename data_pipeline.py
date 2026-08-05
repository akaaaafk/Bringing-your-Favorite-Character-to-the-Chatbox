"""
Data pipeline: download Cornell Movie-Dialogs Corpus, parse, select characters,
build Hugging Face Datasets, and save processed splits.

Usage:
    python data_pipeline.py                   # use CHARACTERS from config.py
    python data_pipeline.py --list-top 30     # print top characters by line count
    python data_pipeline.py --chars "HANNIBAL LECTER,JOKER,FORREST"
"""
import argparse
import io
import json
import random
import urllib.request
import zipfile
from collections import Counter, defaultdict
from pathlib import Path

import pandas as pd
from datasets import ClassLabel, Dataset, DatasetDict, Features, Value

from config import (
    CHARACTERS, CORPUS_URL, MIN_LINES, PROCESSED_DIR,
    RAW_DIR, TRAIN_FRAC, VAL_FRAC,
)

SEP = " +++$+++ "

# ── Corpus download ──────────────────────────────────────────────────────────

def download_corpus() -> Path:
    zip_path = RAW_DIR / "cornell.zip"
    if zip_path.exists():
        print(f"[data] corpus already downloaded: {zip_path}")
        return zip_path
    print(f"[data] downloading Cornell corpus from {CORPUS_URL} …")
    urllib.request.urlretrieve(CORPUS_URL, zip_path)
    print(f"[data] saved to {zip_path} ({zip_path.stat().st_size // 1024} KB)")
    return zip_path


def _read_from_zip(zip_path: Path, filename: str) -> list[str]:
    with zipfile.ZipFile(zip_path) as zf:
        members = [m for m in zf.namelist() if Path(m).name == filename]
        if not members:
            raise FileNotFoundError(f"{filename} not found in zip")
        with zf.open(members[0]) as f:
            return f.read().decode("latin-1").splitlines()


# ── Parsing ──────────────────────────────────────────────────────────────────

def parse_characters(zip_path: Path) -> dict[str, str]:
    """Return {char_id: char_name_upper}."""
    lines = _read_from_zip(zip_path, "movie_characters_metadata.txt")
    mapping = {}
    for line in lines:
        parts = line.split(SEP)
        if len(parts) >= 2:
            mapping[parts[0].strip()] = parts[1].strip().upper()
    return mapping


def parse_lines(zip_path: Path, char_map: dict[str, str]) -> dict[str, list[str]]:
    """Return {char_name_upper: [utterance, …]}."""
    raw_lines = _read_from_zip(zip_path, "movie_lines.txt")
    corpus: dict[str, list[str]] = defaultdict(list)
    for raw in raw_lines:
        parts = raw.split(SEP)
        if len(parts) < 5:
            continue
        char_id = parts[1].strip()
        text = parts[4].strip()
        if not text:
            continue
        name = char_map.get(char_id)
        if name:
            corpus[name].append(text)
    return corpus


# ── Character selection ───────────────────────────────────────────────────────

def top_characters(corpus: dict[str, list[str]], n: int = 30) -> list[tuple[str, int]]:
    counts = [(name, len(lines)) for name, lines in corpus.items() if len(lines) >= MIN_LINES]
    return sorted(counts, key=lambda x: x[1], reverse=True)[:n]


def select_characters(
    corpus: dict[str, list[str]],
    requested: list[str],
) -> list[str]:
    available = {c for c in corpus if len(corpus[c]) >= MIN_LINES}
    selected = []
    missing = []
    for c in requested:
        if c in available:
            selected.append(c)
        else:
            # fuzzy fallback: substring match
            matches = [a for a in available if c in a or a in c]
            if matches:
                best = max(matches, key=lambda a: len(corpus[a]))
                print(f"[data] '{c}' not found exactly; using '{best}'")
                selected.append(best)
            else:
                missing.append(c)
    if missing:
        print(f"[data] WARNING — characters not found (< {MIN_LINES} lines or absent): {missing}")
    return selected


# ── Dataset construction ──────────────────────────────────────────────────────

def build_splits(
    corpus: dict[str, list[str]],
    characters: list[str],
    seed: int = 42,
) -> DatasetDict:
    random.seed(seed)
    label2id = {c: i for i, c in enumerate(characters)}

    def make_rows(chars_subset, lines_subset):
        rows = []
        for char, lines in zip(chars_subset, lines_subset):
            for text in lines:
                rows.append({"text": text, "label": label2id[char], "character": char})
        random.shuffle(rows)
        return rows

    train_rows, val_rows, test_rows = [], [], []
    for char in characters:
        lines = corpus[char][:]
        random.shuffle(lines)
        n = len(lines)
        n_train = int(n * TRAIN_FRAC)
        n_val = int(n * VAL_FRAC)
        train_rows += [{"text": t, "label": label2id[char], "character": char}
                       for t in lines[:n_train]]
        val_rows += [{"text": t, "label": label2id[char], "character": char}
                     for t in lines[n_train:n_train + n_val]]
        test_rows += [{"text": t, "label": label2id[char], "character": char}
                      for t in lines[n_train + n_val:]]

    for split in [train_rows, val_rows, test_rows]:
        random.shuffle(split)

    features = Features({
        "text": Value("string"),
        "label": ClassLabel(names=characters),
        "character": Value("string"),
    })

    return DatasetDict({
        "train": Dataset.from_list(train_rows, features=features),
        "val": Dataset.from_list(val_rows, features=features),
        "test": Dataset.from_list(test_rows, features=features),
    })


def print_stats(dsd: DatasetDict, characters: list[str]) -> None:
    print("\n── Dataset statistics ────────────────────────────────────────")
    for split_name, ds in dsd.items():
        counts = Counter(ds["character"])
        total = len(ds)
        print(f"\n  {split_name} ({total} examples)")
        for c in characters:
            print(f"    {c:<25} {counts.get(c, 0):>5}")
    print()


# ── Entry point ───────────────────────────────────────────────────────────────

def run(characters: list[str] | None = None, list_top: int = 0) -> DatasetDict | None:
    zip_path = download_corpus()
    char_map = parse_characters(zip_path)
    corpus = parse_lines(zip_path, char_map)

    if list_top:
        top = top_characters(corpus, list_top)
        print(f"\nTop {list_top} characters by line count:")
        for name, count in top:
            print(f"  {count:>5}  {name}")
        return None

    chars = characters or CHARACTERS
    selected = select_characters(corpus, chars)
    if len(selected) < 2:
        raise ValueError("Need at least 2 characters; check CHARACTERS in config.py")

    print(f"[data] selected characters: {selected}")
    dsd = build_splits(corpus, selected)
    print_stats(dsd, selected)

    dsd.save_to_disk(str(PROCESSED_DIR / "splits"))
    print(f"[data] saved to {PROCESSED_DIR / 'splits'}")

    # also save character list for downstream scripts
    meta = {"characters": selected, "label2id": {c: i for i, c in enumerate(selected)}}
    (PROCESSED_DIR / "meta.json").write_text(json.dumps(meta, indent=2))
    print(f"[data] saved metadata to {PROCESSED_DIR / 'meta.json'}")

    return dsd


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--list-top", type=int, default=0,
                        help="print top-N characters by line count and exit")
    parser.add_argument("--chars", type=str, default="",
                        help="comma-separated character names (overrides config.py)")
    args = parser.parse_args()

    chars_override = [c.strip().upper() for c in args.chars.split(",") if c.strip()] or None
    run(characters=chars_override, list_top=args.list_top)
