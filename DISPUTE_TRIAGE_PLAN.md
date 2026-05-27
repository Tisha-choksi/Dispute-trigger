# Dispute Triage Assistant — Crypto Escrow

## Overview

AI-powered dispute resolution assistant for a blockchain escrow platform. Uses transformer-based NLP for chat summarization and evidence analysis, reducing arbitration effort by ~60%. Orchestrates smart contract–integrated dispute workflows that generate AI-assisted resolution recommendations.

---

## Phase 1: Foundation (Week 1–2)

### 1.1 Smart Contract Layer

**File:** `contracts/Escrow.sol`

```solidity
// State machine
enum DisputeState { Open, UnderReview, AwaitingEvidence, Resolved }

struct Dispute {
    uint256 id;
    address claimant;
    address respondent;
    uint256 amount;
    DisputeState state;
    string evidenceIPFSHashes; // comma-separated
    string aiSummaryCID;
    string aiRecommendationCID;
    address resolver;
    uint256 createdAt;
    uint256 resolvedAt;
}

// Events
event DisputeRaised(uint256 indexed disputeId, address claimant, address respondent, uint256 amount);
event EvidenceSubmitted(uint256 indexed disputeId, address submitter, string ipfsHash);
event ResolutionProposed(uint256 indexed disputeId, address resolver, string recommendationCID);
event DisputeResolved(uint256 indexed disputeId, address winner, uint256 payout);
```

**Functions:**
- `raiseDispute(address _respondent)` — locks escrowed funds, emits `DisputeRaised`
- `submitEvidence(uint256 _disputeId, string _ipfsHash)` — only claimant/respondent
- `proposeResolution(uint256 _disputeId, string _recommendationCID)` — only authorized resolver (AI oracle or human)
- `resolveDispute(uint256 _disputeId, address _winner)` — finalizes payout

**Test file:** `test/Escrow.test.ts` — cover raise, evidence, resolution, edge cases (double-resolve, unauthorized caller).

### 1.2 Backend API

**Stack:** Python FastAPI + SQLAlchemy + PostgreSQL

**Project structure:**

```
backend/
  app/
    main.py              # FastAPI entry, CORS, middleware
    config.py            # env vars (DB URL, RPC URL, contract address)
    database.py          # SQLAlchemy engine + session
    models/
      dispute.py         # SQLAlchemy model
      evidence.py
      ai_insight.py
    schemas/
      dispute.py         # Pydantic request/response
      evidence.py
      recommendation.py
    routers/
      disputes.py        # CRUD /disputes
      evidence.py        # POST /evidence, GET /evidence/{id}
      summarization.py   # POST /summarize
      recommendations.py # POST /recommend
    services/
      dispute_service.py
      summarization_service.py
      evidence_classifier.py
      recommendation_engine.py
      web3_listener.py   # event listener
    worker/
      celery_tasks.py    # async NLP tasks
  alembic/               # migrations
  requirements.txt
  Dockerfile
```

**Database model (`dispute.py`):**

| Column             | Type     | Notes                          |
|--------------------|----------|--------------------------------|
| id                 | UUID     | PK                             |
| chain_dispute_id   | int      | on-chain dispute ID            |
| claimant           | address  |                                 |
| respondent         | address  |                                 |
| amount             | decimal  | escrowed amount                |
| state              | enum     | Open, UnderReview, Resolved    |
| summary_text       | text     | AI-generated summary           |
| recommendation_text| text     | AI-generated recommendation    |
| arbiter_decision   | text     | human override if any          |
| created_at         | datetime |                                 |
| resolved_at        | datetime | nullable                       |

**REST Endpoints:**

| Method | Path                    | Description                          |
|--------|-------------------------|--------------------------------------|
| GET    | `/disputes`             | List disputes (paginated, filterable by state) |
| GET    | `/disputes/{id}`        | Single dispute with evidence + AI insights |
| POST   | `/disputes`             | Create dispute record (triggered by on-chain event) |
| PATCH  | `/disputes/{id}/state`  | Advance dispute state                |
| POST   | `/evidence`             | Upload evidence metadata             |
| GET    | `/evidence/{dispute_id}`| List evidence for a dispute          |
| POST   | `/summarize`            | Trigger AI summarization on chat logs |
| POST   | `/recommend`            | Generate resolution recommendation   |
| GET    | `/stats`                | Dashboard metrics (avg resolution time, arbitrator agreement rate) |

