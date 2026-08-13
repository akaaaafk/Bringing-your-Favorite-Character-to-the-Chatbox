"""
Generate "hard negative" training examples using Claude: take a real line
spoken by character A, and have Claude rewrite it as character B would say
it. The rewrite is labeled as character B (a negative example of A's
style), forcing the classifier to learn genuine stylistic signal instead
of just memorizing vocabulary/topic overlap.

Reads:  data/processed/train.csv   (real lines only — never touches val/test)
Writes: data/processed/train_hard_negatives.csv

Requires ANTHROPIC_API_KEY set in the environment (or a .env file).

Usage:
    python experiments/scripts/generate_hard_negatives.py
"""

from pathlib import Path
import json
import pandas as pd
from anthropic import Anthropic
from dotenv import load_dotenv

load_dotenv()

PROCESSED_DIR = Path(__file__).resolve().parents[2] / "data" / "processed"
TRAIN_PATH = PROCESSED_DIR / "train.csv"
OUTPUT_PATH = PROCESSED_DIR / "train_hard_negatives.csv"

client = Anthropic()
MODEL = "claude-sonnet-4-5"

# Explicit, distinguishing traits per character — included in the prompt
# alongside reference lines so the model has more than just examples to
# infer style from. Written to call out what's DIFFERENT about each voice,
# since generic-sounding traits (e.g. "casual") don't help distinguish
# characters from each other.
CHARACTER_TRAITS = {
    "JACK": (
        "Detached, deadpan narrator voice. Short, clipped sentences. Dark, "
        "ironic humor delivered flatly, without emotional emphasis. "
        "Sometimes drifts into self-aware, almost clinical observations "
        "about his own life, as if narrating from outside himself."
    ),
    "BATEMAN": (
        "Clinical and blunt. Frequently references brands, designers, "
        "restaurants, or status markers even in casual conversation. "
        "Tone stays flat and controlled even when the content turns dark "
        "or vulgar — no dramatic build-up, just a sudden shift. Cutting, "
        "dismissive remarks delivered matter-of-factly. Speaks with "
        "certainty, not hesitation — NEVER uses hedging fillers like "
        "'I mean', 'I guess', or 'kind of'."
    ),
    "ALVY": (
        "Rambling and self-interrupting. Frequently restarts or corrects "
        "his own sentences mid-thought ('There's-there's...'). Neurotic, "
        "digresses into tangents, uses filler words ('uh', 'you know'). "
        "Wordy — explains and over-explains rather than stating things "
        "simply."
    ),
    "BEN": (
        "Terse and hesitant. Short, often monosyllabic responses. Avoids "
        "elaborating even when more explanation would help. Passive "
        "phrasing, understated reactions, rarely initiates a topic — "
        "mostly responds to what others say."
    ),
    "ERIN": (
        "Blunt and confrontational. Asks direct questions rather than "
        "making statements. Informal, colloquial phrasing. Assertive — "
        "pushes back rather than deferring, even in formal or "
        "intimidating settings."
    ),
}

# One worked example per character, independent of any specific source
# line, so the model has a concrete pattern to imitate rather than only
# a prose description of traits to infer from. This is what actually
# fixed the "generic voice" failure mode in testing — trait descriptions
# alone weren't concrete enough on their own.
EXAMPLE_REWRITES = {
    "JACK": (
        "Input: \"I'm tired.\"\n"
        "  Output: \"I hadn't slept in six days. Not that it mattered. "
        "Insomnia turns everything into a copy of a copy of a copy.\""
    ),
    "BATEMAN": (
        "Input: \"Where's the bathroom?\"\n"
        "  Output: \"Bathroom. Preferably not stocked with whatever "
        "off-brand towels Van Patten's using these days.\""
    ),
    "ALVY": (
        "Input: \"I don't know what to say.\"\n"
        "  Output: \"I don't- I mean, what do you say to something like "
        "that? There's no- I don't have a response, I mean, does anyone?\""
    ),
    "BEN": (
        "Input: \"I don't know what to say.\"\n"
        "  Output: \"I don't know.\""
    ),
    "ERIN": (
        "Input: \"I don't know what to say.\"\n"
        "  Output: \"What do you want me to say? That everything's fine? "
        "Because it's not.\""
    ),
}

