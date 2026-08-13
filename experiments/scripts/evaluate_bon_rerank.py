"""
Compare plain LoRA generation vs Best-of-N classifier reranking.

Metrics:
  1. Same RoBERTa persona classifier used as the reranker (P(target|reply))
  2. Independent local LLM judge: base Qwen2.5-1.5B-Instruct with LoRA disabled
     (same backbone family as the generator, but not the classifier and not
     the persona adapter — free, no Inference API credits)

Usage (from final_project/):
    python -u experiments/scripts/evaluate_bon_rerank.py
    python -u experiments/scripts/evaluate_bon_rerank.py --n 3 --seed 42
"""

from __future__ import annotations

import argparse
import json
import os
import re
import time
from pathlib import Path

os.environ.setdefault("PYTHONUNBUFFERED", "1")
os.environ.setdefault("HF_HUB_DISABLE_PROGRESS_BARS", "1")
os.environ.setdefault("TRANSFORMERS_VERBOSITY", "error")

ROOT = Path(__file__).resolve().parents[2]

import torch

from movie_persona.classifier import predict_persona_batch
from movie_persona.pipeline import CHARACTERS, PERSONA_IDENTITY, PersonaPipeline

OUT_DIR = ROOT / "results" / "published"
OUT_JSON = OUT_DIR / "bon_vs_plain_eval.json"
OUT_MD = OUT_DIR / "bon_vs_plain_eval.md"

PROMPTS = [
    "How's your day going?",
    "What do you think about modern life?",
    "Someone just cut me off in traffic. What should I do?",
    "Tell me something you care about.",
    "I'm bored. Entertain me.",
    "Do you trust people?",
    "What's the worst advice you've ever gotten?",
    "Describe yourself in one sentence.",
]

PERSONA_BLURBS = {
    "jack": (
        "Fight Club's Jack: detached, deadpan, clipped sentences, dark ironic "
        "humor delivered flatly, clinical self-observation."
    ),
    "bateman": (
        "American Psycho's Patrick Bateman: cold, precise, polished diction, "
        "obsessive detail, status markers, controlled even when dark."
    ),
    "alvy": (
        "Annie Hall's Alvy Singer: neurotic, self-deprecating, stammers, "
        "tangents, restarts mid-thought, anxious humor."
    ),
    "ben": (
        "The Graduate's Benjamin Braddock: hesitant, soft, awkward, terse, "
        "understated, uncertain."
    ),
    "erin": (
        "Erin Brockovich: blunt, fiery, confrontational warmth, direct, "
        "colloquial, assertive."
    ),
}


def classifier_score(text: str, persona: str) -> float:
    return float(predict_persona_batch([text])[0].get(persona, 0.0))


def local_judge_score(
    pipe: PersonaPipeline,
    persona: str,
    prompt: str,
    reply: str,
) -> int:
    """Score 1–5 with base instruct model (LoRA adapters disabled)."""
    short, full = PERSONA_IDENTITY[persona]
    blurb = PERSONA_BLURBS[persona]
    system = (
        "You rate how well a chat reply matches a movie character's speaking "
        "style. Ignore factual correctness except when the reply clearly "
        "breaks character. Reply with ONLY an integer 1-5.\n"
        "1=wrong persona / generic chatbot\n"
        "2=weak hints of the persona\n"
        "3=somewhat in character\n"
        "4=clearly in character\n"
        "5=strongly distinctive persona voice"
    )
    user = (
        f"Character: {full} ({short})\n"
        f"Style: {blurb}\n"
        f"User said: {prompt}\n"
        f"Reply to rate:\n{reply}\n\n"
        "Score (1-5 only):"
    )
    judge_prompt = (
        f"<|im_start|>system\n{system}<|im_end|>\n"
        f"<|im_start|>user\n{user}<|im_end|>\n"
        "<|im_start|>assistant\n"
    )
    inputs = pipe.gen_tokenizer(judge_prompt, return_tensors="pt").to(pipe.device)
    # Base model only — independent of the persona LoRA used for generation.
    ctx = (
        pipe.gen_model.disable_adapter()
        if hasattr(pipe.gen_model, "disable_adapter")
        else nullcontext()
    )
    with torch.no_grad(), ctx:
        out = pipe.gen_model.generate(
            **inputs,
            max_new_tokens=4,
            do_sample=False,
            pad_token_id=pipe.gen_tokenizer.eos_token_id,
        )
    raw = pipe.gen_tokenizer.decode(
        out[0, inputs["input_ids"].shape[1] :], skip_special_tokens=True
    ).strip()
    m = re.search(r"[1-5]", raw)
    if not m:
        # Fail closed to mid score rather than crashing the whole run.
        print(f"  [judge] unparseable {raw!r} -> 3")
        return 3
    return int(m.group(0))


