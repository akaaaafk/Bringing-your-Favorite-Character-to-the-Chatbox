"""
Persona inference pipeline with Best-of-N classifier reranking.

Combines the LoRA-fine-tuned Qwen2.5-1.5B-Instruct generator with
Chelsea's RoBERTa persona classifier to generate and rerank candidate
responses for a selected character.

Usage (programmatic):
    from movie_persona.pipeline import PersonaPipeline
    pipe = PersonaPipeline()
    response = pipe.chat("How's your day going?", character="jack")

Usage (CLI):
    movie-persona --character "jack" --prompt "How's your day going?"
    movie-persona --character "bateman" --prompt "..." --n 5 --all
"""
import argparse
import re
from dataclasses import dataclass
from pathlib import Path

import torch
from transformers import AutoModelForCausalLM, AutoTokenizer
from peft import PeftModel

from .classifier import predict_persona_batch
from .paths import MODELS_DIR

BASE_MODEL = "Qwen/Qwen2.5-1.5B-Instruct"
ADAPTER_DIR = MODELS_DIR / "generator"
CHARACTERS = ["jack", "bateman", "alvy", "ben", "erin"]
# Keep recent turns only — small instruct model + short replies.
MAX_HISTORY_MESSAGES = 8

# short name, full name — used for identity questions
PERSONA_IDENTITY: dict[str, tuple[str, str]] = {
    "alvy": ("Alvy", "Alvy Singer"),
    "jack": ("Jack", "Jack"),
    "bateman": ("Patrick", "Patrick Bateman"),
    "ben": ("Ben", "Benjamin Braddock"),
    "erin": ("Erin", "Erin Brockovich"),
}

# Manner / diction only — content should still answer like a normal conversation.
PERSONA_DELIVERY: dict[str, str] = {
    "alvy": (
        "Neurotic, self-deprecating, tangents and stammers; still give a real answer."
    ),
    "jack": (
        "Deadpan, clipped, dry irony; still give a real answer without theatrical dodge."
    ),
    "bateman": (
        "Cold, precise, polished diction; still give a real answer, not cryptic evasion."
    ),
    "ben": (
        "Hesitant, soft, a little awkward; still give a real answer eventually."
    ),
    "erin": (
        "Blunt, direct, a little fiery; still give a real, useful answer."
    ),
}

# Hard answers for "what's your name" / "who are you" — all five personas.
IDENTITY_REPLY: dict[str, str] = {
    "alvy": "I'm Alvy Singer.",
    "jack": "I'm Jack.",
    "bateman": "I'm Patrick Bateman.",
    "ben": "I'm Benjamin Braddock.",
    "erin": "I'm Erin Brockovich.",
}

# Reject filler after "I'm …" so we don't treat "I'm sorry" as a name.
_NAME_STOP = frozenset(
    {
        "a",
        "an",
        "the",
        "not",
        "just",
        "so",
        "really",
        "sorry",
        "fine",
        "good",
        "okay",
        "ok",
        "here",
        "going",
        "doing",
        "feeling",
        "back",
        "home",
        "there",
        "glad",
        "sure",
        "confused",
        "lost",
        "scared",
        "happy",
        "ready",
        "done",
        "trying",
        "kidding",
        "joking",
        "alone",
        "late",
        "early",
        "busy",
        "tired",
        "hungry",
        "cold",
        "hot",
        "new",
        "old",
        "from",
        "with",
        "about",
        "into",
        "over",
        "under",
    }
)

_NAME_PATTERNS = (
    re.compile(r"\bmy name is ([A-Za-z][A-Za-z\-']{1,30})\b", re.I),
    re.compile(r"\bi(?:'| a)?m ([A-Za-z][A-Za-z\-']{1,30})\b", re.I),
    re.compile(r"\bcall me ([A-Za-z][A-Za-z\-']{1,30})\b", re.I),
)

# "im shawn" without apostrophe / "i am shawn"
_NAME_PATTERNS_LOOSE = (
    re.compile(r"\bim ([A-Za-z][A-Za-z\-']{1,30})\b", re.I),
    re.compile(r"\bi am ([A-Za-z][A-Za-z\-']{1,30})\b", re.I),
)

