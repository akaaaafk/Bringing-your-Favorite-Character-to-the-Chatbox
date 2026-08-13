"""
Parse the raw Cornell Movie-Dialogs Corpus files into a clean, analysis-ready
table of (character, movie, line text) rows, and produce a per-character line
count summary to support character selection.

Input:  data/raw/movie_lines.txt, movie_characters_metadata.txt
Output: data/processed/lines.csv
        data/processed/character_line_counts.csv

Usage:
    python experiments/scripts/preprocess.py
"""

from pathlib import Path
import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
RAW_DIR = ROOT / "data" / "raw"
PROCESSED_DIR = ROOT / "data" / "processed"

SEP = " +++$+++ "


def read_raw_lines(path: Path) -> list[str]:
    """Read a corpus file, trying utf-8 first then falling back to
    windows-1252 (the official Cornell release ships these files in that
    encoding, not plain latin-1 — windows-1252 gets smart quotes/em-dashes
    right where latin-1 would silently mangle them), then latin-1 as a
    last resort since it never raises on any byte sequence."""
    for encoding in ("utf-8", "windows-1252", "latin-1"):
        try:
            return path.read_text(encoding=encoding).splitlines()
        except UnicodeDecodeError:
            continue
    raise UnicodeDecodeError(f"Could not decode {path} with utf-8, windows-1252, or latin-1")


def load_movie_lines() -> pd.DataFrame:
    """movie_lines.txt fields: lineID, characterID, movieID, character name, text"""
    rows = []
    n_malformed = 0
    for raw in read_raw_lines(RAW_DIR / "movie_lines.txt"):
        fields = raw.split(SEP)
        if len(fields) < 5:
            # A handful of lines have empty/missing text after the last
            # separator; skip rather than silently mis-align columns.
            n_malformed += 1
            continue
        line_id, char_id, movie_id, char_name, text = fields[0], fields[1], fields[2], fields[3], SEP.join(fields[4:])
        rows.append(
            {
                "line_id": line_id,
                "character_id": char_id,
                "movie_id": movie_id,
                "character_name": char_name.strip(),
                "text": text.strip(),
            }
        )
    if n_malformed:
        print(f"  Skipped {n_malformed} malformed rows in movie_lines.txt")
    return pd.DataFrame(rows)


def load_character_metadata() -> pd.DataFrame:
    """movie_characters_metadata.txt fields:
    characterID, character name, movieID, movie title, gender, position in credits
    """
    rows = []
    for raw in read_raw_lines(RAW_DIR / "movie_characters_metadata.txt"):
        fields = raw.split(SEP)
        if len(fields) < 6:
            continue
        rows.append(
            {
                "character_id": fields[0],
                "character_name": fields[1].strip(),
                "movie_id": fields[2],
                "movie_title": fields[3].strip(),
                "gender": fields[4].strip(),
                "credit_position": fields[5].strip(),
            }
        )
    return pd.DataFrame(rows)


def main() -> None:
    PROCESSED_DIR.mkdir(parents=True, exist_ok=True)

    print("Parsing movie_lines.txt ...")
    lines_df = load_movie_lines()
    print(f"  {len(lines_df):,} utterances parsed")

    print("Parsing movie_characters_metadata.txt ...")
    chars_df = load_character_metadata()
    print(f"  {len(chars_df):,} characters parsed")

    # Join on character_id (character_name/movie_id duplicated across both
    # files, but movie_title only lives in the metadata file).
    merged = lines_df.merge(
        chars_df[["character_id", "movie_title"]],
        on="character_id",
        how="left",
    )

    # Drop empty-text lines and exact duplicate utterances.
    merged = merged[merged["text"].str.len() > 0].drop_duplicates(
        subset=["character_id", "text"]
    )

    out_path = PROCESSED_DIR / "lines.csv"
    merged.to_csv(out_path, index=False)
    print(f"Wrote {len(merged):,} clean rows -> {out_path}")

    # Per-(character, movie) line counts, since character names collide
    # across different movies (e.g. multiple characters named "John").
    counts = (
        merged.groupby(["character_id", "character_name", "movie_title"])
        .size()
        .reset_index(name="line_count")
        .sort_values("line_count", ascending=False)
    )
    counts_path = PROCESSED_DIR / "character_line_counts.csv"
    counts.to_csv(counts_path, index=False)
    print(f"Wrote {len(counts):,} character summaries -> {counts_path}")
    print("\nTop 20 characters by line count:")
    print(counts.head(20).to_string(index=False))


if __name__ == "__main__":
    main()
