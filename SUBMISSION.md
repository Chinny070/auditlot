# AuditLot — submission draft

## Purpose

AuditLot is a reusable blind semantic sampling primitive for large batches. It lets a producer commit an immutable batch, derive a sample through a bonded, two-party commit/reveal entropy ceremony, and obtain a consensus-backed certification without inspecting every item or allowing the producer to choose the examples — subject to the specific, narrowly-qualified fairness guarantee in `docs/SECURITY_MODEL.md` (bonding and a capped retry count, not unconditional unbiasedness; see that document for why no stronger primitive is available on this platform today).

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

AuditLot separates semantic judgement from protocol mechanics. Commitments, reveals, seed derivation, sample-index selection, counters, thresholds, lifecycle transitions, bond accounting, and the final certificate digest are deterministic.

Given a fixed seed, index selection is unbiased by construction (domain-separated rejection sampling avoids modulo bias — see `tests/test_protocol_model.py`). This is a distinct, narrower claim than "the two-party reveal process cannot be gamed"; see `docs/SECURITY_MODEL.md` for the latter.

The sample exists only after both commitments are fixed. A missing reveal cannot silently fall back to producer-selected examples; the batch eventually terminates `ABORTED`, with the non-revealing party's bond forfeited to whichever party did reveal (or both bonds refunded if neither did).

## Fairness redesign (v2)

A strict review identified that v1's commit/reveal scheme let whichever party revealed second privately preview the resulting sample and withhold its own reveal — for free — if it disliked the outcome, and let a producer create unlimited fresh batches for the same manifest and rubric after an unfavorable real result. v2 addresses both:

- **Canonical assessment identity.** `assessment_id_for(manifest_sha256, rubric_sha256)` is the identity of what's being tested. Once an assessment produces one real, fully-sampled, fully-audited terminal result, `create_batch` permanently refuses any further attempt for it — structurally, not by convention.
- **Bonded commit/reveal.** Both `create_batch` and `join_entropy` are payable; a party who fails to reveal after the other one did forfeits its entire bond to the honest party. A retry after a non-reveal abort is capped at `MAX_ABORTS_PER_ASSESSMENT` attempts.
- **Domain-separated, non-reusable commitments.** Every commitment is bound to the assessment, participant role, and protocol version, and can never be reused across any assessment or role on this contract.

See `docs/SECURITY_MODEL.md` for the full analysis (what this does and does not prevent) and `docs/DEPLOYMENT_EVIDENCE.md` for live proof.

## Reuse

The contract exposes terminal certificate data, `get_assessment`/`assessment_id_for` for retry-policy transparency, and an `is_certified(batch_id, expected_certificate_sha256)` view for downstream consumers. `IAuditLot` declares the complete public lifecycle, including `abort_non_reveal` and `cancel_unmatched`. Builders can use it for AI-generated catalogues, annotation datasets, document-processing runs, code-migration batches, content moderation batches, agent fulfilment fleets and other high-volume outputs where exhaustive GenLayer evaluation would be wasteful.

## Scope

AuditLot certifies only the sampled evidence against the frozen rubric, for one specific, permanently-non-retriable assessment. It does not claim that every unsampled item is correct, that a submitted manifest exhaustively represents every real-world deliverable, or that the blind sample is unconditionally unbiased against a party willing to forfeit its bond.

## Testing evidence

- `python scripts/preflight.py` and `python -m unittest discover -s tests -v` — deterministic protocol-model checks, including a mechanical demonstration of the last-revealer preview this design bounds rather than eliminates.
- `gltest tests/direct -v` — direct-mode (GLSim) execution tests against the real contract file: storage (`TreeMap`, `DynArray`), payable bonding and forfeiture-target accounting (via a recorded-transfer hook), assessment resolved-lock and retry-parameter-lock enforcement, commitment-reuse rejection, URL/calendar-date/missing-timestamp validation, and independently-verified validator agreement/disagreement.
- `genvm-lint check contracts/auditlot.py` — AST safety lint, SDK-based semantic validation, and Pyright type-checking all pass.
- CI runs the full check set (preflight, compilation, unit tests, direct-mode suite, lint, secret/artifact scan) on every push and pull request; see `.github/workflows/ci.yml`.
- See `docs/DEPLOYMENT_EVIDENCE.md` for live Studionet (chain 61999) deployment and acceptance-matrix evidence, with the superseded v1 deployment clearly separated from the current v2 evidence.
