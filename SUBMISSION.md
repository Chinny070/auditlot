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

- `python scripts/preflight.py` and `python -m unittest discover -s tests -v` — deterministic protocol-model checks (commitment domain separation, unbiased unique sampling, fail-closed settlement math).
- `gltest tests/direct -v` — 37 GenVM direct-mode (GLSim) execution tests against the real contract file, covering storage (`TreeMap`, `DynArray`), decorators, `gl.vm.run_nondet_unsafe` leader/validator closures, and independently-verified validator agreement/disagreement.
- `genvm-lint check contracts/auditlot.py` — AST safety lint, SDK-based semantic validation, and Pyright type-checking all pass.
- Deployed and finalized on Studionet (chain 61999) at `0x601b8d1Db0fEC038c9281DB0c9897A2481bbeFc9`. The full live matrix in `docs/LIVE_TEST_PLAN.md` — CERTIFIED, REJECTED, and INCONCLUSIVE (fail-closed hash-mismatch) batches; commitment-mismatch rejection; full-permutation sample uniqueness; non-reveal `ABORTED` liveness; and every replay/state-machine rejection — was executed with real finalized transactions and independently re-verified validator behavior. See `docs/DEPLOYMENT_EVIDENCE.md` for every transaction hash and outcome.
