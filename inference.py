"""
Persona inference pipeline with Best-of-N classifier reranking.

Usage (programmatic):
    from inference import PersonaPipeline
    pipe = PersonaPipeline()
    response = pipe.chat("Tell me about the lambs, Clarice.", character="HANNIBAL LECTER")

Usage (CLI):
    python inference.py --character "JOKER" --prompt "Why so serious?"
    python inference.py --character "FORREST" --prompt "What is life?" --n 5
"""
import argparse
import json
from dataclasses import dataclass, field
from pathlib import Path

import torch
from transformers import (
    AutoModelForCausalLM,
    AutoModelForSequenceClassification,
    AutoTokenizer,
    pipeline,
)

from config import (
    BEAM_N, CLASSIFIER_DIR, GENERATOR_DIR, GENERATOR_MAX_NEW,
    PROCESSED_DIR, TEMPERATURE, TOP_P,
)


@dataclass
class CandidateResult:
    text: str
    persona_score: float          # classifier prob for target character
    rank: int                     # 1 = best


class PersonaPipeline:
    """
    Two-model pipeline:
      1. LoRA-fine-tuned generator produces N candidate completions.
      2. RoBERTa classifier scores each for persona-consistency.
      3. Highest-scoring candidate is returned.
    """

    def __init__(
        self,
        generator_path: str | Path = None,
        classifier_path: str | Path = None,
        device: str | None = None,
    ):
        gen_path = str(generator_path or GENERATOR_DIR / "merged")
        cls_path = str(classifier_path or CLASSIFIER_DIR)

        if device is None:
            device = "cuda" if torch.cuda.is_available() else "cpu"
        self.device = device

        print(f"[pipeline] loading generator from {gen_path} …")
        self.gen_tokenizer = AutoTokenizer.from_pretrained(gen_path, use_fast=True)
        self.gen_tokenizer.pad_token = self.gen_tokenizer.eos_token
        self.gen_model = AutoModelForCausalLM.from_pretrained(
            gen_path,
            torch_dtype=torch.float16 if device == "cuda" else torch.float32,
        ).to(device)
        self.gen_model.eval()

        print(f"[pipeline] loading classifier from {cls_path} …")
        self.cls_tokenizer = AutoTokenizer.from_pretrained(cls_path)
        self.cls_model = AutoModelForSequenceClassification.from_pretrained(
            cls_path
        ).to(device)
        self.cls_model.eval()

        # label mapping from classifier config
        self.id2label: dict[int, str] = self.cls_model.config.id2label
        self.label2id: dict[str, int] = self.cls_model.config.label2id

        meta_path = PROCESSED_DIR / "meta.json"
        self.characters: list[str] = []
        if meta_path.exists():
            self.characters = json.loads(meta_path.read_text())["characters"]

    # ── Generation ────────────────────────────────────────────────────────────

    def _build_prompt(self, user_text: str, character: str) -> str:
        tag = character.replace(" ", "_")
        return (
            f"<|system|>You are {tag}. Speak exactly in their voice.\n</s>\n"
            f"<|user|>{user_text}\n</s>\n"
            f"<|assistant|>"
        )

    def _generate_candidates(self, prompt: str, n: int) -> list[str]:
        inputs = self.gen_tokenizer(
            prompt, return_tensors="pt", truncation=True, max_length=512
        ).to(self.device)

        with torch.no_grad():
            outputs = self.gen_model.generate(
                **inputs,
                max_new_tokens=GENERATOR_MAX_NEW,
                do_sample=True,
                temperature=TEMPERATURE,
                top_p=TOP_P,
                num_return_sequences=n,
                pad_token_id=self.gen_tokenizer.eos_token_id,
                eos_token_id=self.gen_tokenizer.eos_token_id,
            )

        prompt_len = inputs["input_ids"].shape[1]
        candidates = []
        for output in outputs:
            generated = self.gen_tokenizer.decode(
                output[prompt_len:], skip_special_tokens=True
            ).strip()
            candidates.append(generated)
        return candidates

    # ── Scoring ───────────────────────────────────────────────────────────────

    def _score_candidates(
        self, candidates: list[str], target_label_id: int
    ) -> list[float]:
        if not candidates:
            return []
        enc = self.cls_tokenizer(
            candidates,
            return_tensors="pt",
            truncation=True,
            max_length=128,
            padding=True,
        ).to(self.device)
        with torch.no_grad():
            logits = self.cls_model(**enc).logits
        probs = torch.softmax(logits, dim=-1)[:, target_label_id].cpu().tolist()
        return probs

    # ── Public API ────────────────────────────────────────────────────────────

    def chat(
        self,
        user_text: str,
        character: str,
        n: int = BEAM_N,
        return_all: bool = False,
    ) -> str | list[CandidateResult]:
        """
        Generate n candidates and return the one with the highest classifier score
        for the target character.  If return_all=True, returns all ranked candidates.
        """
        char_upper = character.upper()
        if char_upper not in self.label2id:
            raise ValueError(
                f"Unknown character '{character}'. "
                f"Available: {list(self.label2id.keys())}"
            )
        target_id = self.label2id[char_upper]

        prompt = self._build_prompt(user_text, char_upper)
        candidates = self._generate_candidates(prompt, n)
        scores = self._score_candidates(candidates, target_id)

        ranked = sorted(
            [CandidateResult(text=t, persona_score=s, rank=0)
             for t, s in zip(candidates, scores)],
            key=lambda x: x.persona_score,
            reverse=True,
        )
        for i, r in enumerate(ranked):
            r.rank = i + 1

        if return_all:
            return ranked
        return ranked[0].text if ranked else ""

    def plain_generate(self, user_text: str, character: str) -> str:
        """No reranking — plain greedy / sampling baseline."""
        char_upper = character.upper()
        prompt = self._build_prompt(user_text, char_upper)
        candidates = self._generate_candidates(prompt, n=1)
        return candidates[0] if candidates else ""


# ── CLI ───────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--character", required=True)
    parser.add_argument("--prompt", required=True)
    parser.add_argument("--n", type=int, default=BEAM_N)
    parser.add_argument("--all", action="store_true", help="show all candidates")
    args = parser.parse_args()

    pipe = PersonaPipeline()
    results = pipe.chat(args.prompt, args.character, n=args.n, return_all=True)

    if args.all:
        print(f"\nAll {len(results)} candidates for [{args.character}]:")
        for r in results:
            print(f"  #{r.rank} (score={r.persona_score:.3f}): {r.text}")
    else:
        print(f"\n[{args.character}]: {results[0].text}")
        print(f"  persona score: {results[0].persona_score:.3f} "
              f"(best of {len(results)})")