---

## Phase 2: NLP Pipeline (Week 3–4)

### 2.1 Chat Summarization

**Goal:** Convert raw dispute chat logs into a structured summary.

**Approach:** Fine-tune `bert-base-uncased` (or `RoBERTa`) as a text-to-text summarizer using a custom dataset.

**Module:** `backend/app/services/summarization_service.py`

```
Input:  Raw chat transcript (parties A and B exchange messages)
Output: JSON with fields:
        - parties: [address_claimant, address_respondent]
        - dispute_amount: number
        - key_facts: ["item not delivered", "payment sent on date X"]
        - timeline: [{timestamp, event}]
        - summary_paragraph: string (2-3 sentences)
```

**Dataset preparation:**
- Generate 500+ synthetic dispute chat logs using GPT-based simulation
- Manually label 100 for validation
- Use `datasets` library from HuggingFace

**Training pipeline:**

```python
# train_summarizer.py
from transformers import (
    AutoTokenizer,
    AutoModelForSeq2SeqLM,
    Seq2SeqTrainingArguments,
    Seq2SeqTrainer,
    DataCollatorForSeq2Seq,
)

model_name = "facebook/bart-base"  # or "t5-base"
tokenizer = AutoTokenizer.from_pretrained(model_name)
model = AutoModelForSeq2SeqLM.from_pretrained(model_name)

# Tokenize inputs (raw chat) and targets (structured JSON summary)
# Train for 5 epochs, eval every 500 steps
# Export to backend/app/models/summarizer/
```

**Fallback:** If fine-tuning is impractical, use a zero-shot approach with `LangChain` + GPT-4:

```python
from langchain.prompts import PromptTemplate
from langchain.chains import LLMChain

prompt = PromptTemplate(
    input_variables=["chat_log"],
    template="""
You are a dispute resolution assistant. Summarize the following chat log between a buyer and seller.

Chat log:
{chat_log}

Extract:
1. Parties involved
2. Item/service in question
3. Amount disputed
4. Buyer's claim
5. Seller's defense
6. Timeline of key events
7. Summary paragraph
""",
)
```

### 2.2 Evidence Classification

**Goal:** Classify submitted evidence as supporting claimant, supporting respondent, or neutral.

**Model:** Fine-tune `distilbert-base-uncased` for 3-class classification.

**Module:** `backend/app/services/evidence_classifier.py`

```
Input: evidence text + metadata (type: "receipt", "message_screenshot", "tracking_info")
Output: { label: "supporting_claimant" | "supporting_respondent" | "neutral",
          confidence: 0.92 }
```

**Training data schema:**

```json
{
  "text": "Shipment tracking shows delivered at 2PM on June 5th",
  "label": "supporting_respondent"
}
```

**Integration:**

```python
class EvidenceClassifier:
    def __init__(self):
        self.pipeline = pipeline(
            "text-classification",
            model="backend/app/models/evidence_classifier/",
        )

    def classify(self, text: str, evidence_type: str) -> dict:
        # Prepend type hint for context
        augmented_input = f"[{evidence_type}] {text}"
        result = self.pipeline(augmented_input)
        return {"label": result[0]["label"], "confidence": result[0]["score"]}
```

---

## Phase 3: Dispute Workflow Engine (Week 5)

### 3.1 State Machine

**File:** `backend/app/services/dispute_service.py`

```
                ┌──────────┐
                │   Open   │
                └────┬─────┘
                     │ evidence submitted
                     ▼
             ┌───────────────┐
             │ UnderReview   │◄──── evidence threshold met
             └───────┬───────┘
                     │ AI completes analysis
                     ▼
            ┌──────────────────┐
            │ AIRecommendation │
            └────────┬─────────┘
                     │ arbiter approves
                     ▼
               ┌──────────┐
               │ Resolved │
               └──────────┘
```

**Trigger conditions for AI analysis:**
- Minimum 2 evidence pieces submitted (configurable via env `EVIDENCE_THRESHOLD`)
- At least one piece from each party
- Auto-trigger after 48h of inactivity (fallback)

### 3.2 AI Resolution Generator

**Module:** `backend/app/services/recommendation_engine.py`

**Pipeline:**

