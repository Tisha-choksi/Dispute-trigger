# Phase 1 — System Architecture

---

## 1. High-Level Overview

```
┌─────────────────────────────────────────────────────────────────────┐
│                         Phase 1 Boundary                             │
│                                                                     │
│  ┌──────────────────┐       ┌───────────────────────────────────┐   │
│  │   Smart Contract  │       │         FastAPI Backend           │   │
│  │   (Solidity)      │◄──────►  (Python)                        │   │
│  │                   │  RPC  │                                   │   │
│  │  Escrow.sol       │       │  main.py                          │   │
│  │                   │       │  routers/disputes.py              │   │
│  │  ─ Events ─       │       │  models/dispute.py               │   │
│  │  DisputeRaised    │       │  schemas/dispute.py              │   │
│  │  EvidenceSubmitted│       │  services/dispute_service.py     │   │
│  │  ResolutionProposed│      │  services/web3_listener.py       │   │
│  │  DisputeResolved  │       │  worker/celery_tasks.py          │   │
│  └──────────────────┘       └──────────┬────────────────────────┘   │
│                                        │                           │
│                                        ▼                           │
│                              ┌──────────────────┐                  │
│                              │   PostgreSQL      │                  │
│                              │   dispute_triage  │                  │
│                              └──────────────────┘                  │
└─────────────────────────────────────────────────────────────────────┘
```

---

## 2. Smart Contract Layer

### 2.1 State Machine

```
                  ┌──────────┐
                  │   Open   │  (0)
                  └────┬─────┘
                       │ evidence submitted
                       ▼
              ┌──────────────────┐
              │   UnderReview    │  (1)
              └───────┬──────────┘
                       │ resolution proposed + arbiter resolves
                       ▼
                 ┌──────────┐
                 │ Resolved │  (2)
                 └──────────┘
```

### 2.2 Contract Architecture (`contracts/Escrow.sol`)

```
Escrow
├── Storage
│   ├── nextEscrowId: uint256
│   ├── nextDisputeId: uint256
│   ├── escrows: mapping(uint256 → EscrowAgreement)
│   ├── disputes: mapping(uint256 → Dispute)
│   └── disputeToEscrow: mapping(uint256 → uint256)
│
├── Structs
│   ├── EscrowAgreement { id, buyer, seller, amount, released, disputed, disputeId }
│   └── Dispute { id, claimant, respondent, amount, state, evidenceIPFSHashes,
│                  aiSummaryCID, aiRecommendationCID, resolver, createdAt, resolvedAt }
│
├── Mutative Functions
│   ├── createEscrow(address seller)        payable  — locks ETH
│   ├── releaseFunds(uint256 escrowId)       — buyer releases to seller
│   ├── raiseDispute(uint256 escrowId)       — party triggers dispute
│   ├── submitEvidence(uint256, string)      — party uploads IPFS hash
│   ├── proposeResolution(uint256, string)   — AI oracle submits CID
│   └── resolveDispute(uint256, address)     — arbiter finalizes, transfers ETH
│
└── Events
    ├── EscrowCreated(escrowId, buyer, seller, amount)
    ├── FundsReleased(escrowId, recipient, amount)
    ├── DisputeRaised(disputeId, escrowId, claimant, respondent, amount)
    ├── EvidenceSubmitted(disputeId, submitter, ipfsHash)
    ├── ResolutionProposed(disputeId, resolver, recommendationCID)
    └── DisputeResolved(disputeId, winner, payout)
```

### 2.3 Key Design Decisions

| Decision | Rationale |
|---|---|
| Comma-separated IPFS hashes in `evidenceIPFSHashes` | Avoids dynamic arrays in storage — gas efficient |
| `proposeResolution` separate from `resolveDispute` | Separates AI recommendation from human finalization |
| `disputeToEscrow` reverse mapping | Quick lookup from dispute → escrow during resolution |
| `nextEscrowId` starts at 1 | 0 serves as null/uninitialized sentinel |

---

## 3. Backend Layer

### 3.1 Application Structure

```
backend/
├── app/
│   ├── main.py                  # FastAPI app factory, CORS, lifespan
│   ├── config.py                # Pydantic BaseSettings (env-driven)
│   ├── database.py              # SQLAlchemy engine + session + Base
│   │
│   ├── models/
│   │   ├── __init__.py
│   │   └── dispute.py           # ORM: Dispute table
│   │
│   ├── schemas/
│   │   ├── __init__.py
│   │   └── dispute.py           # Pydantic: Create, Update, Response
│   │
│   ├── routers/
│   │   ├── __init__.py
│   │   └── disputes.py          # REST endpoints
│   │
│   ├── services/
│   │   ├── __init__.py
│   │   ├── dispute_service.py   # State machine + business logic
│   │   └── web3_listener.py     # On-chain event poller
│   │
│   └── worker/
│       ├── __init__.py
│       └── celery_tasks.py      # Async NLP task stubs
├── requirements.txt
├── Dockerfile
└── .env
```

