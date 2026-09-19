# AuditLot

**Blind semantic sampling for large batches on GenLayer.**

AuditLot is a standalone Intelligent Contract primitive for certifying large batches without asking GenLayer validators to inspect every item and without letting the producer choose the audited examples.

It uses a two-party, bonded commit/reveal entropy ceremony to select a unique sample *after* an immutable batch manifest is committed. Each selected item is independently fetched and hash-verified by validators, then semantically judged against a rubric that was frozen before the sample existed. Batch settlement is deterministic.

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
producer entropy commitment (bonded)
      +
independent partner entropy commitment (bonded, matching)
      ↓
both reveal after commitments are fixed
      ↓
deterministic unpredictable sample
      ↓
validators independently fetch + hash-check each sampled item
      ↓
semantic PASS / FAIL / INCONCLUSIVE per item
      ↓
deterministic batch certificate, assessment marked resolved
```

**On the fairness claim:** if both parties choose fresh, independent secrets, neither can determine the sample before both commitments are fixed. This does **not** by itself mean the reveal step is fair against a party willing to preview the result before deciding whether to submit its own reveal — see [`docs/SECURITY_MODEL.md`](docs/SECURITY_MODEL.md) for the precise, narrowly-qualified guarantee AuditLot actually makes (bonding + a capped retry count, not unconditional unbiasedness) and why: no verifiable-random-function or randomness-beacon primitive is exposed to Intelligent Contracts on this platform as of this writing.

## What GenLayer decides vs what code decides

**Consensus decides only:** whether each sampled immutable text artefact clearly passes, fails, or is inconclusive against the already-frozen rubric.

**Deterministic code decides:** commitment validity, entropy combination, sample indexes, uniqueness, manifest/item hashes, counters, threshold arithmetic, lifecycle transitions, bond accounting, and the final certificate hash.

The LLM never chooses the sample, never changes the threshold, and never decides the final batch status directly.

## Manifest format

AuditLot accepts immutable UTF-8 text artefacts over HTTPS.

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

The exact manifest response body is itself hashed and pinned on-chain. Every sampled item's exact response body is also hash-pinned inside the manifest. (This is the manifest *data format* version, separate from the sampling-protocol version below; a v2 protocol contract still reads `"version": "auditlot-1"` manifests.)

Use `scripts/build_manifest.py` to generate a canonical manifest and its digest.

## Assessments and batches

An **assessment** is the canonical identity of what's being tested: this exact manifest plus this exact rubric, on this exact chain and contract. Get it from the deployed contract itself —

```bash
genlayer call <contract> assessment_id_for --args <manifest_sha256> <rubric_sha256>
```

— rather than reimplementing the hash formula off-chain. A **batch** is one concrete attempt at an assessment. An assessment can be resolved (produce one real, fully-sampled, fully-audited terminal result) **at most once, ever** — once resolved, `create_batch` refuses any further attempt for that manifest+rubric, at any sample size or threshold, so a producer cannot cherry-pick a favorable result out of several real draws. See `docs/SECURITY_MODEL.md` and `docs/ARCHITECTURE.md`.

## Lifecycle

1. **Producer:** build immutable manifest and rubric.
2. **Producer:** look up the assessment id with `assessment_id_for(manifest_sha256, rubric_sha256)`, then generate a fresh secret and commitment with `scripts/commit.py <assessment_id> producer`.
3. **Producer:** call `create_batch(...)` (payable — the attached GEN becomes the bond both sides must post), naming an independent entropy partner.
4. **Partner:** generate a fresh secret/commitment with `scripts/commit.py <assessment_id> partner`, then call `join_entropy(...)` (payable, must match the producer's bond exactly).
5. **Producer + partner:** each calls `reveal_entropy(...)` before the deadline.
6. Once both reveals match their commitments, AuditLot deterministically derives unique sample indexes and enters `SAMPLE_READY`.
7. Anyone can call `audit_sample(batch_id, slot)` for every sample slot.
8. Anyone can call `settle(batch_id)` after every selected slot is resolved — both bonds are refunded in full, regardless of the terminal outcome, and the assessment is marked resolved.
9. The terminal status is `CERTIFIED`, `REJECTED`, or `INCONCLUSIVE`.
10. If either side fails to reveal by the deadline, anyone can call `abort_non_reveal(...)`: the non-revealer's bond is forfeited to whichever side did reveal (or both refunded if neither did). A retry for the same assessment is allowed, up to `MAX_ABORTS_PER_ASSESSMENT` (3) times, reusing the exact locked sampling parameters and bond.
11. `cancel_unmatched(...)` lets the producer withdraw (and get its bond back) an `OPEN` batch nobody has joined yet.

`IAuditLot` (in `contracts/auditlot.py`) declares the full public interface for downstream integrators — every method above, including `abort_non_reveal` and `cancel_unmatched`, not just the happy-path methods.

**`create_batch` and `join_entropy` signal rejection by return value, not by reverting.** Both are payable, and GenVM credits attached value to the contract *before* the method body runs and does not roll that credit back on revert — so if either method reverted on invalid input, the caller's GEN would be stranded with no way to refund it (this happened during live testing on Studionet and is the reason for this design). Instead, both methods catch every internal failure, refund the attached value to the caller, emit `CreateBatchRejected(sender, reason)` / `JoinEntropyRejected(batch_id, sender, reason)`, and return a sentinel (`u256(0)` for `create_batch`, `False` for `join_entropy`) from an otherwise-successful call. Integrators must check the return value (or the rejection event), not `expect_revert`-style handling, to detect failure from these two methods. Every other write method still raises normally on failure.

## Settlement rule

- If **any** sampled item is `INCONCLUSIVE`, the whole batch is `INCONCLUSIVE`. AuditLot does not turn missing evidence into a pass or fail.
- Otherwise `pass_bps = PASS * 10,000 / sample_size`.
- `pass_bps >= min_pass_bps` → `CERTIFIED`.
- Otherwise → `REJECTED`.

This conservative policy makes the certificate easy for other builders to reason about.

## Commitments

```text
assessment_id = sha256("AUDITLOT_ASSESSMENT_V2|" + chain_id + "|" + contract_address + "|" + manifest_sha256 + "|" + rubric_sha256)
commitment    = sha256("AUDITLOT_COMMIT_V2|" + assessment_id + "|" + role + "|" + secret)   # role: "producer" | "partner"
```

Get `assessment_id` from the deployed contract's `assessment_id_for` view method; don't hand-roll the hash. Every commitment the contract accepts must be globally fresh — reusing one (even for a different assessment or role) is rejected on-chain, not just discouraged by convention, because a revealed secret is permanently public and reusing it hands away real entropy.

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

Current contract (v0.2.3): `0xb5FBe4396d38DeC89aC0bA9712E4Eaf0e17bE714` on Studionet (chain 61999). The live acceptance matrix (certified, rejected, inconclusive, wrong secret, replays, 10-of-10 sampling, non-reveal forfeiture, and the retry cap) was executed against it; every transaction hash is in `docs/DEPLOYMENT_EVIDENCE.md`.

Two things to know when deploying yourself: `genlayer deploy` takes no `--args` for this contract (passing `--args '[]'` sends a stray argument and the constructor crashes, even though the deploy transaction still shows as agreed), and the `genlayer` CLI cannot attach value to a write call, so the payable methods (`create_batch`, `join_entropy`) must be called through the official `genlayer-js` SDK.

See `docs/DEPLOYMENT_EVIDENCE.md`, which clearly separates the superseded v1 deployment (the pre-fairness-redesign contract; do not use) from the current v2 deployment evidence.

## Security boundaries

AuditLot proves a bounded statement:

> A deterministic blind sample from this exact manifest achieved this terminal result against this exact rubric under GenLayer consensus, for this specific, permanently-non-retriable assessment.

It does **not** prove every unsampled item is good, does not prove the producer disclosed every real-world item, does not claim statistical guarantees beyond the sample policy chosen by the user, and does not claim the blind sample is unconditionally unbiased against a party willing to forfeit its bond. See `docs/SECURITY_MODEL.md` for the full, precise claim.

## Repository map

```text
contracts/auditlot.py          standalone Intelligent Contract
scripts/build_manifest.py      canonical manifest helper
scripts/commit.py              entropy commitment helper (v2: assessment + role bound)
scripts/preflight.py           network/syntax/repository checks
tests/test_protocol_model.py   deterministic protocol-model tests
tests/direct/                  GenVM direct-mode (GLSim) execution tests
fixtures/certified/            live-demo fixture: all sampled items PASS
fixtures/rejected/             live-demo fixture: all sampled items FAIL
fixtures/inconclusive/         live-demo fixture: intentional hash mismatch
docs/ARCHITECTURE.md           state and consensus architecture
docs/SECURITY_MODEL.md         threat model, last-revealer analysis, and epistemic limits
docs/LIVE_TEST_PLAN.md         Studio acceptance matrix
docs/DEPLOYMENT_EVIDENCE.md    v1 (superseded) and v2 deployment + live matrix evidence
SUBMISSION.md                   reviewer-facing submission draft
```

## Licence

MIT.
