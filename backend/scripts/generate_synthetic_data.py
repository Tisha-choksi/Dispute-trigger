"""
Generate synthetic dispute chat logs and evidence for training.

Produces JSONL files for both summarization and classification training.

Usage:
    python scripts/generate_synthetic_data.py --output data/
"""

import argparse
import json
import logging
import os
import random

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

SEED = 42
random.seed(SEED)

DISPUTE_SCENARIOS = [
    {
        "item": "vintage camera",
        "amount": 2.5,
        "claim": "camera arrived with a cracked lens",
        "defense": "camera was in perfect condition when shipped, photos provided",
    },
    {
        "item": "graphics card",
        "amount": 1.8,
        "claim": "card was not the advertised model",
        "defense": "correct model was sent, buyer may be confused",
    },
    {
        "item": "consulting services",
        "amount": 5.0,
        "claim": "deliverables were incomplete and late",
        "defense": "all deliverables were provided on time per the agreement",
    },
    {
        "item": "designer handbag",
        "amount": 3.2,
        "claim": "received a counterfeit item",
        "defense": "item is authentic with certificate of authenticity included",
    },
    {
        "item": "smartphone",
        "amount": 1.5,
        "claim": "phone does not turn on",
        "defense": "phone was tested before shipping, buyer may have damaged it",
    },
]

PARTIES = [
    ("0xA1bCdef1234567890aBcDeF1234567890abcDEF1", "0xB2cDeF1234567890aBcDeF1234567890abcDEF2"),
    ("0xC3dEf1234567890aBcDeF1234567890abcDEF3", "0xD4eF1234567890aBcDeF1234567890abcDEF4"),
    ("0xE5f1234567890aBcDeF1234567890abcDEF56", "0xF61234567890aBcDeF1234567890abcDEF567"),
]

EVIDENCE_TYPES = ["receipt", "message_screenshot", "tracking_info", "photo", "contract"]


def generate_chat_log(scenario, claimant_addr, respondent_addr):
    lines = [
        f"{claimant_addr}: I purchased the {scenario['item']} for {scenario['amount']} ETH.",
        f"{respondent_addr}: Confirmed. I shipped it promptly.",
        f"{claimant_addr}: {scenario['claim']}",
        f"{respondent_addr}: {scenario['defense']}",
    ]
    for i in range(random.randint(1, 3)):
        party = claimant_addr if random.random() < 0.5 else respondent_addr
        msg = random.choice([
            f"I have photo evidence of the issue.",
            f"The tracking shows it was delivered on time.",
            f"Please refund the amount.",
            f"I suggest we find a fair resolution.",
            f"This is unacceptable.",
            f"I acted in good faith throughout.",
        ])
        lines.append(f"{party}: {msg}")
    return lines


def generate_summarization_sample(idx):
    scenario = random.choice(DISPUTE_SCENARIOS)
    parties = random.choice(PARTIES)
    chat = generate_chat_log(scenario, parties[0], parties[1])
    return {
        "parties": list(parties),
        "chat_log": chat,
        "dispute_amount": scenario["amount"],
        "key_facts": [scenario["claim"], scenario["defense"]],
        "timeline": [
            {"timestamp": "Day 1", "event": f"Purchase of {scenario['item']}"},
            {"timestamp": "Day 3", "event": "Item received"},
            {"timestamp": "Day 5", "event": "Dispute raised"},
        ],
        "summary_paragraph": (
            f"A dispute was raised regarding the purchase of {scenario['item']} "
            f"for {scenario['amount']} ETH. The claimant states: {scenario['claim']}. "
            f"The respondent counters: {scenario['defense']}."
        ),
    }


def generate_classification_sample(idx):
    scenario = random.choice(DISPUTE_SCENARIOS)
    evidence_type = random.choice(EVIDENCE_TYPES)
    label = random.choice(["supporting_claimant", "supporting_respondent", "neutral"])

    texts = {
        "supporting_claimant": [
            f"Photo clearly shows the {scenario['item']} is damaged.",
            f"Payment record confirms {scenario['amount']} ETH was sent.",
            f"Chat log shows seller acknowledged the issue.",
        ],
        "supporting_respondent": [
            f"Tracking number confirms delivery was completed.",
            f"Pre-shipment photos show the item in perfect condition.",
            f"Screenshot of the listing matches the item description.",
        ],
        "neutral": [
            f"Both parties have submitted evidence.",
            f"Shipping address matches the records.",
            f"Transaction hash is visible on the block explorer.",
        ],
    }

    return {
        "text": random.choice(texts[label]),
        "label": label,
        "evidence_type": evidence_type,
    }


def main():
    parser = argparse.ArgumentParser(description="Generate synthetic training data")
    parser.add_argument("--output", default="data", help="Output directory")
    parser.add_argument("--num-summaries", type=int, default=500)
    parser.add_argument("--num-classification", type=int, default=1000)
    args = parser.parse_args()

    os.makedirs(args.output, exist_ok=True)

    sum_path = os.path.join(args.output, "synthetic_disputes.jsonl")
    with open(sum_path, "w") as f:
        for i in range(args.num_summaries):
            f.write(json.dumps(generate_summarization_sample(i)) + "\n")
    logger.info("Generated %d summarization samples -> %s", args.num_summaries, sum_path)

    cls_path = os.path.join(args.output, "evidence_dataset.jsonl")
    with open(cls_path, "w") as f:
        for i in range(args.num_classification):
            f.write(json.dumps(generate_classification_sample(i)) + "\n")
    logger.info("Generated %d classification samples -> %s", args.num_classification, cls_path)


if __name__ == "__main__":
    main()