### 3.2 Database Model

```
Table: disputes
┌──────────────────────┬──────────────────┬──────────────────────────────────┐
│ Column               │ Type             │ Notes                            │
├──────────────────────┼──────────────────┼──────────────────────────────────┤
│ id                   │ UUID (PK)        │ Generated server-side            │
│ chain_dispute_id     │ INTEGER (UQ)     │ Maps to on-chain Dispute.id      │
│ chain_escrow_id      │ INTEGER          │ Maps to on-chain EscrowAgreement │
│ claimant             │ VARCHAR(42)      │ Ethereum address                 │
│ respondent           │ VARCHAR(42)      │ Ethereum address                 │
│ amount               │ NUMERIC(32,18)   │ ETH amount with 18 decimals      │
│ state                │ ENUM             │ Open / UnderReview / Resolved    │
│ evidence_ipfs_hashes │ TEXT             │ Comma-separated IPFS CIDs        │
│ summary_text         │ TEXT (nullable)  │ AI-generated summary (Phase 2)   │
│ recommendation_text  │ TEXT (nullable)  │ AI recommendation (Phase 3)      │
│ arbiter_decision     │ TEXT (nullable)  │ Human override (Phase 3)         │
│ contract_address     │ VARCHAR(42)      │ Deployed contract address        │
│ resolver_address     │ VARCHAR(42)      │ Address that resolved            │
│ created_at           │ DATETIME         │ Auto-set on insert               │
│ resolved_at          │ DATETIME         │ Set on resolution                │
│ updated_at           │ DATETIME         │ Auto-updated                     │
└──────────────────────┴──────────────────┴──────────────────────────────────┘
```

### 3.3 REST API

```
Base URL: /api/v1

┌─────────┬───────────────────────────┬────────────────────────────────────────┐
│ Method  │ Path                      │ Description                            │
├─────────┼───────────────────────────┼────────────────────────────────────────┤
│ GET     │ /disputes                 │ List disputes (paginated, filterable)  │
│         │   ?state=Open             │ Filter by state                        │
│         │   &page=1&page_size=20    │ Pagination                             │
│ POST    │ /disputes                 │ Create dispute record                  │
│ GET     │ /disputes/{id}            │ Get single dispute                     │
│ PATCH   │ /disputes/{id}            │ Update dispute (state, evidence, etc)  │
│ DELETE  │ /disputes/{id}            │ Soft-delete / remove                   │
│ GET     │ /health                   │ Health check                           │
└─────────┴───────────────────────────┴────────────────────────────────────────┘
```

### 3.4 Request/Response Schemas

**POST /disputes — Request Body**
```json
{
  "chain_dispute_id": 1,
  "chain_escrow_id": 1,
  "claimant": "0x123...",
  "respondent": "0x456...",
  "amount": "1.0",
  "contract_address": "0x789..."
}
```

**GET /disputes — Response**
```json
{
  "items": [
    {
      "id": "uuid...",
      "chain_dispute_id": 1,
      "state": "Open",
      "claimant": "0x123...",
      "respondent": "0x456...",
      "amount": "1.0",
      "evidence_ipfs_hashes": "QmX...,QmY...",
      "summary_text": null,
      "recommendation_text": null,
      "created_at": "2026-05-23T10:00:00Z",
      "resolved_at": null
    }
  ],
  "total": 42,
  "page": 1,
  "page_size": 20
}
```

---

## 4. Event Listener Architecture

```
┌──────────────────┐     poll every 2s     ┌─────────────────────┐
│  Ethereum Node   │◄──────────────────────│  Web3 Event Listener │
│  (Hardhat/Anvil) │                       │  (web3_listener.py)  │
│                  │── DisputeRaised ──────►│                      │
│                  │── EvidenceSubmitted ──►│  on_dispute_raised() │
│                  │── ResolutionProposed ─►│  → create DB record  │
│                  │── DisputeResolved ────►│                      │
└──────────────────┘                       └─────────┬───────────┘
                                                      │
                                                      ▼
                                            ┌──────────────────┐
                                            │   PostgreSQL      │
                                            │   dispute_triage  │
                                            └──────────────────┘
```

**Flow:**
1. Listener polls `get_logs(from_block, to_block)` every 2 seconds
2. On `DisputeRaised` → creates dispute record in DB via `POST /disputes`
3. On `EvidenceSubmitted` → appends IPFS hash to `evidence_ipfs_hashes`
4. On `ResolutionProposed` → stores recommendation CID
5. On `DisputeResolved` → updates state + resolved_at

