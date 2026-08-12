"""
LoRA-fine-tune Qwen2.5-1.5B-Instruct as the persona generator.

Reads:
    data/processed/training_pairs.csv   (from scripts/build_training_pairs.py)

Writes:
    models/generator/                   (LoRA adapter — loaded by inference.py)

Usage:
    python scripts/train_generator.py
    python scripts/train_generator.py --epochs 3 --batch-size 4
"""

from __future__ import annotations

import argparse
from pathlib import Path

import pandas as pd
import torch
from datasets import Dataset
from peft import LoraConfig, TaskType, get_peft_model
from transformers import (
    AutoModelForCausalLM,
    AutoTokenizer,
    DataCollatorForLanguageModeling,
    Trainer,
    TrainingArguments,
)

ROOT = Path(__file__).resolve().parent.parent
PAIRS_PATH = ROOT / "data" / "processed" / "training_pairs.csv"
ADAPTER_DIR = ROOT / "models" / "generator"

BASE_MODEL = "Qwen/Qwen2.5-1.5B-Instruct"


def format_example(row: pd.Series) -> dict[str, str]:
    system = (
        f"You are {row['persona_tag']}. Respond only in their voice, "
        "matching their vocabulary and speech patterns."
    )
    text = (
        f"<|im_start|>system\n{system}<|im_end|>\n"
        f"<|im_start|>user\n{row['prompt']}<|im_end|>\n"
        f"<|im_start|>assistant\n{row['response']}<|im_end|>"
    )
    return {"text": text}


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--epochs", type=int, default=3)
    parser.add_argument("--batch-size", type=int, default=4)
    parser.add_argument("--lr", type=float, default=2e-4)
    parser.add_argument("--max-length", type=int, default=256)
    args = parser.parse_args()

    if not PAIRS_PATH.exists():
        raise FileNotFoundError(
            f"{PAIRS_PATH} not found. Run scripts/build_training_pairs.py first."
        )

    df = pd.read_csv(PAIRS_PATH).dropna()
    print(f"Loaded {len(df):,} training pairs")

    formatted = df.apply(format_example, axis=1, result_type="expand")
    dataset = Dataset.from_pandas(formatted)
    print(dataset[0]["text"])

    tokenizer = AutoTokenizer.from_pretrained(BASE_MODEL)
    if tokenizer.pad_token is None:
        tokenizer.pad_token = tokenizer.eos_token

    dtype = torch.bfloat16 if torch.cuda.is_available() else torch.float32
    model = AutoModelForCausalLM.from_pretrained(
        BASE_MODEL,
        torch_dtype=dtype,
        device_map="auto" if torch.cuda.is_available() else None,
    )

    lora_config = LoraConfig(
        task_type=TaskType.CAUSAL_LM,
        r=16,
        lora_alpha=32,
        lora_dropout=0.05,
        target_modules=["q_proj", "v_proj", "k_proj", "o_proj"],
        bias="none",
    )
    model = get_peft_model(model, lora_config)
    model.print_trainable_parameters()

    def tokenize_function(examples):
        return tokenizer(
            examples["text"],
            truncation=True,
            max_length=args.max_length,
            padding="max_length",
        )

    tokenized_dataset = dataset.map(
        tokenize_function, batched=True, remove_columns=["text"]
    )
    data_collator = DataCollatorForLanguageModeling(tokenizer=tokenizer, mlm=False)

    use_bf16 = torch.cuda.is_available() and torch.cuda.is_bf16_supported()
    training_args = TrainingArguments(
        output_dir=str(ADAPTER_DIR / "checkpoints"),
        num_train_epochs=args.epochs,
        per_device_train_batch_size=args.batch_size,
        gradient_accumulation_steps=4,
        learning_rate=args.lr,
        warmup_ratio=0.05,
        lr_scheduler_type="cosine",
        logging_steps=10,
        save_strategy="epoch",
        bf16=use_bf16,
        report_to="none",
    )

    trainer = Trainer(
        model=model,
        args=training_args,
        train_dataset=tokenized_dataset,
        data_collator=data_collator,
    )

    print("Starting training...")
    trainer.train()

    ADAPTER_DIR.mkdir(parents=True, exist_ok=True)
    model.save_pretrained(str(ADAPTER_DIR))
    tokenizer.save_pretrained(str(ADAPTER_DIR))
    print(f"Adapter saved to {ADAPTER_DIR}")


if __name__ == "__main__":
    main()