# (source_character, target_character, n_examples) — direction matters:
# we sample real lines FROM source, rewrite them AS target.
# Focused near-pairs get more volume; everything else gets light coverage.
PAIR_BUDGET = [
    ("JACK", "BATEMAN", 50),
    ("BATEMAN", "JACK", 50),
    ("ALVY", "BEN", 40),
    ("BEN", "ALVY", 40),
    # light coverage across remaining pair-directions
    ("JACK", "ALVY", 10), ("ALVY", "JACK", 10),
    ("JACK", "BEN", 10), ("BEN", "JACK", 10),
    ("JACK", "ERIN", 10), ("ERIN", "JACK", 10),
    ("BATEMAN", "ALVY", 10), ("ALVY", "BATEMAN", 10),
    ("BATEMAN", "BEN", 10), ("BEN", "BATEMAN", 10),
    ("BATEMAN", "ERIN", 10), ("ERIN", "BATEMAN", 10),
]

REWRITE_PROMPT = """You are helping build a stylistic-similarity dataset for a research project on character voice classification.

{target}'s distinguishing voice traits:
{target_traits}

Reference lines showing how {target} actually speaks in their film — pay attention to sentence length, vocabulary, rhythm, and tone, not just individual words:
{reference_lines}

For contrast, here is how {source} (a DIFFERENT character) speaks — make sure your rewrite does NOT sound like this:
{source_traits}

Here is an example showing {target}'s voice pattern in action (unrelated content, just showing the STYLE to imitate):
{target_example}

Now, rewrite the following line — originally spoken by {source} — so that it sounds like {target} said it instead. Preserve the underlying meaning/intent of the line, but restructure the phrasing, sentence length, and rhythm to match {target}'s actual voice as described and shown above. Do not just insert one of {target}'s typical words or phrases into {source}'s original sentence structure — genuinely rewrite it as if {target} were expressing that same idea in their own distinct way, following their traits and the example above. Do not default to hedging fillers ("I mean", "I guess", "kind of", etc.) unless they specifically appear in {target}'s reference lines above — only use them if they're actually part of {target}'s voice, not as a generic fallback for uncertainty.

Original line (spoken by {source}): "{source_line}"

Respond with ONLY the rewritten line, no preamble, no quotation marks, no explanation."""


def get_reference_lines(train_df: pd.DataFrame, character: str, n: int = 8) -> str:
    lines = (
        train_df[train_df["character_name"] == character]["text"]
        .sample(n, random_state=42)
        .tolist()
    )
    return "\n".join(f"- {line}" for line in lines)


def rewrite_line(source_line: str, source: str, target: str, reference_lines: str) -> str:
    prompt = REWRITE_PROMPT.format(
        target=target,
        source=source,
        source_line=source_line,
        reference_lines=reference_lines,
        target_traits=CHARACTER_TRAITS[target],
        source_traits=CHARACTER_TRAITS[source],
        target_example=EXAMPLE_REWRITES[target],
    )
    response = client.messages.create(
        model=MODEL,
        max_tokens=150,
        messages=[{"role": "user", "content": prompt}],
    )
    return response.content[0].text.strip()


def main() -> None:
    train_df = pd.read_csv(TRAIN_PATH)

    # Resume support: skip pairs/rows already generated if this script
    # was interrupted and re-run.
    existing = pd.read_csv(OUTPUT_PATH) if OUTPUT_PATH.exists() else pd.DataFrame(
        columns=["source_character", "target_character", "source_line", "text", "character_name", "is_synthetic"]
    )
    results = existing.to_dict("records")
    done_count = {
        (r["source_character"], r["target_character"]): sum(
            1 for x in results if x["source_character"] == r["source_character"] and x["target_character"] == r["target_character"]
        )
        for r in results
    }

    for source, target, n in PAIR_BUDGET:
        already = done_count.get((source, target), 0)
        remaining = n - already
        if remaining <= 0:
            print(f"{source} -> {target}: already have {already}/{n}, skipping")
            continue

        print(f"{source} -> {target}: generating {remaining} (have {already}/{n})")
        reference_lines = get_reference_lines(train_df, target)
        source_lines = (
            train_df[train_df["character_name"] == source]["text"]
            .sample(remaining, random_state=hash((source, target)) % (2**31))
            .tolist()
        )

        for source_line in source_lines:
            try:
                rewritten = rewrite_line(source_line, source, target, reference_lines)
            except Exception as e:
                print(f"  FAILED on '{source_line[:40]}...': {e}")
                continue

            results.append({
                "source_character": source,
                "target_character": target,
                "source_line": source_line,
                "text": rewritten,
                "character_name": target,  # label = the STYLE being imitated
                "is_synthetic": True,
            })
            # save incrementally so a crash doesn't lose progress
            pd.DataFrame(results).to_csv(OUTPUT_PATH, index=False)

    print(f"\nDone. {len(results)} total synthetic examples -> {OUTPUT_PATH}")
    print(pd.DataFrame(results).groupby(["source_character", "target_character"]).size())


if __name__ == "__main__":
    main()