---

## 5. Data Flow: End-to-End Dispute

```
User Action              On-Chain                Backend                 DB
──────────              ─────────               ───────                 ──
Buyer creates escrow    createEscrow()
                        ── EscrowCreated ──►    listener creates
                        (event ignored in         escrow row
                         Phase 1)

Buyer raises dispute    raiseDispute()
                        ── DisputeRaised ───►   listener hits
                                                 POST /disputes       INSERT
                                                                      row

Seller submits          submitEvidence()
evidence                ── EvidenceSubmitted ►   listener hits
                                                 PATCH /disputes      UPDATE
                                                                      row

AI oracle submits       proposeResolution()
recommendation          ── ResolutionProposed ►  listener stores CID  UPDATE

Arbiter resolves        resolveDispute()
                        ── DisputeResolved ──►   listener updates
                                                 state → Resolved     UPDATE
                                                                      row

Arbiter/Dashboard       polls REST API          GET /disputes         SELECT
```

---

## 6. Contract Test Coverage

```
Escrow
├── Escrow Creation (4 tests)
│   ├── ✔ creates escrow with correct details
│   ├── ✔ rejects zero value
│   ├── ✔ emits EscrowCreated event
│   └── ✔ increments escrow ID
│
├── Fund Release (4 tests)
│   ├── ✔ releases funds to seller
│   ├── ✔ only buyer can release
│   ├── ✔ rejects double release
│   └── ✔ emits FundsReleased event
│
└── Dispute Lifecycle (19 tests)
    ├── ✔ raises a dispute
    ├── ✔ emits DisputeRaised event
    ├── ✔ cannot dispute released escrow
    ├── ✔ cannot dispute twice
    ├── ✔ third party cannot dispute
    ├── ✔ claimant submits evidence
    ├── ✔ respondent submits evidence
    ├── ✔ third party cannot submit evidence
    ├── ✔ cannot submit evidence after resolution
    ├── ✔ emits EvidenceSubmitted event
    ├── ✔ proposes a resolution
    ├── ✔ emits ResolutionProposed event
    ├── ✔ resolves in favor of claimant
    ├── ✔ resolves in favor of respondent
    ├── ✔ rejects invalid winner
    ├── ✔ rejects double resolution
    ├── ✔ emits DisputeResolved event
    ├── ✔ marks escrow as released after resolution
    └── ✔ full flow: create → dispute → evidence → resolve
```

**Result:** 27 passing / 0 failing

---

## 7. Infrastructure

### 7.1 Docker Compose Topology

```
docker-compose.yml
├── db (postgres:16-alpine)
│   ├── port 5432
│   └── volume: pgdata
├── redis (redis:7-alpine)
│   └── port 6379
└── backend
    ├── port 8000
    ├── depends_on: db, redis
    ├── volume mount: ./backend:/app (hot reload)
    └── env: DATABASE_URL, REDIS_URL, RPC_URL
```

### 7.2 Hardhat Configuration

```typescript
// hardhat.config.ts
{
  solidity: "0.8.24",
  optimizer: { enabled: true, runs: 200 },
  networks: { localhost: "http://127.0.0.1:8545" },
}
```

---

## 8. Component Dependency Graph

```
                    ┌──────────────┐
                    │  Hardhat     │
                    │  (local node)│
                    └──────┬───────┘
                           │ RPC (8545)
                           ▼
              ┌──────────────────────┐
              │  Web3 Event Listener │
              │  (web3_listener.py)  │
              └──────────┬───────────┘
                         │ triggers
                         ▼
              ┌──────────────────────┐
              │  Dispute Router      │
              │  (routers/disputes)  │
              └──────────┬───────────┘
                         │ reads/writes
                         ▼
              ┌──────────────────────┐
              │  PostgreSQL          │
              │  (dispute_triage)    │
              └──────────────────────┘
```

---

## 9. Key Files Reference

| File | Path |
|---|---|
| Solidity Contract | `contracts/Escrow.sol` |
| Contract Tests | `test/Escrow.test.ts` |
| Deploy Script | `scripts/deploy.ts` |
| Hardhat Config | `hardhat.config.ts` |
| FastAPI Entry | `backend/app/main.py` |
| Config | `backend/app/config.py` |
| DB Session | `backend/app/database.py` |
| ORM Model | `backend/app/models/dispute.py` |
| Pydantic Schemas | `backend/app/schemas/dispute.py` |
| REST Routes | `backend/app/routers/disputes.py` |
| Business Logic | `backend/app/services/dispute_service.py` |
| Event Listener | `backend/app/services/web3_listener.py` |
| Celery Tasks | `backend/app/worker/celery_tasks.py` |
| Dependencies | `backend/requirements.txt` |
| Docker Compose | `docker-compose.yml` |
