import json
import logging
import os
from typing import Optional

logger = logging.getLogger(__name__)

LABELS = ["supporting_claimant", "supporting_respondent", "neutral"]


class EvidenceClassifier:
    def __init__(self, model_path: Optional[str] = None):
        self.model_path = model_path or os.path.join(
            os.path.dirname(__file__), "..", "models", "evidence_classifier"
        )
        self._pipeline = None

    def _init_pipeline(self):
        try:
            from transformers import pipeline

            self._pipeline = pipeline(
                "text-classification",
                model=str(self.model_path),
                top_k=None,
            )
        except (ImportError, OSError) as e:
            logger.warning(
                "Could not load fine-tuned model from %s: %s. "
                "Falling back to zero-shot classification.",
                self.model_path,
                e,
            )
            self._init_zero_shot()

    def _init_zero_shot(self):
        try:
            from transformers import pipeline

            self._pipeline = pipeline(
                "zero-shot-classification",
                model="facebook/bart-large-mnli",
            )
        except ImportError:
            logger.error(
                "transformers not installed. Install with: pip install transformers torch"
            )
            raise

    def classify(self, text: str, evidence_type: str = "general") -> dict:
        augmented_input = f"[{evidence_type}] {text}"

        if self._pipeline is None:
            self._init_pipeline()

        try:
            if self._pipeline.task == "zero-shot-classification":
                result = self._pipeline(augmented_input, candidate_labels=LABELS)
                scores = {
                    label: score
                    for label, score in zip(result["labels"], result["scores"])
                }
                best_label = max(scores, key=scores.get)
                return {
                    "label": best_label,
                    "confidence": round(scores[best_label], 4),
                }
            else:
                result = self._pipeline(augmented_input)
                return {
                    "label": result[0]["label"],
                    "confidence": round(result[0]["score"], 4),
                }
        except Exception as e:
            logger.error("Evidence classification failed: %s", e)
            return {"label": "neutral", "confidence": 0.0}

    def train(self, dataset_path: str, output_path: Optional[str] = None):
        from transformers import (
            Trainer,
            TrainingArguments,
            AutoModelForSequenceClassification,
            AutoTokenizer,
        )
        from datasets import load_dataset

        output = output_path or str(self.model_path)

        dataset = load_dataset("json", data_files=dataset_path)["train"].train_test_split(
            test_size=0.2
        )

        tokenizer = AutoTokenizer.from_pretrained("distilbert-base-uncased")
        model = AutoModelForSequenceClassification.from_pretrained(
            "distilbert-base-uncased", num_labels=len(LABELS)
        )

        id2label = {i: l for i, l in enumerate(LABELS)}
        label2id = {l: i for i, l in enumerate(LABELS)}
        model.config.id2label = id2label
        model.config.label2id = label2id

        def tokenize(batch):
            tokens = tokenizer(
                batch["text"], padding="max_length", truncation=True, max_length=256
            )
            tokens["label"] = [label2id[l] for l in batch["label"]]
            return tokens

        tokenized = dataset.map(tokenize, batched=True)

        args = TrainingArguments(
            output_dir=output,
            evaluation_strategy="epoch",
            save_strategy="epoch",
            num_train_epochs=5,
            per_device_train_batch_size=16,
            per_device_eval_batch_size=16,
            logging_dir=f"{output}/logs",
            logging_steps=500,
        )

        trainer = Trainer(
            model=model,
            args=args,
            train_dataset=tokenized["train"],
            eval_dataset=tokenized["test"],
            tokenizer=tokenizer,
        )

        trainer.train()
        trainer.save_model(output)
        tokenizer.save_pretrained(output)
        logger.info("Model saved to %s", output)

        self._pipeline = None
        self.model_path = output
