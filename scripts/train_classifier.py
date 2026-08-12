"""
Fine-tune a RoBERTa-base multi-class classifier to identify which of the
5 selected characters a line of dialogue belongs to.

Reads:
    data/processed/train.csv              (real lines)
    data/processed/train_hard_negatives.csv (Claude-synthesized, optional)
    data/processed/val.csv
    data/processed/test.csv
    data/processed/selected_characters.json (character_name -> persona_tag)

Writes:
    models/classifier/                    (HF checkpoint — auto-detected by
                                            persona_classifier/predict.py,
                                            which is what Phase 3 imports)
    results/classifier_metrics.json
    results/classifier_confusion_matrix.png

Usage:
    uv run scripts/train_classifier.py                  # real + synthetic
    uv run scripts/train_classifier.py --no-synthetic    # ablation: real only
"""

import argparse
import json
from pathlib import Path

import numpy as np
import pandas as pd
import torch
from sklearn.metrics import accuracy_score, f1_score, confusion_matrix
import matplotlib.pyplot as plt
import seaborn as sns
from transformers import (
    AutoTokenizer,
    AutoModelForSequenceClassification,
    Trainer,
    TrainingArguments,
)
from datasets import Dataset

PROCESSED_DIR = Path(__file__).resolve().parent.parent / "data" / "processed"
MODELS_DIR = Path(__file__).resolve().parent.parent / "models"
RESULTS_DIR = Path(__file__).resolve().parent.parent / "results"

BASE_MODEL = "roberta-base"


def load_persona_tag_map() -> dict[str, str]:
    with open(PROCESSED_DIR / "selected_characters.json") as f:
        characters = json.load(f)
    return {c["character_name"]: c["persona_tag"] for c in characters}


def build_split(
    csv_path: Path, persona_tag_map: dict[str, str], is_synthetic: bool
) -> pd.DataFrame:
    df = pd.read_csv(csv_path)
    df = df[["text", "character_name"]].copy()
    df["is_synthetic"] = is_synthetic
    df["persona_tag"] = df["character_name"].map(persona_tag_map)

    unmapped = df[df["persona_tag"].isnull()]
    if len(unmapped):
        bad_names = unmapped["character_name"].unique().tolist()
        raise ValueError(
            f"{csv_path.name}: {len(unmapped)} rows have character_name(s) "
            f"{bad_names} not present in selected_characters.json. "
            "Check that selected_characters.json is up to date with your "
            "final 5 characters before training."
        )
    return df


def load_training_data(persona_tag_map: dict[str, str], use_synthetic: bool) -> pd.DataFrame:
    real = build_split(PROCESSED_DIR / "train.csv", persona_tag_map, is_synthetic=False)
    if not use_synthetic:
        return real

    synth_path = PROCESSED_DIR / "train_hard_negatives.csv"
    if not synth_path.exists():
        print(f"WARNING: {synth_path} not found, training on real data only.")
        return real

    synth = build_split(synth_path, persona_tag_map, is_synthetic=True)
    combined = pd.concat([real, synth], ignore_index=True)
    print(
        f"Training data: {len(real)} real + {len(synth)} synthetic = "
        f"{len(combined)} total rows"
    )
    return combined