```python
class RecommendationEngine:
    def generate(self, dispute_id: int) -> dict:
        dispute = dispute_repo.get(dispute_id)
        summary = summarization_service.summarize(dispute.chat_logs)
        evidence_list = evidence_repo.get_all(dispute_id)

        # Classify each evidence
        evidence_analysis = []
        for ev in evidence_list:
            result = classifier.classify(ev.text, ev.type)
            evidence_analysis.append(result)

        # Build pros/cons per party using LangChain
        pros_cons = self._build_pros_cons(summary, evidence_analysis)

        # Generate final recommendation
        recommendation = self._generate_recommendation(
            summary, evidence_analysis, pros_cons
        )

        return {
            "dispute_id": dispute_id,
            "summary": summary,
            "evidence_analysis": evidence_analysis,
            "pros_cons": pros_cons,
            "recommendation": recommendation,
            "confidence_score": self._calculate_confidence(evidence_analysis),
        }

    def _build_pros_cons(self, summary, evidence_analysis):
        prompt = PromptTemplate(
            template="""
Based on this dispute summary and evidence analysis, list pros and cons for each party.

Summary: {summary}

Evidence: {evidence}

Claimant Pros: ...
Claimant Cons: ...
Respondent Pros: ...
Respondent Cons: ...
""",
        )
        return llm_chain.run(summary=summary, evidence=evidence_analysis)

    def _generate_recommendation(self, summary, evidence_analysis, pros_cons):
        prompt = PromptTemplate(
            template="""
Given the following dispute, who should prevail and why?

Summary: {summary}
Evidence Analysis: {evidence_analysis}
Pros/Cons: {pros_cons}

Recommendation:
- Prevailing party: (claimant / respondent / split)
- Reasoning (bullet points):
- Suggested split percentage if split:
""",
        )
        return llm_chain.run(...)
```

### 3.3 Confidence Scoring

```python
def _calculate_confidence(self, evidence_analysis: list) -> float:
    """
    Factors:
      - Number of evidence pieces
      - Consistency of classifications (all leaning one way vs split)
      - Average confidence of individual classifications
    """
    if not evidence_analysis:
        return 0.0

    avg_confidence = np.mean([e["confidence"] for e in evidence_analysis])
    labels = [e["label"] for e in evidence_analysis]

    claimant_count = labels.count("supporting_claimant")
    respondent_count = labels.count("supporting_respondent")
    total = len(labels)

    # Leaning strength: how one-sided the evidence is (0 to 1)
    leaning = abs(claimant_count - respondent_count) / total if total > 0 else 0

    # Combined score
    score = 0.4 * avg_confidence + 0.6 * leaning
    return round(min(score, 1.0), 2)
```

---

## Phase 4: Integration & UI (Week 6)

### 4.1 Web3 Event Listener

**Module:** `backend/app/services/web3_listener.py`

```python
from web3 import Web3
import asyncio

class DisputeEventListener:
    def __init__(self, rpc_url, contract_address, abi):
        self.w3 = Web3(Web3.HTTPProvider(rpc_url))
        self.contract = self.w3.eth.contract(
            address=contract_address, abi=abi
        )

    async def listen_forever(self):
        event_filter = self.contract.events.DisputeRaised.create_filter(fromBlock="latest")

        while True:
            for event in event_filter.get_new_entries():
                dispute_id = event["args"]["disputeId"]
                # Create dispute record in DB
                # Trigger async summarization task
                celery_app.send_task("summarize_dispute", args=[dispute_id])

            await asyncio.sleep(2)
```

### 4.2 Frontend Dashboard

**Stack:** React + TypeScript + wagmi (web3 hooks) + Tailwind CSS

**Structure:**

```
frontend/
  src/
    App.tsx
    pages/
      Dashboard.tsx           # Stats overview (total disputes, avg resolution time, arbiter agreement %)
      DisputeList.tsx         # Paginated table with state filter, search
      DisputeDetail.tsx       # Single dispute view
      EvidencePanel.tsx       # Upload/view evidence
      AIInsights.tsx          # Summary + recommendation display
    components/
      DisputeCard.tsx         # Summary card for list view
      RecommendationCard.tsx  # AI recommendation + arbiter action buttons
      EvidenceUploader.tsx    # File upload to IPFS
      Timeline.tsx            # Event timeline component
      ConfidenceBadge.tsx     # Color-coded confidence indicator
    hooks/
      useDisputes.ts          # wagmi contract read hooks
      useEvidence.ts
      useAIRecommendation.ts  # Calls backend /recommend endpoint
    utils/
      contract.ts             # wagmi config, contract ABI import
      ipfs.ts                 # Pinata or web3.storage client
```

