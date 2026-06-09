"""
Fine-tune DistilBERT for evidence classification.

Usage:
    python scripts/train_classifier.py --data data/evidence_dataset.jsonl --output ../app/models/evidence_classifier
"""

import argparse
import logging

from datasets import load_dataset
from transformers import (
    AutoTokenizer,
    AutoModelForSequenceClassification,
    Trainer,
    TrainingArguments,
)

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

LABELS = ["supporting_claimant", "supporting_respondent", "neutral"]
ID2LABEL = {i: l for i, l in enumerate(LABELS)}
LABEL2ID = {l: i for i, l in enumerate(LABELS)}


def parse_args():
    parser = argparse.ArgumentParser(description="Train evidence classifier")
    parser.add_argument("--data", required=True, help="Path to training data (JSONL)")
    parser.add_argument(
        "--output",
        default="backend/app/models/evidence_classifier",
        help="Output directory for model",
    )
    parser.add_argument(
        "--model-name", default="distilbert-base-uncased", help="Base model"
    )
    parser.add_argument("--epochs", type=int, default=5)
    parser.add_argument("--batch-size", type=int, default=16)
    parser.add_argument("--max-length", type=int, default=256)
    return parser.parse_args()


def main():
    args = parse_args()

    tokenizer = AutoTokenizer.from_pretrained(args.model_name)
    model = AutoModelForSequenceClassification.from_pretrained(
        args.model_name,
        num_labels=len(LABELS),
        id2label=ID2LABEL,
        label2id=LABEL2ID,
    )

    dataset = load_dataset("json", data_files=args.data)["train"]
    split = dataset.train_test_split(test_size=0.2, seed=42)

    def tokenize(batch):
        tokens = tokenizer(
            batch["text"],
            padding="max_length",
            truncation=True,
            max_length=args.max_length,
        )
        tokens["label"] = [LABEL2ID[l] for l in batch["label"]]
        return tokens

    tokenized = split.map(tokenize, batched=True)

    training_args = TrainingArguments(
        output_dir=args.output,
        evaluation_strategy="epoch",
        save_strategy="epoch",
        num_train_epochs=args.epochs,
        per_device_train_batch_size=args.batch_size,
        per_device_eval_batch_size=args.batch_size,
        logging_dir=f"{args.output}/logs",
        logging_steps=500,
        save_total_limit=2,
        load_best_model_at_end=True,
        metric_for_best_model="accuracy",
    )

    trainer = Trainer(
        model=model,
        args=training_args,
        train_dataset=tokenized["train"],
        eval_dataset=tokenized["test"],
        tokenizer=tokenizer,
    )

    trainer.train()
    trainer.save_model(args.output)
    tokenizer.save_pretrained(args.output)
    logger.info("Model saved to %s", args.output)


if __name__ == "__main__":
    main()