_ASKS_USER_NAME = re.compile(
    r"\b(?:what(?:'s| is|s)? my name|who am i|do you remember my name|"
    r"what was my name|remind me (?:of )?my name)\b",
    re.I,
)

_ASKS_SELF_NAME = re.compile(
    r"\b(?:what(?:'s| is|s)? your name|who are you|"
    r"tell me your name|your name(?: again)?|"
    r"what(?:'s| is|s)? you called)\b",
    re.I,
)


def extract_user_names(history: list[dict] | None) -> list[str]:
    """Pull user-stated first names from prior user turns (oldest → newest)."""
    names: list[str] = []
    seen: set[str] = set()
    for turn in history or []:
        if turn.get("role") != "user":
            continue
        text = (turn.get("text") or "").strip()
        if not text:
            continue
        for pat in (*_NAME_PATTERNS, *_NAME_PATTERNS_LOOSE):
            for match in pat.finditer(text):
                raw = match.group(1)
                key = raw.lower()
                if key in _NAME_STOP or key in seen:
                    continue
                if not raw[0].isalpha():
                    continue
                seen.add(key)
                names.append(raw[0].upper() + raw[1:])
    return names


def _mentions_persona(text: str, persona_tag: str) -> bool:
    short, full = PERSONA_IDENTITY[persona_tag]
    text_l = text.lower()
    if short.lower() in text_l or full.lower() in text_l:
        return True
    # e.g. "Bateman" from "Patrick Bateman"
    for part in full.split():
        if len(part) > 2 and part.lower() in text_l:
            return True
    return False