**Key UI States:**
- **Loading** — Skeleton cards while AI generates
- **Empty** — "No disputes" illustration
- **Error** — Failed AI generation with retry button
- **Edge case** — Missing evidence, tie confidence, long chat logs truncated

**Dashboard metrics (from `/stats`):**
- Total disputes handled
- Avg resolution time (hours)
- Arbiter agreement rate (%)
- Disputes by state (pie chart)
- Confidence distribution (histogram)

### 4.3 IPFS Integration

- Use `web3.storage` or `Pinata` for evidence file storage
- Store AI outputs (summary, recommendation) as JSON on IPFS
- Save CID on-chain in `Dispute.aiSummaryCID` / `Dispute.aiRecommendationCID`

---

## Phase 5: Evaluation (Week 7)

### 5.1 Metrics & KPIs

| Metric                          | Target     | How to Measure                          |
|---------------------------------|------------|-----------------------------------------|
| Time-to-recommendation          | < 5 min    | Time from "UnderReview" to recommendation generated |
| Arbiter agreement rate          | > 80%      | % of AI recommendations accepted without modification |
| Summary accuracy (ROUGE-L)      | > 0.70     | Compare AI summary vs human-written summary on test set |
| Evidence classification F1      | > 0.85     | On manually labeled evidence test set   |
| False positive / false negative | < 10%      | Arbiter overrides analysis              |

### 5.2 Ground Truth Dataset

- Collect 100+ historical escrow disputes
- Each labeled by 2 independent arbiters (resolve disagreements via third arbiter)
- Fields per sample: chat_log, evidence_list, correct_winner, reasoning

### 5.3 A/B Testing

- Run 50 disputes with AI recommendation visible vs 50 without
- Measure arbiter decision time and consistency between groups

---

## Complete Project Structure

```
dispute-triage/
├── contracts/                  # Solidity smart contracts
│   ├── Escrow.sol
│   └── test/
│       └── Escrow.test.ts
├── backend/
│   ├── app/
│   │   ├── main.py
│   │   ├── config.py
│   │   ├── database.py
│   │   ├── models/
│   │   ├── schemas/
│   │   ├── routers/
│   │   ├── services/
│   │   └── worker/
│   ├── alembic/
│   ├── requirements.txt
│   └── Dockerfile
├── models/                     # Trained/fine-tuned models
│   ├── summarizer/
│   └── evidence_classifier/
├── frontend/
│   ├── src/
│   │   ├── pages/
│   │   ├── components/
│   │   ├── hooks/
│   │   └── utils/
│   ├── package.json
│   └── tailwind.config.js
├── data/
│   ├── synthetic_chat_logs.json
│   └── labeled_disputes.csv
├── notebooks/
│   ├── 01_data_generation.ipynb
│   ├── 02_train_summarizer.ipynb
│   └── 03_train_classifier.ipynb
├── scripts/
│   ├── deploy_contract.sh
│   └── seed_data.py
├── docker-compose.yml          # PostgreSQL + backend + worker
├── DISPUTE_TRIAGE_PLAN.md
└── README.md
```

---

## Tech Stack Summary

| Component             | Choice                      | Purpose                              |
|-----------------------|-----------------------------|--------------------------------------|
| Smart Contracts       | Solidity 0.8.x + Hardhat    | Escrow + dispute state machine       |
| Backend               | Python FastAPI              | REST API for dispute CRUD + AI       |
| Database              | PostgreSQL + SQLAlchemy     | Off-chain dispute records            |
| NLP Models            | HuggingFace Transformers    | Summarization + evidence classification |
| LLM Orchestration     | LangChain + GPT-4 / Claude  | Recommendation generation            |
| Blockchain Events     | web3.py                     | Listen for on-chain dispute events   |
| Frontend              | React + TypeScript + wagmi  | Dashboard for arbiters               |
| Storage               | IPFS (web3.storage)         | Evidence + AI output persistence     |
| Async Tasks           | Celery + Redis              | Background AI processing             |
| Containerization      | Docker Compose              | Local development + deployment       |
