"""
LoRA fine-tune a small instruction-tuned LM for persona-conditioned text generation.

Training format (ChatML):
    <|system|>You are {CHARACTER_TAG}. Respond only in their voice.</s>
    <|user|>{prompt}</s>
    <|assistant|>{character_line}</s>

For lines from the Cornell corpus we treat the line itself as both prompt context
and target completion (self-supervised), using the preceding conversation turn
(if available) as the user turn; otherwise a generic "Continue the conversation."

Usage:
    python train_generator.py
    python train_generator.py --base-model TinyLlama/TinyLlama-1.1B-Chat-v1.0
    python train_generator.py --epochs 5 --batch 8
"""
import argparse
import json

import torch
from datasets import load_from_disk
from peft import LoraConfig, TaskType, get_peft_model
from transformers import AutoModelForCausalLM, AutoTokenizer, BitsAndBytesConfig
from trl import DataCollatorForCompletionOnlyLM, SFTConfig, SFTTrainer

from config import (
    GENERATOR_BASE, GENERATOR_BATCH, GENERATOR_DIR, GENERATOR_EPOCHS,
    GENERATOR_GRAD_ACCUM, GENERATOR_LR, LORA_ALPHA, LORA_DROPOUT,
    LORA_R, LORA_TARGET_MODULES, PROCESSED_DIR, RESULTS_DIR,
)


RESPONSE_TEMPLATE = "<|assistant|>"
IGNORE_INDEX = -100


# ── Prompt formatting ────────────────────────────────────────────────────────

def format_example(character: str, line: str) -> str:
    """Wrap a dialogue line in ChatML for SFT."""
    tag = character.replace(" ", "_")
    return (
        f"<|system|>You are {tag}. Speak exactly in their voice — "
        f"vocabulary, rhythm, and characteristic phrases.\n</s>\n"
        f"<|user|>Continue the conversation.\n</s>\n"
        f"<|assistant|>{line}</s>"
    )


def prepare_dataset(characters: list[str]):
    dsd = load_from_disk(str(PROCESSED_DIR / "splits"))
    train_ds = dsd["train"]
    val_ds = dsd["val"]

    def _format(batch):
        texts = [
            format_example(char, line)
            for char, line in zip(batch["character"], batch["text"])
        ]
        return {"formatted": texts}

    train_fmt = train_ds.map(_format, batched=True, remove_columns=train_ds.column_names)
    val_fmt = val_ds.map(_format, batched=True, remove_columns=val_ds.column_names)
    return train_fmt, val_fmt


# ── LoRA setup ───────────────────────────────────────────────────────────────

def build_model(base_model: str):
    use_4bit = torch.cuda.is_available()

    bnb_config = None
    if use_4bit:
        bnb_config = BitsAndBytesConfig(
            load_in_4bit=True,
            bnb_4bit_quant_type="nf4",
            bnb_4bit_compute_dtype=torch.bfloat16,
            bnb_4bit_use_double_quant=True,
        )

    tokenizer = AutoTokenizer.from_pretrained(base_model, use_fast=True)
    tokenizer.pad_token = tokenizer.eos_token
    tokenizer.padding_side = "right"

    model = AutoModelForCausalLM.from_pretrained(
        base_model,
        quantization_config=bnb_config,
        device_map="auto" if use_4bit else None,
        torch_dtype=torch.float32 if not use_4bit else None,
    )

    lora_cfg = LoraConfig(
        task_type=TaskType.CAUSAL_LM,
        r=LORA_R,
        lora_alpha=LORA_ALPHA,
        lora_dropout=LORA_DROPOUT,
        target_modules=LORA_TARGET_MODULES,
        bias="none",
    )
    model = get_peft_model(model, lora_cfg)
    model.print_trainable_parameters()
    return model, tokenizer


# ── Training ──────────────────────────────────────────────────────────────────

def train(base_model: str, epochs: int, batch: int, lr: float) -> None:
    meta = json.loads((PROCESSED_DIR / "meta.json").read_text())
    characters = meta["characters"]

    print(f"[gen] base model: {base_model}")
    model, tokenizer = build_model(base_model)

    train_ds, val_ds = prepare_dataset(characters)

    # Only compute loss on completion tokens (after RESPONSE_TEMPLATE)
    collator = DataCollatorForCompletionOnlyLM(
        response_template=RESPONSE_TEMPLATE,
        tokenizer=tokenizer,
    )

    sft_cfg = SFTConfig(
        output_dir=str(GENERATOR_DIR),
        num_train_epochs=epochs,
        per_device_train_batch_size=batch,
        per_device_eval_batch_size=batch,
        gradient_accumulation_steps=GENERATOR_GRAD_ACCUM,
        learning_rate=lr,
        warmup_ratio=0.05,
        lr_scheduler_type="cosine",
        eval_strategy="epoch",
        save_strategy="epoch",
        load_best_model_at_end=True,
        metric_for_best_model="eval_loss",
        logging_steps=50,
        report_to="none",
        bf16=torch.cuda.is_available(),
        dataloader_num_workers=0,
        dataset_text_field="formatted",
        max_seq_length=256,
    )

    trainer = SFTTrainer(
        model=model,
        args=sft_cfg,
        train_dataset=train_ds,
        eval_dataset=val_ds,
        tokenizer=tokenizer,
        data_collator=collator,
    )

    print(f"[gen] training on {len(train_ds)} examples …")
    trainer.train()

    # Merge LoRA weights and save full model
    merged = trainer.model.merge_and_unload()
    merged.save_pretrained(str(GENERATOR_DIR / "merged"))
    tokenizer.save_pretrained(str(GENERATOR_DIR / "merged"))
    print(f"[gen] merged model saved to {GENERATOR_DIR / 'merged'}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--base-model", default=GENERATOR_BASE)
    parser.add_argument("--epochs", type=int, default=GENERATOR_EPOCHS)
    parser.add_argument("--batch", type=int, default=GENERATOR_BATCH)
    parser.add_argument("--lr", type=float, default=GENERATOR_LR)
    args = parser.parse_args()
    train(args.base_model, args.epochs, args.batch, args.lr)
