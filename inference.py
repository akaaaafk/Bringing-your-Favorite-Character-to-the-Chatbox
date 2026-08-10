"""
Persona inference pipeline with Best-of-N classifier reranking.

Combines the LoRA-fine-tuned Qwen2.5-1.5B-Instruct generator with
Chelsea's RoBERTa persona classifier to generate and rerank candidate
responses for a selected character.

Usage (programmatic):
    from inference import PersonaPipeline
    pipe = PersonaPipeline()
    response = pipe.chat("How's your day going?", character="jack")

Usage (CLI):
    python inference.py --character "jack" --prompt "How's your day going?"
    python inference.py --character "bateman" --prompt "..." --n 5 --all
"""
import argparse
from dataclasses import dataclass
from pathlib import Path

import torch
from transformers import AutoModelForCausalLM, AutoTokenizer
from peft import PeftModel

from persona_classifier import predict_persona_batch

BASE_MODEL = "Qwen/Qwen2.5-1.5B-Instruct"
ADAPTER_DIR = Path(__file__).resolve().parent / "models" / "generator"
CHARACTERS = ["jack", "bateman", "alvy", "ben", "erin"]


@dataclass
class CandidateResult:
    text: str
    persona_score: float          # classifier probability for target character
    rank: int                     # 1 = best


class PersonaPipeline:
    """
    Two-model pipeline:
      1. LoRA-fine-tuned Qwen2.5-1.5B-Instruct generates N candidate replies.
      2. Chelsea's RoBERTa classifier scores each for persona-consistency.
      3. The highest-scoring candidate is returned.
    """

    def __init__(self, adapter_dir: str | Path = None, device: str | None = None):
        adapter_path = Path(adapter_dir or ADAPTER_DIR)
        self._using_adapter = adapter_path.exists() and any(adapter_path.iterdir())

        if device is None:
            device = "cuda" if torch.cuda.is_available() else "cpu"
        self.device = device

        print(f"[pipeline] loading generator base model {BASE_MODEL} …")
        self.gen_tokenizer = AutoTokenizer.from_pretrained(
            str(adapter_path) if self._using_adapter else BASE_MODEL
        )
        if self.gen_tokenizer.pad_token is None:
            self.gen_tokenizer.pad_token = self.gen_tokenizer.eos_token

        base_model = AutoModelForCausalLM.from_pretrained(
            BASE_MODEL,
            torch_dtype=torch.bfloat16 if device == "cuda" else torch.float32,
        ).to(device)

        if self._using_adapter:
            print(f"[pipeline] applying LoRA adapter from {adapter_path} …")
            self.gen_model = PeftModel.from_pretrained(base_model, str(adapter_path))
        else:
            print("[pipeline] no adapter found, using base model untuned")
            self.gen_model = base_model
        self.gen_model.eval()

        print("[pipeline] classifier loaded via persona_classifier module")

    # ── Generation ────────────────────────────────────────────────────────────

    def _build_prompt(self, user_text: str, persona_tag: str) -> str:
        system = (
            f"You are {persona_tag}. Respond only in their voice, "
            f"matching their vocabulary and speech patterns."
        )
        return (
            f"<|im_start|>system\n{system}<|im_end|>\n"
            f"<|im_start|>user\n{user_text}<|im_end|>\n"
            f"<|im_start|>assistant\n"
        )

    def _generate_candidates(self, prompt: str, n: int, max_new_tokens: int = 60) -> list[str]:
        inputs = self.gen_tokenizer(prompt, return_tensors="pt").to(self.device)
        with torch.no_grad():
            outputs = self.gen_model.generate(
                **inputs,
                max_new_tokens=max_new_tokens,
                do_sample=True,
                temperature=0.9,
                top_p=0.95,
                num_return_sequences=n,
                pad_token_id=self.gen_tokenizer.eos_token_id,
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

    def _score_candidates(self, candidates: list[str], persona_tag: str) -> list[float]:
        if not candidates:
            return []
        scores = predict_persona_batch(candidates)
        return [s.get(persona_tag, 0.0) for s in scores]

    # ── Public API ────────────────────────────────────────────────────────────

    def chat(
        self,
        user_text: str,
        character: str,
        n: int = 3,
        return_all: bool = False,
    ) -> str | list[CandidateResult]:
        """
        Generate n candidates and return the one with the highest classifier
        score for the target character. If return_all=True, returns all
        ranked candidates instead of just the best one.
        """
        persona_tag = character.lower()
        if persona_tag not in CHARACTERS:
            raise ValueError(f"Unknown character '{character}'. Available: {CHARACTERS}")

        prompt = self._build_prompt(user_text, persona_tag)
        candidates = self._generate_candidates(prompt, n)
        scores = self._score_candidates(candidates, persona_tag)

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
        """No reranking — plain single-sample generation baseline."""
        persona_tag = character.lower()
        prompt = self._build_prompt(user_text, persona_tag)
        candidates = self._generate_candidates(prompt, n=1)
        return candidates[0] if candidates else ""


# ── CLI ───────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--character", required=True)
    parser.add_argument("--prompt", required=True)
    parser.add_argument("--n", type=int, default=3)
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
        print(f"  persona score: {results[0].persona_score:.3f} (best of {len(results)})")