def grounding_bonus(
    candidate: str,
    user_text: str,
    user_names: list[str],
    persona_tag: str,
) -> float:
    """
    Prefer replies that answer identity questions with the right names.

    Persona scores are ~0–1; a large bonus makes grounded answers win rerank.
    """
    text_l = candidate.lower()
    asks_user = bool(_ASKS_USER_NAME.search(user_text))
    asks_self = bool(_ASKS_SELF_NAME.search(user_text))

    if asks_self:
        has_self = _mentions_persona(candidate, persona_tag)
        # Hard preference for an explicit self-ID line.
        text_l = candidate.lower().strip()
        short, full = PERSONA_IDENTITY[persona_tag]
        explicit = (
            text_l.startswith("i'm ")
            or text_l.startswith("i am ")
            or full.lower() in text_l
        )
        bonus = 4.0 if (has_self and explicit) else (3.0 if has_self else -2.0)
        if user_names and any(n.lower() in text_l for n in user_names) and not has_self:
            bonus -= 1.5
        return bonus

    if user_names:
        mentioned = any(n.lower() in text_l for n in user_names)
        if asks_user:
            return 3.0 if mentioned else -1.0
        return 0.35 if mentioned else 0.0
    return 0.0

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
      3. Grounding bonus + persona score pick the final reply.
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

        print("[pipeline] classifier interface ready")

    # ── Generation ────────────────────────────────────────────────────────────

    def _build_prompt(
        self,
        user_text: str,
        persona_tag: str,
        history: list[dict] | None = None,
    ) -> str:
        user_names = extract_user_names(history)
        short, full = PERSONA_IDENTITY[persona_tag]
        delivery = PERSONA_DELIVERY.get(persona_tag, "")
        system = (
            f"You are {full} (also called {short}) in a normal back-and-forth chat. "
            f"Priority 1: answer the user's latest message the way a real person would—"
            f"clear, on-topic, useful. If they ask a simple question, give a simple answer. "
            f"Priority 2: keep their manner of speaking: {delivery} "
            f"Use natural contractions and spoken rhythm; a little character flavor is good, "
            f"but do not monologue, dodge, or turn every reply into a movie scene. "
            f"Do not invent random plot twists or camera-experiment bits unless asked. "
            f"Do not wrap lines in stage-direction brackets. "
            f"Your own name is {full}. If asked your name or who you are, say you are {short} "
            f"(or {full}) in the first sentence—never dodge. "
            f"Do not give the user's name when asked for yours. "
            f"Use the conversation history to stay consistent and answer follow-ups."
        )
        if user_names:
            joined = ", ".join(user_names)
            system += (
                f" Known facts from this conversation (treat as true): "
                f"the user's name is {joined}. "
                f"If asked the user's name, answer with {joined} — "
                f"do not invent a different name."
            )
        parts = [f"<|im_start|>system\n{system}<|im_end|>\n"]
        for turn in (history or [])[-MAX_HISTORY_MESSAGES:]:
            role = turn.get("role")
            text = (turn.get("text") or "").strip()
            if role not in ("user", "assistant") or not text:
                continue
            parts.append(f"<|im_start|>{role}\n{text}<|im_end|>\n")
        parts.append(f"<|im_start|>user\n{user_text}<|im_end|>\n")
        parts.append("<|im_start|>assistant\n")
        return "".join(parts)

    def _generate_candidates(
        self,
        prompt: str,
        n: int,
        max_new_tokens: int = 80,
        temperature: float = 0.9,
    ) -> list[str]:
        inputs = self.gen_tokenizer(prompt, return_tensors="pt").to(self.device)
        with torch.no_grad():
            outputs = self.gen_model.generate(
                **inputs,
                max_new_tokens=max_new_tokens,
                do_sample=True,
                temperature=temperature,
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
        history: list[dict] | None = None,
    ) -> str | list[CandidateResult]:
        """
        Generate n candidates and return the one with the highest classifier
        score for the target character. If return_all=True, returns all
        ranked candidates instead of just the best one.
        """
        persona_tag = character.lower()
        if persona_tag not in CHARACTERS:
            raise ValueError(f"Unknown character '{character}'. Available: {CHARACTERS}")

        # Identity questions: never let dramatic sampling dodge the name (any persona).
        if _ASKS_SELF_NAME.search(user_text):
            reply = IDENTITY_REPLY[persona_tag]
            if return_all:
                return [CandidateResult(text=reply, persona_score=1.0, rank=1)]
            return reply

        user_names = extract_user_names(history)
        prompt = self._build_prompt(user_text, persona_tag, history=history)
        asks_user = bool(_ASKS_USER_NAME.search(user_text))
        temperature = 0.7 if asks_user else 0.9
        candidates = self._generate_candidates(prompt, n, temperature=temperature)

        if asks_user and user_names:
            if not any(
                any(n.lower() in c.lower() for n in user_names) for c in candidates
            ):
                candidates = list(candidates) + [f"{user_names[-1]}."]

        persona_scores = self._score_candidates(candidates, persona_tag)

        scored = [
            (
                t,
                s,
                s + grounding_bonus(t, user_text, user_names, persona_tag),
            )
            for t, s in zip(candidates, persona_scores)
        ]
        scored.sort(key=lambda x: x[2], reverse=True)
        ranked = [
            CandidateResult(text=t, persona_score=s, rank=i + 1)
            for i, (t, s, _) in enumerate(scored)
        ]

        if return_all:
            return ranked
        return ranked[0].text if ranked else ""

    def plain_generate(
        self,
        user_text: str,
        character: str,
        history: list[dict] | None = None,
    ) -> str:
        """No reranking — plain single-sample generation baseline."""
        persona_tag = character.lower()
        if _ASKS_SELF_NAME.search(user_text):
            return IDENTITY_REPLY[persona_tag]
        prompt = self._build_prompt(user_text, persona_tag, history=history)
        asks_user = bool(_ASKS_USER_NAME.search(user_text))
        temperature = 0.7 if asks_user else 0.9
        candidates = self._generate_candidates(prompt, n=1, temperature=temperature)
        if asks_user:
            user_names = extract_user_names(history)
            if user_names and not any(
                any(n.lower() in c.lower() for n in user_names) for c in candidates
            ):
                return f"{user_names[-1]}."
        return candidates[0] if candidates else ""
# ── CLI ───────────────────────────────────────────────────────────────────────

def main() -> None:
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


if __name__ == "__main__":
    main()
