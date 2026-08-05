"""
Fine-tune RoBERTa-base as a multi-class persona classifier.

Training set = real dialogue lines + Claude hard-negative rewrites.
Hard negatives receive a down-weighted loss via a sample_weight column
(implemented through a custom Trainer subclass).

Usage:
    python train_classifier.py
    python train_classifier.py --no-hard-negs   # real lines only
    python train_classifier.py --epochs 3 --batch 16
"""
import argparse
import json
from pathlib import Path

import numpy as np
import torch
from datasets import Dataset, DatasetDict, concatenate_datasets, load_from_disk
from transformers import (
    AutoModelForSequenceClassification,
    AutoTokenizer,
    DataCollatorWithPadding,
    Trainer,
    TrainerCallback,
    TrainingArguments,
)

from config import (
    CLASSIFIER_BASE, CLASSIFIER_BATCH, CLASSIFIER_DIR, CLASSIFIER_EPOCHS,
    CLASSIFIER_LR, CLASSIFIER_MAX_LEN, CLASSIFIER_WARMUP_RATIO,
    HARD_NEG_WEIGHT, NEGATIVES_FILE, PROCESSED_DIR, RESULTS_DIR,
)


# ── Weighted loss trainer ─────────────────────────────────────────────────────

class WeightedTrainer(Trainer):
    """Apply per-sample loss weights stored in 'weight' feature."""

    def compute_loss(self, model, inputs, return_outputs=False, **kwargs):
        weights = inputs.pop("weight", None)
        labels = inputs.get("labels")
        outputs = model(**inputs)
        logits = outputs.logits

        loss_fct = torch.nn.CrossEntropyLoss(reduction="none")
        loss = loss_fct(logits.view(-1, model.config.num_labels), labels.view(-1))

        if weights is not None:
            loss = (loss * weights.float()).mean()
        else:
            loss = loss.mean()

        return (loss, outputs) if return_outputs else loss


# ── Metrics ───────────────────────────────────────────────────────────────────

def compute_metrics(eval_pred):
    from sklearn.metrics import f1_score
    logits, labels = eval_pred
    preds = np.argmax(logits, axis=-1)
    acc = (preds == labels).mean()
    f1_macro = f1_score(labels, preds, average="macro")
    f1_weighted = f1_score(labels, preds, average="weighted")
    return {"accuracy": acc, "f1_macro": f1_macro, "f1_weighted": f1_weighted}


# ── Data preparation ──────────────────────────────────────────────────────────

def load_data(use_hard_negs: bool) -> tuple[Dataset, Dataset, Dataset, list[str]]:
    meta = json.loads((PROCESSED_DIR / "meta.json").read_text())
    characters = meta["characters"]

    dsd: DatasetDict = load_from_disk(str(PROCESSED_DIR / "splits"))
    train_ds = dsd["train"].map(lambda ex: {"weight": 1.0})
    val_ds = dsd["val"]
    test_ds = dsd["test"]

    if use_hard_negs and NEGATIVES_FILE.exists():
        with open(NEGATIVES_FILE) as f:
            negs = [json.loads(l) for l in f if l.strip()]
        label2id = meta["label2id"]
        neg_rows = [
            {"text": r["text"], "label": label2id[r["character"]],
             "character": r["character"], "weight": HARD_NEG_WEIGHT}
            for r in negs if r["character"] in label2id
        ]
        if neg_rows:
            neg_ds = Dataset.from_list(neg_rows)
            train_ds = concatenate_datasets([train_ds, neg_ds])
            print(f"[cls] added {len(neg_rows)} hard negatives to train → {len(train_ds)} total")
    elif use_hard_negs:
        print("[cls] no hard_negatives.jsonl found; run generate_hard_negatives.py first")

    # ensure 'weight' column exists on val/test (not used in loss but needed for collator)
    val_ds = val_ds.map(lambda ex: {"weight": 1.0})
    test_ds = test_ds.map(lambda ex: {"weight": 1.0})

    return train_ds, val_ds, test_ds, characters


def tokenize(ds: Dataset, tokenizer, remove_columns: list[str]) -> Dataset:
    def _tok(batch):
        enc = tokenizer(
            batch["text"],
            truncation=True,
            max_length=CLASSIFIER_MAX_LEN,
            padding=False,
        )
        enc["weight"] = batch["weight"]
        return enc

    return ds.map(
        _tok,
        batched=True,
        remove_columns=remove_columns,
    )


# ── Main ──────────────────────────────────────────────────────────────────────

def train(epochs: int, batch: int, use_hard_negs: bool, lr: float) -> None:
    train_ds, val_ds, test_ds, characters = load_data(use_hard_negs)
    num_labels = len(characters)

    tokenizer = AutoTokenizer.from_pretrained(CLASSIFIER_BASE)

    remove_cols = [c for c in train_ds.column_names if c not in ("label", "weight")]
    train_tok = tokenize(train_ds, tokenizer, remove_cols)
    val_tok = tokenize(val_ds, tokenizer, remove_cols)

    model = AutoModelForSequenceClassification.from_pretrained(
        CLASSIFIER_BASE,
        num_labels=num_labels,
        id2label={i: c for i, c in enumerate(characters)},
        label2id={c: i for i, c in enumerate(characters)},
    )

    args = TrainingArguments(
        output_dir=str(CLASSIFIER_DIR),
        num_train_epochs=epochs,
        per_device_train_batch_size=batch,
        per_device_eval_batch_size=batch * 2,
        learning_rate=lr,
        warmup_ratio=CLASSIFIER_WARMUP_RATIO,
        weight_decay=0.01,
        eval_strategy="epoch",
        save_strategy="epoch",
        load_best_model_at_end=True,
        metric_for_best_model="f1_macro",
        logging_steps=50,
        report_to="none",
        fp16=torch.cuda.is_available(),
        dataloader_num_workers=0,
    )

    collator = DataCollatorWithPadding(tokenizer, pad_to_multiple_of=8)

    trainer = WeightedTrainer(
        model=model,
        args=args,
        train_dataset=train_tok,
        eval_dataset=val_tok,
        tokenizer=tokenizer,
        data_collator=collator,
        compute_metrics=compute_metrics,
    )

    print(f"[cls] training on {len(train_tok)} examples ({num_labels} classes) …")
    trainer.train()

    model.save_pretrained(str(CLASSIFIER_DIR))
    tokenizer.save_pretrained(str(CLASSIFIER_DIR))
    print(f"[cls] model saved to {CLASSIFIER_DIR}")

    # quick test-set evaluation
    test_tok = tokenize(test_ds, tokenizer, remove_cols)
    test_results = trainer.predict(test_tok)
    print(f"\n[cls] test metrics: {test_results.metrics}")
    (RESULTS_DIR / "classifier_test_metrics.json").write_text(
        json.dumps(test_results.metrics, indent=2)
    )


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--epochs", type=int, default=CLASSIFIER_EPOCHS)
    parser.add_argument("--batch", type=int, default=CLASSIFIER_BATCH)
    parser.add_argument("--lr", type=float, default=CLASSIFIER_LR)
    parser.add_argument("--no-hard-negs", action="store_true")
    args = parser.parse_args()
    train(args.epochs, args.batch, not args.no_hard_negs, args.lr)
