# AuditLot

**Blind semantic sampling for large batches on GenLayer.**

AuditLot is a standalone Intelligent Contract primitive for certifying large batches without asking GenLayer validators to inspect every item and without letting the producer choose the audited examples.

It uses a two-party commit/reveal entropy ceremony to select a unique sample *after* an immutable batch manifest is committed. Each selected item is independently fetched and hash-verified by validators, then semantically judged against a rubric that was frozen before the sample existed. Batch settlement is deterministic.

## Network

This repository targets **Studionet only**:

- network preset: `studionet`
- chain ID: **61999**
- Studio: `https://studio.genlayer.com`
- GenLayer RPC: `https://studio.genlayer.com/api`

The contract uses the stable `py-genlayer` dependency line already used by stable Studionet contracts.

## No frontend

There is intentionally **no frontend**. AuditLot is a reusable contract primitive, not a full product. Reviewers and builders interact through Studio, CLI, SDKs, or their own consuming contracts.

## Why this exists

A producer with 5,000 deliverables has two bad options:

1. ask validators to inspect every item, which is wasteful; or
2. let the producer choose a few examples, which is gameable.

AuditLot creates a third option:

```text
immutable manifest
      ↓
producer entropy commitment
      +
independent partner entropy commitment
      ↓
both reveal after commitments are fixed
      ↓
deterministic unpredictable sample
      ↓
validators independently fetch + hash-check each sampled item
      ↓
semantic PASS / FAIL / INCONCLUSIVE per item
      ↓
deterministic batch certificate
```

Neither party can know the final sample when it makes its commitment as long as at least one of the two secrets is honestly chosen and kept private until reveal.

## What GenLayer decides vs what code decides

**Consensus decides only:** whether each sampled immutable text artefact clearly passes, fails, or is inconclusive against the already-frozen rubric.

**Deterministic code decides:** commitment validity, entropy combination, sample indexes, uniqueness, manifest/item hashes, counters, threshold arithmetic, lifecycle transitions, and the final certificate hash.

The LLM never chooses the sample, never changes the threshold, and never decides the final batch status directly.

## Manifest format

AuditLot v1 accepts immutable UTF-8 text artefacts over HTTPS.

```json
{
  "version": "auditlot-1",
  "items": [
    {
      "id": "deliverable-001",
      "url": "https://example.org/batch/item-001.txt",
      "sha256": "<sha256 of exact response body>"
    }
  ]
}
```

The exact manifest response body is itself hashed and pinned on-chain. Every sampled item's exact response body is also hash-pinned inside the manifest.

Use `scripts/build_manifest.py` to generate a canonical manifest and its digest.

## Lifecycle

1. **Producer:** build immutable manifest and rubric.
2. **Producer:** generate a fresh secret and commitment with `scripts/commit.py`.
3. **Producer:** call `create_batch(...)`, naming an independent entropy partner.
4. **Partner:** generate a fresh secret/commitment and call `join_entropy(...)`.
5. **Producer + partner:** each calls `reveal_entropy(...)` before the deadline.
6. Once both reveals match their commitments, AuditLot deterministically derives unique sample indexes and enters `SAMPLE_READY`.
7. Anyone can call `audit_sample(batch_id, slot)` for every sample slot.
8. Anyone can call `settle(batch_id)` after every selected slot is resolved.
9. The terminal status is `CERTIFIED`, `REJECTED`, or `INCONCLUSIVE`.

## Settlement rule

- If **any** sampled item is `INCONCLUSIVE`, the whole batch is `INCONCLUSIVE`. AuditLot does not turn missing evidence into a pass or fail.
- Otherwise `pass_bps = PASS * 10,000 / sample_size`.
- `pass_bps >= min_pass_bps` → `CERTIFIED`.
- Otherwise → `REJECTED`.

This conservative policy makes the certificate easy for other builders to reason about.

## Commitments

The commitment is:

```text
sha256("AUDITLOT_V1|" + secret)
```

Always use a fresh high-entropy secret for every batch.

## Deployment

```bash
genlayer network set studionet
genlayer deploy --contract contracts/auditlot.py
```

Before deployment:

```bash
python scripts/preflight.py
python -m unittest discover -s tests -v
gltest tests/direct -v
genvm-lint check contracts/auditlot.py
```

Then deploy and execute the live matrix in `docs/LIVE_TEST_PLAN.md` from Studio. Record the finalized transaction hashes and deployed address in `docs/DEPLOYMENT_EVIDENCE.md` before submission.

### Live on Studionet

AuditLot is deployed and finalized at `0x601b8d1Db0fEC038c9281DB0c9897A2481bbeFc9` on Studionet (chain 61999). The complete live acceptance matrix — a CERTIFIED batch, a REJECTED batch, an INCONCLUSIVE (fail-closed hash-mismatch) batch, commitment-mismatch rejection, full-permutation sample uniqueness, non-reveal `ABORTED` liveness, and every replay/state-machine rejection in `docs/LIVE_TEST_PLAN.md` — was executed with real finalized transactions. See `docs/DEPLOYMENT_EVIDENCE.md` for every transaction hash and outcome.

## Security boundaries

AuditLot proves a bounded statement:

> A deterministic blind sample from this exact manifest achieved this terminal result against this exact rubric under GenLayer consensus.

It does **not** prove every unsampled item is good, does not prove the producer disclosed every real-world item, and does not claim statistical guarantees beyond the sample policy chosen by the user. See `docs/SECURITY_MODEL.md`.

## Repository map

```text
contracts/auditlot.py          standalone Intelligent Contract
scripts/build_manifest.py      canonical manifest helper
scripts/commit.py              entropy commitment helper
scripts/preflight.py           network/syntax/repository checks
tests/test_protocol_model.py   deterministic protocol-model tests
tests/direct/                  GenVM direct-mode (GLSim) execution tests
fixtures/certified/            live-demo fixture: all sampled items PASS
fixtures/rejected/             live-demo fixture: all sampled items FAIL
fixtures/inconclusive/         live-demo fixture: intentional hash mismatch
docs/ARCHITECTURE.md           state and consensus architecture
docs/SECURITY_MODEL.md         threat model and epistemic limits
docs/LIVE_TEST_PLAN.md         Studio acceptance matrix
docs/DEPLOYMENT_EVIDENCE.md    finalized Studionet deployment + live matrix evidence
SUBMISSION.md                   reviewer-facing submission draft
```

## Licence

MIT.
