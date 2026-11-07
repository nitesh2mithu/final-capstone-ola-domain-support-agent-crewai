# Completed Ola (Business Operations / Customer Support) track — Ola Domain Support Agent

## Overview

This capstone demonstrates a customer-support assistant for an Ola-themed scenario. It answers questions from a local policy knowledge base, looks up fabricated support tickets, and remembers ticket context across a conversation.

The project runs through command-line tools or FastAPI. All language-model stages use deterministic `MOCK_LLM`, so runtime requires zero API keys and uses no paid model services. Tickets and policies are fabricated for this project and are not official Ola data or policies.

## How it works

1. Input guards mask the declared phone-number format and reject known prompt-injection patterns.
2. The Retrieval Agent searches local policy documents, while the Lookup Agent alone can read ticket records.
3. The Composer creates a structured answer from the retrieved evidence.
4. A two-agent AutoGen review either approves the answer or revises unsupported content.
5. Pydantic validation and output guards check the final response before it is returned and logged.

The application combines local SentenceTransformers embeddings, separate Chroma indexes, a three-agent CrewAI crew, conversation memory, AutoGen review, and FastAPI. Policy responses may be cached; ticket and session-specific responses are never shared. Runtime tools are read-only and cannot issue refunds or change ticket records.

## Setup and quick start

Use Python 3.11. The verified environment uses Python 3.11.17 on macOS Apple Silicon. Exact dependency versions are in [requirements-api.lock](requirements-api.lock); other platforms may need compatible wheels and their own verification.

Create the environment and download the pinned public embedding model:

```sh
python3.11 -m venv .venv311
.venv311/bin/python -m pip install --cache-dir .cache/pip -r requirements-api.lock
HF_HUB_OFFLINE=0 TRANSFORMERS_OFFLINE=0 .venv311/bin/python -m scripts.download_embedding_model
```

The model is `sentence-transformers/all-MiniLM-L6-v2` at revision `1110a243fdf4706b3f48f1d95db1a4f5529b4d41`. [The model manifest](evidence/model_manifest.json) pins its files and checksums. Model weights and generated indexes are excluded from Git.

Rebuild the local indexes before the first run:

```sh
export MOCK_LLM=true CREWAI_DISABLE_TELEMETRY=true OTEL_SDK_DISABLED=true
.venv311/bin/python -m scripts.rebuild_indexes
```

Telemetry is disabled before framework imports, including CrewAI kickoff. Runtime checks block external networking and child processes; API checks permit only their declared localhost port. Setup downloads are separate from offline runtime.

The main offline verification command is:

```sh
.venv311/bin/python -m scripts.run_final_verification
```

The [acceptance report](docs/FINAL_ACCEPTANCE_REPORT.md) contains the complete verification sequence. The original evaluation is implemented in [scripts.evaluate_support](scripts/evaluate_support.py).

## Usage examples

Ask two ticket questions in the same conversation:

```sh
.venv311/bin/python -m scripts.ask_support \
  'Check OLA-0001 status.' \
  'What is its escalation score?'
```

Ask a policy question:

```sh
.venv311/bin/python -m scripts.ask_policy \
  'When can a duplicate charge be refunded?'
```

Start the local API with one worker:

```sh
.venv311/bin/python -m scripts.serve_api --port 8000
```

Then send a request:

```sh
curl --noproxy '*' -s http://127.0.0.1:8000/ask \
  -H 'Content-Type: application/json' \
  -d '{"session_id":"demo","query":"Check OLA-0001 status."}'
```

FastAPI provides typed `POST /ask`, `POST /reset-session`, and multi-turn WebSocket `/ws/chat` endpoints. Sessions, memory, cache, and serialized crew execution are process-local, so the server must use one worker.

## Dataset and knowledge base

[dataset.py](dataset.py) generates **60** tickets using seed **42** and an isolated `random.Random`. Records are generated rather than hand-edited.

- Categories: Billing, Technical Issue, Account Access, Product Defect, and General Inquiry; weights **20, 20, 20, 20, 20**.
- Statuses: Open, In Progress, Escalated, Resolved, and Closed; weights **20, 25, 20, 20, 15**.
- Resolution time: **1–168** hours globally, with category-specific ranges.
- **Range rationale:** one hour supports simple inquiries, while up to one week allows specialist defect investigation.
- Ticket age: integer 0–30 days, with terminal tickets old enough to cover their resolution time.
- Optional fabricated amount: INR **0–5000**, drawn uniformly.
- `reopen_count`: integer 0–3 from a separate random stream using seed 43; the original fields retain their seed-42 draw order.

The generated category counts are **20/10/8/9/13**, and status counts are **12/13/14/10/11**, in the orders above. Escalation is **14/60 = 23.33%**.