class nullcontext:
    def __enter__(self):
        return None

    def __exit__(self, *args):
        return False


def mean(xs: list[float]) -> float:
    return sum(xs) / len(xs) if xs else 0.0


def paired_wins(a: list[float], b: list[float]) -> tuple[int, int, int]:
    wa = wb = ties = 0
    for x, y in zip(a, b):
        if x > y:
            wa += 1
        elif y > x:
            wb += 1
        else:
            ties += 1
    return wa, wb, ties


def summarize(rows: list[dict], meta: dict) -> dict:
    plain_clf = [r["plain_clf"] for r in rows]
    bon_clf = [r["bon_clf"] for r in rows]
    plain_j = [float(r["plain_judge"]) for r in rows]
    bon_j = [float(r["bon_judge"]) for r in rows]
    clf_bw, clf_pw, clf_t = paired_wins(bon_clf, plain_clf)
    j_bw, j_pw, j_t = paired_wins(bon_j, plain_j)
    return {
        **meta,
        "n_pairs": len(rows),
        "plain_clf_mean": mean(plain_clf),
        "bon_clf_mean": mean(bon_clf),
        "clf_delta": mean(bon_clf) - mean(plain_clf),
        "plain_judge_mean": mean(plain_j),
        "bon_judge_mean": mean(bon_j),
        "judge_delta": mean(bon_j) - mean(plain_j),
        "clf_bon_wins": clf_bw,
        "clf_plain_wins": clf_pw,
        "clf_ties": clf_t,
        "judge_bon_wins": j_bw,
        "judge_plain_wins": j_pw,
        "judge_ties": j_t,
    }


def write_markdown(summary: dict, rows: list[dict]) -> None:
    s = summary
    lines = [
        "# Best-of-N vs plain LoRA — persona consistency",
        "",
        f"- Characters: {', '.join(s['characters'])}",
        f"- Prompts per character: {s['n_prompts']}",
        f"- BoN candidates (N): {s['n_candidates']}",
        f"- Seed: {s['seed']}",
        f"- LLM judge: `{s['judge_model']}`",
        f"- Pairs: {s['n_pairs']}",
        "",
        "## Aggregate",
        "",
        "| Metric | Plain LoRA | Best-of-N | Δ (BoN − plain) |",
        "|---|---:|---:|---:|",
        f"| Mean classifier P(target) | {s['plain_clf_mean']:.4f} | {s['bon_clf_mean']:.4f} | {s['clf_delta']:.4f} |",
        f"| Mean LLM judge (1–5) | {s['plain_judge_mean']:.3f} | {s['bon_judge_mean']:.3f} | {s['judge_delta']:.3f} |",
        "",
        f"- Classifier pairwise: BoN wins **{s['clf_bon_wins']}**, plain wins **{s['clf_plain_wins']}**, ties **{s['clf_ties']}**",
        f"- Judge pairwise: BoN wins **{s['judge_bon_wins']}**, plain wins **{s['judge_plain_wins']}**, ties **{s['judge_ties']}**",
        "",
        "Note: the classifier metric uses the same scorer as the reranker, so "
        "BoN is expected to look better on that axis by selection. The LLM "
        "judge (base instruct model, LoRA off) is the independent check.",
        "",
        "## Per example",
        "",
        "| persona | prompt | plain clf | BoN clf | plain judge | BoN judge |",
        "|---|---|---:|---:|---:|---:|",
    ]
    for r in rows:
        p = r["prompt"].replace("|", "/")
        lines.append(
            f"| {r['persona']} | {p[:48]} | {r['plain_clf']:.3f} | {r['bon_clf']:.3f} "
            f"| {r['plain_judge']} | {r['bon_judge']} |"
        )
    OUT_MD.write_text("\n".join(lines) + "\n", encoding="utf-8")