def compute_metrics(eval_pred):
    logits, labels = eval_pred
    preds = np.argmax(logits, axis=-1)
    return {
        "accuracy": accuracy_score(labels, preds),
        "macro_f1": f1_score(labels, preds, average="macro"),
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--no-synthetic",
        action="store_true",
        help="Ablation mode: train on real data only, skip hard negatives.",
    )
    parser.add_argument("--epochs", type=int, default=4)
    parser.add_argument("--batch-size", type=int, default=8)
    parser.add_argument("--lr", type=float, default=2e-5)
    args = parser.parse_args()

    use_synthetic = not args.no_synthetic
    run_name = "persona_classifier" if use_synthetic else "persona_classifier_no_synthetic"
    # Inference loads models/classifier/ (see persona_classifier/predict.py)
    output_dir = MODELS_DIR / "classifier"

    persona_tag_map = load_persona_tag_map()
    persona_tags = sorted(set(persona_tag_map.values()))
    label2id = {tag: i for i, tag in enumerate(persona_tags)}
    id2label = {i: tag for tag, i in label2id.items()}
    print(f"Labels: {persona_tags}")

    train_df = load_training_data(persona_tag_map, use_synthetic)
    val_df = build_split(PROCESSED_DIR / "val.csv", persona_tag_map, is_synthetic=False)
    test_df = build_split(PROCESSED_DIR / "test.csv", persona_tag_map, is_synthetic=False)

    train_df["label"] = train_df["persona_tag"].map(label2id)
    val_df["label"] = val_df["persona_tag"].map(label2id)
    test_df["label"] = test_df["persona_tag"].map(label2id)

    tokenizer = AutoTokenizer.from_pretrained(BASE_MODEL)

    def tokenize(batch):
        return tokenizer(batch["text"], truncation=True, padding="max_length", max_length=64)

    train_ds = Dataset.from_pandas(train_df[["text", "label"]]).map(tokenize, batched=True)
    val_ds = Dataset.from_pandas(val_df[["text", "label"]]).map(tokenize, batched=True)
    test_ds = Dataset.from_pandas(test_df[["text", "label"]]).map(tokenize, batched=True)

    model = AutoModelForSequenceClassification.from_pretrained(
        BASE_MODEL,
        num_labels=len(persona_tags),
        id2label=id2label,
        label2id=label2id,
    )

    training_args = TrainingArguments(
        output_dir=str(output_dir / "checkpoints"),
        num_train_epochs=args.epochs,
        per_device_train_batch_size=args.batch_size,
        per_device_eval_batch_size=args.batch_size,
        learning_rate=args.lr,
        eval_strategy="epoch",
        save_strategy="epoch",
        load_best_model_at_end=True,
        metric_for_best_model="macro_f1",
        logging_steps=10,
        report_to="none",
    )

    trainer = Trainer(
        model=model,
        args=training_args,
        train_dataset=train_ds,
        eval_dataset=val_ds,
        compute_metrics=compute_metrics,
    )

    print(f"\nTraining ({'with' if use_synthetic else 'without'} synthetic data)...")
    trainer.train()

    # Final eval on the untouched test set — this is the number that goes
    # in the report, not the validation metric used for model selection.
    print("\nEvaluating on held-out test set...")
    test_output = trainer.predict(test_ds)
    test_preds = np.argmax(test_output.predictions, axis=-1)
    test_labels = test_output.label_ids

    accuracy = accuracy_score(test_labels, test_preds)
    macro_f1 = f1_score(test_labels, test_preds, average="macro")
    per_class_f1 = f1_score(test_labels, test_preds, average=None)

    print(f"Test accuracy: {accuracy:.3f}")
    print(f"Test macro-F1: {macro_f1:.3f}")

    RESULTS_DIR.mkdir(parents=True, exist_ok=True)
    metrics = {
        "run_name": run_name,
        "used_synthetic_data": use_synthetic,
        "test_accuracy": accuracy,
        "test_macro_f1": macro_f1,
        "per_class_f1": {persona_tags[i]: f for i, f in enumerate(per_class_f1)},
    }
    metrics_path = RESULTS_DIR / f"{run_name}_metrics.json"
    with open(metrics_path, "w") as f:
        json.dump(metrics, f, indent=2)
    print(f"Metrics saved -> {metrics_path}")

    # Confusion matrix
    cm = confusion_matrix(test_labels, test_preds)
    plt.figure(figsize=(7, 6))
    sns.heatmap(
        cm, annot=True, fmt="d", cmap="Blues",
        xticklabels=persona_tags, yticklabels=persona_tags,
    )
    plt.xlabel("Predicted")
    plt.ylabel("True")
    plt.title(f"Confusion Matrix ({run_name})")
    plt.tight_layout()
    cm_path = RESULTS_DIR / f"{run_name}_confusion_matrix.png"
    plt.savefig(cm_path, dpi=150)
    print(f"Confusion matrix saved -> {cm_path}")

    # Save model + tokenizer to the path persona_classifier/predict.py
    # auto-detects — this is what unblocks Phase 3 with the real model.
    output_dir.mkdir(parents=True, exist_ok=True)
    trainer.save_model(str(output_dir))
    tokenizer.save_pretrained(str(output_dir))
    print(f"Model saved -> {output_dir}")


if __name__ == "__main__":
    main()
