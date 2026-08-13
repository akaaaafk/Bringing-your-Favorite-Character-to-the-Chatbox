"""
Download the Cornell Movie-Dialogs Corpus directly from the official
Cornell source (not a third-party mirror).

Citation:
  Cristian Danescu-Niculescu-Mizil and Lillian Lee. 2011.
  "Chameleons in imagined conversations: A new approach to understanding
  coordination of linguistic style in dialogs."
  https://www.cs.cornell.edu/~cristian/Cornell_Movie-Dialogs_Corpus.html

Usage:
    python experiments/scripts/download_data.py
"""

from pathlib import Path
import zipfile
import requests

RAW_DIR = Path(__file__).resolve().parents[2] / "data" / "raw"

OFFICIAL_URL = "https://www.cs.cornell.edu/~cristian/data/cornell_movie_dialogs_corpus.zip"


def main() -> None:
    RAW_DIR.mkdir(parents=True, exist_ok=True)
    zip_path = RAW_DIR / "cornell_movie_dialogs_corpus.zip"

    print(f"Downloading from official Cornell source: {OFFICIAL_URL}")
    resp = requests.get(OFFICIAL_URL, timeout=60)
    resp.raise_for_status()
    zip_path.write_bytes(resp.content)
    print(f"  Downloaded {len(resp.content):,} bytes -> {zip_path}")

    print("Extracting...")
    with zipfile.ZipFile(zip_path) as z:
        # The official zip nests files inside a
        # "cornell movie-dialogs corpus/" subfolder — flatten that out so
        # downstream scripts can just look in RAW_DIR directly.
        for member in z.namelist():
            filename = Path(member).name
            if not filename or not filename.endswith(".txt"):
                continue
            with z.open(member) as src, open(RAW_DIR / filename, "wb") as dst:
                dst.write(src.read())
            print(f"  Extracted: {filename}")

    print("Done.")


if __name__ == "__main__":
    main()
