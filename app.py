"""
Gradio chatbox: select a movie character and converse with their persona.

Run:
    python app.py
    python app.py --share          # public Gradio link
    python app.py --no-rerank      # plain generation (no classifier reranking)
"""
import argparse
import json
import re
from pathlib import Path

import gradio as gr

from config import BEAM_N, CHARACTERS, PROCESSED_DIR
from inference import PersonaPipeline


# Character display info ──────────────────────────────────────────────────────
CHARACTER_INFO = {
    "HANNIBAL LECTER": {
        "emoji": "🎭",
        "desc": "Precise, erudite, theatrically menacing. Silence of the Lambs.",
        "example": "Tell me, what do you smell on the other side of that glass?",
    },
    "CLARICE": {
        "emoji": "🔍",
        "desc": "Earnest, professional, plain-spoken. FBI trainee.",
        "example": "I just need to know if I'm on the right track.",
    },
    "JOKER": {
        "emoji": "🃏",
        "desc": "Chaotic, clipped, darkly comic. The Dark Knight.",
        "example": "Why so serious?",
    },
    "FORREST": {
        "emoji": "🍫",
        "desc": "Simple, literal, heartfelt. Forrest Gump.",
        "example": "Mama always said life was like a box of chocolates.",
    },
    "JAMES BOND": {
        "emoji": "🍸",
        "desc": "Suave, dry-witted, controlled. British intelligence.",
        "example": "The name's Bond. James Bond.",
    },
}


def char_label(char: str) -> str:
    info = CHARACTER_INFO.get(char, {})
    emoji = info.get("emoji", "🎬")
    return f"{emoji} {char.title()}"


# Load pipeline lazily ────────────────────────────────────────────────────────
_pipeline: PersonaPipeline | None = None

def get_pipeline() -> PersonaPipeline:
    global _pipeline
    if _pipeline is None:
        _pipeline = PersonaPipeline()
    return _pipeline


# Chat logic ──────────────────────────────────────────────────────────────────

def respond(
    user_message: str,
    history: list[tuple[str, str]],
    character: str,
    n_candidates: int,
    use_rerank: bool,
) -> tuple[list[tuple[str, str]], str]:
    if not user_message.strip():
        return history, ""

    pipe = get_pipeline()
    try:
        if use_rerank:
            all_results = pipe.chat(
                user_message, character, n=n_candidates, return_all=True
            )
            reply = all_results[0].text
            score_info = (
                f"*(persona score: {all_results[0].persona_score:.3f} "
                f"— best of {len(all_results)})*"
            )
        else:
            reply = pipe.plain_generate(user_message, character)
            score_info = "*(no reranking)*"
    except Exception as e:
        reply = f"[Error: {e}]"
        score_info = ""

    full_reply = f"{reply}\n\n{score_info}" if score_info else reply
    history = history + [(user_message, full_reply)]
    return history, ""


def clear_chat():
    return [], ""


def update_example(character: str) -> str:
    return CHARACTER_INFO.get(character, {}).get("example", "")


# ── UI ────────────────────────────────────────────────────────────────────────

def build_ui(use_rerank_default: bool = True) -> gr.Blocks:
    # Resolve available characters from saved meta (may differ from config defaults)
    meta_path = PROCESSED_DIR / "meta.json"
    if meta_path.exists():
        chars = json.loads(meta_path.read_text())["characters"]
    else:
        chars = CHARACTERS

    char_choices = chars
    default_char = chars[0] if chars else ""

    with gr.Blocks(
        title="Movie Persona Chat",
        theme=gr.themes.Soft(),
        css=".gradio-container { max-width: 860px; margin: auto; }",
    ) as demo:
        gr.Markdown("## 🎬 Movie Persona Chat\nConverse with fine-tuned movie characters.")

        with gr.Row():
            with gr.Column(scale=1):
                character_dd = gr.Dropdown(
                    choices=[char_label(c) for c in char_choices],
                    value=char_label(default_char),
                    label="Character",
                )
                char_desc = gr.Markdown(
                    CHARACTER_INFO.get(default_char, {}).get("desc", "")
                )
                n_slider = gr.Slider(
                    minimum=1, maximum=8, value=BEAM_N, step=1,
                    label=f"Candidates (Best-of-N)",
                    visible=use_rerank_default,
                )
                rerank_toggle = gr.Checkbox(
                    value=use_rerank_default,
                    label="Enable classifier reranking",
                )
                example_btn = gr.Button("Try example prompt", size="sm")

            with gr.Column(scale=2):
                chatbot = gr.Chatbot(height=480, label="Conversation")
                msg_box = gr.Textbox(
                    placeholder="Type a message …",
                    label="Your message",
                    lines=2,
                )
                with gr.Row():
                    send_btn = gr.Button("Send", variant="primary")
                    clear_btn = gr.Button("Clear")

        # ── Hidden state: resolved character name ─────────────────────────
        char_state = gr.State(default_char)

        def resolve_char(label: str) -> tuple[str, str]:
            # strip emoji prefix  "🎭 Hannibal Lecter" → "HANNIBAL LECTER"
            name = re.sub(r"^[^\w]+", "", label).strip().upper()
            desc = CHARACTER_INFO.get(name, {}).get("desc", "")
            return name, desc

        def on_char_change(label: str):
            name, desc = resolve_char(label)
            return name, desc

        character_dd.change(
            on_char_change,
            inputs=[character_dd],
            outputs=[char_state, char_desc],
        )

        rerank_toggle.change(
            lambda v: gr.update(visible=v),
            inputs=[rerank_toggle],
            outputs=[n_slider],
        )

        def on_example(char: str) -> str:
            return CHARACTER_INFO.get(char, {}).get("example", "")

        example_btn.click(on_example, inputs=[char_state], outputs=[msg_box])

        send_btn.click(
            respond,
            inputs=[msg_box, chatbot, char_state, n_slider, rerank_toggle],
            outputs=[chatbot, msg_box],
        )
        msg_box.submit(
            respond,
            inputs=[msg_box, chatbot, char_state, n_slider, rerank_toggle],
            outputs=[chatbot, msg_box],
        )
        clear_btn.click(clear_chat, outputs=[chatbot, msg_box])

    return demo


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--share", action="store_true")
    parser.add_argument("--no-rerank", action="store_true")
    parser.add_argument("--port", type=int, default=7860)
    args = parser.parse_args()

    demo = build_ui(use_rerank_default=not args.no_rerank)
    demo.launch(share=args.share, server_port=args.port)
