"""
Evaluate the fine-tuned persona classifier and analyse stylistic features.

Outputs (all saved to results/):
  - classifier_report.txt          — per-class precision / recall / F1
  - confusion_matrix.png           — heatmap
  - top_tokens_per_class.json      — highest-weight tokens per class (embedding analysis)
  - misclassified_examples.jsonl   — worst confident mistakes for error analysis

Usage:
    python evaluate_classifier.py
    python evaluate_classifier.py --split val   # use val instead of test
"""
import argparse
import json
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np
import seaborn as sns
import torch
from datasets import load_from_disk
from transformers import AutoModelForSequenceClassification, AutoTokenizer, pipeline

from config import CLASSIFIER_DIR, PROCESSED_DIR, RESULTS_DIR


def load_model_and_tokenizer():
    tokenizer = AutoTokenizer.from_pretrained(str(CLASSIFIER_DIR))
    model = AutoModelForSequenceClassification.from_pretrained(str(CLASSIFIER_DIR))
    model.eval()
    return model, tokenizer


def get_predictions(texts: list[str], model, tokenizer, batch_size: int = 64):
    device = "cuda" if torch.cuda.is_available() else "cpu"
    model = model.to(device)
    all_logits = []
    for i in range(0, len(texts), batch_size):
        batch = texts[i: i + batch_size]
        enc = tokenizer(batch, return_tensors="pt", truncation=True,
                        max_length=128, padding=True).to(device)
        with torch.no_grad():
            logits = model(**enc).logits
        all_logits.append(logits.cpu())
    logits = torch.cat(all_logits, dim=0)
    probs = torch.softmax(logits, dim=-1).numpy()
    preds = np.argmax(probs, axis=-1)
    return preds, probs


def save_confusion_matrix(cm: np.ndarray, labels: list[str], path: Path) -> None:
    fig, ax = plt.subplots(figsize=(8, 7))
    sns.heatmap(
        cm, annot=True, fmt="d", cmap="Blues",
        xticklabels=labels, yticklabels=labels, ax=ax,
    )
    ax.set_xlabel("Predicted", fontsize=11)
    ax.set_ylabel("True", fontsize=11)
    ax.set_title("Persona Classifier — Confusion Matrix", fontsize=13)
    short_labels = [c.split()[-1] for c in labels]  # last word for readability
    ax.set_xticklabels(short_labels, rotation=45, ha="right")
    ax.set_yticklabels(short_labels, rotation=0)
    fig.tight_layout()
    fig.savefig(str(path), dpi=150)
    plt.close(fig)
    print(f"[eval] confusion matrix saved to {path}")


def top_tokens_per_class(model, tokenizer, top_k: int = 20) -> dict[str, list[str]]:
    """
    Approximate: project each vocab token through the classifier head and rank
    by the class logit. This is only meaningful for linear / shallow heads but
    gives a quick interpretability signal.
    """
    id2label = model.config.id2label
    # classifier head weight: shape (num_labels, hidden_size)
    head_weight = model.classifier.out_proj.weight.detach().cpu()

    # embed every token in the vocabulary via the word embedding layer
    vocab_size = tokenizer.vocab_size
    token_ids = torch.arange(vocab_size)
    with torch.no_grad():
        embeddings = model.roberta.embeddings.word_embeddings(token_ids)  # (V, H)
    scores = embeddings @ head_weight.T  # (V, num_labels)

    result = {}
    for label_id, label_name in id2label.items():
        top_ids = scores[:, label_id].topk(top_k).indices.tolist()
        tokens = [tokenizer.convert_ids_to_tokens(tid) for tid in top_ids]
        # skip special / subword tokens for readability
        tokens = [t for t in tokens if not t.startswith("Ġ") is False or len(t) > 3]
        # decode Ġ prefix (RoBERTa space marker)
        tokens = [t.lstrip("Ġ") for t in tokens]
        result[label_name] = tokens[:top_k]

    return result


def run(split: str = "test") -> None:
    meta = json.loads((PROCESSED_DIR / "meta.json").read_text())
    characters: list[str] = meta["characters"]
    label2id: dict[str, int] = meta["label2id"]
    id2label = {v: k for k, v in label2id.items()}

    dsd = load_from_disk(str(PROCESSED_DIR / "splits"))
    ds = dsd[split]
    texts = ds["text"]
    true_labels = np.array(ds["label"])

    model, tokenizer = load_model_and_tokenizer()
    preds, probs = get_predictions(texts, model, tokenizer)

    # ── Classification report ──────────────────────────────────────────────
    from sklearn.metrics import classification_report, confusion_matrix

    report = classification_report(true_labels, preds, target_names=characters)
    print(f"\n── {split} set ─────────────────────────────────────\n{report}")
    (RESULTS_DIR / "classifier_report.txt").write_text(
        f"Split: {split}\n\n{report}"
    )

    # ── Confusion matrix ───────────────────────────────────────────────────
    cm = confusion_matrix(true_labels, preds, labels=list(range(len(characters))))
    save_confusion_matrix(cm, characters, RESULTS_DIR / "confusion_matrix.png")

    # ── Most confident mistakes ────────────────────────────────────────────
    mistakes = []
    for i, (true, pred, prob) in enumerate(zip(true_labels, preds, probs)):
        if true != pred:
            mistakes.append({
                "text": texts[i],
                "true": id2label[int(true)],
                "predicted": id2label[int(pred)],
                "confidence": float(prob[pred]),
            })
    mistakes.sort(key=lambda x: x["confidence"], reverse=True)
    with open(RESULTS_DIR / "misclassified_examples.jsonl", "w") as f:
        for m in mistakes[:200]:
            f.write(json.dumps(m) + "\n")
    print(f"[eval] {len(mistakes)} mistakes; top-200 saved")

    # ── Token analysis ────────────────────────────────────────────────────
    try:
        top_tokens = top_tokens_per_class(model, tokenizer)
        (RESULTS_DIR / "top_tokens_per_class.json").write_text(
            json.dumps(top_tokens, indent=2, ensure_ascii=False)
        )
        print("[eval] top tokens per class:")
        for char, tokens in top_tokens.items():
            print(f"  {char}: {', '.join(tokens[:10])}")
    except AttributeError:
        print("[eval] token analysis skipped (head architecture incompatible)")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--split", default="test", choices=["val", "test"])
    args = parser.parse_args()
    run(args.split)