def save(payload: dict) -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    OUT_JSON.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")
    write_markdown(payload["summary"], payload["examples"])


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--n", type=int, default=3, help="Best-of-N candidates")
    parser.add_argument("--seed", type=int, default=42, help="Single seed (ignored if --seeds set)")
    parser.add_argument(
        "--seeds",
        type=int,
        nargs="+",
        default=None,
        help="Multiple seeds to average over, e.g. --seeds 42 43 44",
    )
    parser.add_argument("--characters", nargs="+", default=CHARACTERS)
    parser.add_argument(
        "--resume",
        action="store_true",
        help="Reuse completed pairs already in results JSON",
    )
    args = parser.parse_args()
    seeds = args.seeds or [args.seed]

    meta = {
        "characters": list(args.characters),
        "n_prompts": len(PROMPTS),
        "n_candidates": args.n,
        "seeds": seeds,
        "seed": seeds[0] if len(seeds) == 1 else seeds,
        "judge_model": "Qwen/Qwen2.5-1.5B-Instruct (base, LoRA disabled)",
    }

    done: dict[tuple[int, str, str], dict] = {}
    if args.resume and OUT_JSON.exists():
        prev = json.loads(OUT_JSON.read_text(encoding="utf-8"))
        for r in prev.get("examples", []):
            if "plain_judge" in r and "bon_judge" in r:
                done[(int(r.get("seed", seeds[0])), r["persona"], r["prompt"])] = r
        print(f"[resume] loaded {len(done)} completed pairs")

    pipe = PersonaPipeline()
    rows: list[dict] = []
    t0 = time.time()

    for seed in seeds:
        torch.manual_seed(seed)
        if torch.cuda.is_available():
            torch.cuda.manual_seed_all(seed)
        print(f"\n######## seed={seed} ########")

        for persona in args.characters:
            for prompt in PROMPTS:
                key = (seed, persona, prompt)
                if key in done:
                    row = done[key]
                    rows.append(row)
                    print(f"\n[{seed}/{persona}] {prompt!r} (cached)")
                    continue

                print(f"\n[{seed}/{persona}] {prompt!r}")
                plain_text = pipe.plain_generate(prompt, persona)
                bon_text = pipe.chat(prompt, persona, n=args.n)

                plain_clf = classifier_score(plain_text, persona)
                bon_clf = classifier_score(bon_text, persona)
                plain_j = local_judge_score(pipe, persona, prompt, plain_text)
                bon_j = local_judge_score(pipe, persona, prompt, bon_text)

                row = {
                    "seed": seed,
                    "persona": persona,
                    "prompt": prompt,
                    "plain_text": plain_text,
                    "bon_text": bon_text,
                    "plain_clf": plain_clf,
                    "bon_clf": bon_clf,
                    "plain_judge": plain_j,
                    "bon_judge": bon_j,
                }
                rows.append(row)
                print(
                    f"  plain clf={plain_clf:.3f} judge={plain_j} | "
                    f"BoN clf={bon_clf:.3f} judge={bon_j}"
                )
                print(f"  plain: {plain_text[:120]!r}")
                print(f"  BoN:   {bon_text[:120]!r}")

                summary = summarize(
                    rows, {**meta, "elapsed_sec": round(time.time() - t0, 1)}
                )
                save({"summary": summary, "examples": rows})

    summary = summarize(rows, {**meta, "elapsed_sec": round(time.time() - t0, 1)})
    save({"summary": summary, "examples": rows})

    print("\n=== SUMMARY ===")
    print(json.dumps(summary, indent=2))
    print(f"\nWrote {OUT_JSON}")
    print(f"Wrote {OUT_MD}")


if __name__ == "__main__":
    main()
