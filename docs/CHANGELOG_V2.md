# Change record

## Vercel production deployment — 8 November 2026

Commit `1f3ebf1` added a CPU-only Python 3.11 container, Vercel Container configuration, public root and health routes, and deployment instructions. The production API at [final-capstone-ola-domain-support-a.vercel.app](https://final-capstone-ola-domain-support-a.vercel.app) passed HTTPS root, health, policy, session, and reset checks plus secure WebSocket ticket lookup. The [deployment record](../evidence/vercel_deployment_verification.json) states the verified scope and limitations.

## Final capstone publication — 7 November 2026

The verified project, refreshed evidence, and complete Git history were published as [Final Capstone — Ola Domain Support Agent (CrewAI)](https://github.com/nitesh2mithu/final-capstone-ola-domain-support-agent-crewai). The earlier Version 1 and Version 2 repositories remain unchanged as provenance records.

## Judge source verification and grader map — 8 November 2026

The deterministic judge now treats retrieval payloads as untrusted inputs. Before scoring, it independently reloads the canonical policy files, regenerates fixed and sentence chunks, and requires every RAG hit to match its canonical chunk ID, parent, text, metadata and raw source. Negative fixtures reject forged text, a wrong parent and an unknown chunk ID without changing the frozen queries, expected facts, prompts, rubrics or score arithmetic.

The README now includes a compact 16-task implementation/evidence map, the AutoGen approval/revision, cache and WebSocket disconnect proof values, an explicit statement that the five extra cases were written and frozen before execution, and a distinction between native macOS verification and Vercel's clean Linux container build. The single-worker architecture and detailed audit records remain unchanged.

## Documentation finalization — 7 November 2026

The README now leads with the support problem, end-to-end flow, setup, and usage. Required dataset, retrieval, and evaluation measurements remain in the README, while release history and extended verification details link to their dedicated records.

The project status was reduced to the current state, measured results, limitations, and next action. Superseded milestone snapshots remain available through Git history, the development process, the error log, archived evidence, and the final acceptance report.

## Version 2 implementation

### Repository layout

Documentation moved under `docs/`, and historical Version 1 evidence moved under `evidence/archive/v1/`. The [layout record](../evidence/v2_layout_changes.json) lists the exact moves and path-only manifest changes. Archived records continue to describe Version 1.

### Escalation behavior

Version 2 added an independently seeded `reopen_count` field while preserving the original seed-42 fields and their random draw order. The score changed from `0.6*escalated + 0.4*(days_since_created/30)` to:

`0.4*escalated + 0.3*(days_since_created/30) + 0.3*(reopen_count/3)`

Scores are rounded to six decimals. The nearest-rank 80th percentile is used as the threshold, and a strict greater-than comparison excludes ties. The [change evidence](../evidence/v2_escalation_change.json) contains hashes, thresholds, examples, and independent calculations for both versions.

The updated tests cover the formula, threshold, value ranges, types, original-record invariance, and all 60 ticket lookups. The preserved failure record documents the lookup-reference error found during integration and its verified correction.

### Evaluation extension

The original 15 labels, judge prompt, and rubric remained unchanged. Five new cases were [frozen before execution](../evidence/v2_extra_freeze.json): two near-domain cases, two multi-topic or ambiguous cases, and one injection case with a fabricated phone number.

The original set scored **1.0/1.0/1.0/1.0** for Accuracy, Grounding, Completeness, and Safety. The additional set scored **0.8/1.0/0.7/1.0**. Case X01 returned related refund evidence without the required refusal, while X04 covered two of four requested facts. No labels, calibration settings, or crew behavior were changed after observing these results.

### Final review corrections

The final review corrected temporary-path normalization, historical link resolution, directory-link validation, and historical audit output paths. Archived reports remain protected from later verification runs. Failed attempts and their corrections are retained in [the error log](ERROR_LOG.md).

## Publication record — 11 October 2026

[Pull request #1](https://github.com/nitesh2mithu/Ola-Domain-Support-Agent_Manuel-and-AI/pull/1) merged the reviewed implementation with its history intact. Annotated tag `v2.0.0` points to `dae0867753bc7ab17f924a66dd9aa7362e2e8bfa`. A later documentation-only publication record updated `main` without changing the tagged application.

Public tree, README rendering, local links, and required evidence were verified after publication. The Version 1 repository, checkout, and tag remained unchanged. No external service deployment or course-portal submission was performed.