[knowledge_base/](knowledge_base/) contains 12 original **fabricated capstone policies**, each four sentences long. They cover priority, severity SLA, escalation, refunds, communication channels, business hours, repeat complaints, service credits, feedback, VIP handling, outages, and ticket retention.

Ticket urgency uses:

`round(0.4*escalated + 0.3*(days_since_created/30) + 0.3*(reopen_count/3), 6)`

The nearest-rank 80th-percentile threshold is **0.55**. Scores strictly above it produce 12 recommendations, including non-escalated tickets OLA-0007 and OLA-0022 at **0.57**. This is a triage heuristic, not an SLA decision or automatic ticket change.

## Retrieval and evaluation

Two separate cosine Chroma collections use real local 384-dimensional embeddings: fixed chunks of 300 characters with 60-character overlap, and chunks of two sentences. They contain 33 fixed chunks and 24 sentence chunks. Each query retrieves the top three chunks and answers only from retrieved evidence.

Measured top-1 cosine calibration:

| Query | Scope | Fixed | Sentence |
|---|---|---:|---:|
| VIP handling | In | 0.72448504 | 0.74592054 |
| Feedback after resolution | In | 0.72365928 | 0.73351645 |
| Repeat complaint within 30 days | In | 0.68994534 | 0.68911171 |
| Photosynthesis | Out | 0.09160292 | 0.07866859 |
| Chocolate cake | Out | 0.01842099 | 0.01867789 |

The midpoint thresholds are **0.390774130821228** for fixed chunks and **0.38389015197753906** for sentence chunks. Below the selected threshold, the system returns: “I don't know based on the available policy documents.” These examples establish separation only for the measured sample.

On six labelled in-scope queries, fixed chunks achieved mean document precision/recall of **1.0/1.0**. Sentence chunks achieved **0.555556/1.0**. Fixed chunking is therefore selected for this corpus because it retrieved fewer irrelevant parent documents; this result should be reevaluated on a larger corpus. [Detailed retrieval evidence](evidence/final_rag.md) includes the queries, chunk IDs, parent-document mapping, fractions, and fallback case.

The deterministic judge scores actual responses and evidence:

| Evaluation set | Cases | Accuracy | Grounding | Completeness | Safety |
|---|---:|---:|---:|---:|---:|
| Original | 15 | 1.0 | 1.0 | 1.0 | 1.0 |
| Additional | 5 | 0.8 | 1.0 | 0.7 | 1.0 |

The additional cases deliberately retain two measured weaknesses: one answer gives related refund evidence without refusing an undocumented entitlement, and one covers only two of four requested facts. Grounding therefore does not imply that every part of a question was answered. [Original results](evidence/v2_original_evaluation.md), [additional results](evidence/v2_extra_evaluation.md), and [negative fixtures](evidence/v2_judge_fixtures.json) preserve the complete calculations.

## Guardrails, governance and limitations

The project applies four governance layers: fabricated and masked data; evidence-only model adapters and independent review; identity-bound read-only tools; and offline runtime controls with request budgets. Domain risk is **Medium** because incorrect customer-support advice can affect customers. Operational autonomy is **Low** because the system cannot mutate records, issue payments, deploy services, or delegate tools freely.

Per-request caps are 50,000 simulated tokens and USD 0.10 across CrewAI and review. Actual model spending is zero. Guards run before memory, caching, model calls, and logging. Exactly one masked JSONL record is written for each HTTP request or WebSocket user message.

The project remains a local capstone prototype. MOCK scores are lexical and extractive proxies on a small known corpus, not evidence of general semantic quality or adversarial robustness. Pattern-based masking does not cover arbitrary names, addresses, or payment details. Python audit hooks are not an operating-system firewall. Sessions and cache have no persistence or production authentication.

## Documentation

- [Acceptance report](docs/FINAL_ACCEPTANCE_REPORT.md): complete verification commands, results, and evidence links.
- [Project status](docs/PROJECT_STATUS.md): concise current state and measured results.
- [Learnings](docs/LEARNINGS.md): retrieval findings, a documented lookup failure, and requirements for a real model.
- [Change record](docs/CHANGELOG_V2.md): implementation and documentation history.
- [Development process](docs/DEVELOPMENT_PROCESS.md), [requirements tracker](docs/REQUIREMENTS_TRACKER.md), and [error log](docs/ERROR_LOG.md): detailed audit trail.

Version 1 remains preserved by the `v1.0.0` tag, with its acceptance record in [the archive](docs/archive/v1_FINAL_ACCEPTANCE_REPORT.md). Current documentation and evidence describe the improved implementation.

## AI assistance

AI assistance contributed to scaffolding, dataset and policy drafting, implementation, debugging, test execution, documentation, and review. Generated work was checked through executed tests, retained failures, and negative fixtures. The repository does not establish which design or testing work the student performed personally.

I used AI assistance throughout development. The repository records the implementation, executed verification, and known limitations.
