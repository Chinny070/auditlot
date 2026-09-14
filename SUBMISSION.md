# AuditLot — submission draft

## Purpose

AuditLot is a reusable blind semantic sampling primitive for large batches. It lets a producer commit an immutable batch, derive an unpredictable unique sample through two-party commit/reveal entropy, and obtain a consensus-backed certification without inspecting every item or allowing the producer to choose the examples.

## Why GenLayer is required

Everything except the semantic quality judgement can be deterministic. The hard boundary is evaluating whether arbitrary immutable text artefacts satisfy a frozen natural-language rubric. AuditLot places only that judgement inside GenLayer consensus. Validators independently refetch the exact pinned evidence and independently reproduce the outcome.

## Consensus design

For each selected item, leader and validators independently:

- fetch the exact pinned manifest;
- verify its SHA-256 digest and item count;
- resolve the deterministic sampled index;
- fetch the selected immutable item;
- verify its SHA-256 digest;
- judge the item against the precommitted rubric;
- agree on `PASS`, `FAIL`, or `INCONCLUSIVE` plus exact evidence identity fields.

Validator code does not merely validate output format.

## State design

AuditLot separates semantic judgement from protocol mechanics. Commitments, reveals, seed derivation, unbiased unique sampling, counters, thresholds, lifecycle transitions and the final certificate digest are deterministic.

The sample exists only after both commitments are fixed. A missing reveal cannot silently fall back to producer-selected examples; the batch eventually terminates `ABORTED`.

## Reuse

The contract exposes terminal certificate data and an `is_certified(batch_id, expected_certificate_sha256)` view for downstream consumers. Builders can use it for AI-generated catalogues, annotation datasets, document-processing runs, code-migration batches, content moderation batches, agent fulfilment fleets and other high-volume outputs where exhaustive GenLayer evaluation would be wasteful.

## Scope

AuditLot certifies only the sampled evidence against the frozen rubric. It does not claim that every unsampled item is correct or that a submitted manifest exhaustively represents every real-world deliverable.

## Testing evidence

See `docs/LIVE_TEST_PLAN.md` and `docs/DEPLOYMENT_EVIDENCE.md`. Deployment evidence must be populated from finalized Studionet transactions before submission.
