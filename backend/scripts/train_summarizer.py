"""
Fine-tune BART for dispute chat summarization.

Usage:
    python scripts/train_summarizer.py --data data/synthetic_disputes.jsonl --output ../app/models/summarizer
"""

import argparse
import json
import logging
import os

from datasets import Dataset, load_dataset
from transformers import (
    AutoTokenizer,
    AutoModelForSeq2SeqLM,
    DataCollatorForSeq2Seq,
    Seq2SeqTrainingArguments,
    Seq2SeqTrainer,
)

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def parse_args():
    parser = argparse.ArgumentParser(description="Train dispute summarizer")
    parser.add_argument("--data", required=True, help="Path to training data (JSONL)")
    parser.add_argument(
        "--output",
        default="backend/app/models/summarizer",
        help="Output directory for model",
    )
    parser.add_argument("--model-name", default="facebook/bart-base", help="Base model")
    parser.add_argument("--epochs", type=int, default=5, help="Number of epochs")
    parser.add_argument("--batch-size", type=int, default=8, help="Per-device batch size")
    parser.add_argument("--max-length", type=int, default=512, help="Max input length")
    return parser.parse_args()


def format_input(example: dict) -> str:
    parties = example.get("parties", [])
    chat_lines = example.get("chat_log", [])
    header = f"Dispute between {', '.join(parties)}" if parties else "Dispute chat log"
    return header + "\n" + "\n".join(chat_lines)


def format_target(example: dict) -> str:
    return json.dumps(
        {
            "parties": example.get("parties", []),
            "dispute_amount": example.get("dispute_amount"),
            "key_facts": example.get("key_facts", []),
            "timeline": example.get("timeline", []),
            "summary_paragraph": example.get("summary_paragraph", ""),
        },
        ensure_ascii=False,
    )


def main():
    args = parse_args()

    tokenizer = AutoTokenizer.from_pretrained(args.model_name)
    model = AutoModelForSeq2SeqLM.from_pretrained(args.model_name)

    raw = load_dataset("json", data_files=args.data)["train"]
    split = raw.train_test_split(test_size=0.2, seed=42)

    def preprocess(batch):
        inputs = [format_input(e) for e in batch]
        targets = [format_target(e) for e in batch]
        model_inputs = tokenizer(
            inputs, max_length=args.max_length, truncation=True, padding="max_length"
        )
        labels = tokenizer(
            targets, max_length=args.max_length, truncation=True, padding="max_length"
        )
        model_inputs["labels"] = labels["input_ids"]
        return model_inputs

    tokenized = split.map(preprocess, batched=True)

    data_collator = DataCollatorForSeq2Seq(tokenizer=tokenizer, model=model)

    training_args = Seq2SeqTrainingArguments(
        output_dir=args.output,
        evaluation_strategy="steps",
        eval_steps=500,
        save_strategy="steps",
        save_steps=500,
        num_train_epochs=args.epochs,
        per_device_train_batch_size=args.batch_size,
        per_device_eval_batch_size=args.batch_size,
        predict_with_generate=True,
        logging_dir=f"{args.output}/logs",
        logging_steps=100,
        save_total_limit=2,
        load_best_model_at_end=True,
        metric_for_best_model="eval_loss",
    )

    trainer = Seq2SeqTrainer(
        model=model,
        args=training_args,
        train_dataset=tokenized["train"],
        eval_dataset=tokenized["test"],
        tokenizer=tokenizer,
        data_collator=data_collator,
    )

    trainer.train()
    trainer.save_model(args.output)
    tokenizer.save_pretrained(args.output)
    logger.info("Model saved to %s", args.output)


if __name__ == "__main__":
    main()
