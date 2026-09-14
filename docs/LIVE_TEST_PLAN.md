# Live Studionet test plan (v2)

Target network: **Studionet, chain 61999**.

Do not submit until every finalized transaction below has been recorded in `DEPLOYMENT_EVIDENCE.md`, with the superseded v1 deployment clearly separated from this v2 evidence.

## A. Deployment

- deploy `contracts/auditlot.py` (v2, bonded assessment-locked design);
- confirm deployment finalizes;
- record contract address and tx hash;
- read `next_batch_id`/initial state through Studio.

## B. Happy-path certification

Create a six-item immutable manifest with a rubric that four or more known-good items satisfy. Use sample size 3 and threshold 6667 bps. Both producer and entropy partner post the same bond (at least `MIN_BOND_ATOMS`).

- producer creates batch with secret commitment (bonded);
- designated entropy partner joins with independent commitment (matching bond);
- reveal partner secret;
- reveal producer secret;
- verify `SAMPLE_READY` and three unique indexes;
- audit all three slots;
- settle;
- verify terminal certificate, counts, and that **both bonds were refunded in full**;
- verify `get_assessment(assessment_id).resolved == true`.

Expected terminal state: `CERTIFIED` when every sampled item is PASS.

## C. Rejected batch

Create an intentionally failing batch/rubric combination where sampled failures force the pass ratio below the threshold.

Expected: `REJECTED`, with both bonds still refunded in full (a fairly-drawn REJECTED result is not itself penalized).

## D. Inconclusive fail-closed path

After committing a manifest, alter one sampled item's hosted bytes or use a deliberately mismatching item hash.

Expected sampled result: `INCONCLUSIVE`.
Expected terminal batch: `INCONCLUSIVE`, both bonds still refunded in full.

## E. Commitment mismatch

- join with valid partner commitment;
- attempt to reveal a different partner secret.

Expected: deterministic user error; no state advancement.

## F. Sampling uniqueness

Use `item_count=10, sample_size=10` (a dedicated assessment; does not need to be settled to prove the property — reading `sample_indices` right after `SAMPLE_READY` is sufficient).
Expected: exactly 10 unique indexes, each 0..9.

## G. Non-reveal liveness, bond forfeiture, and the retry cap

- create and match a batch with a short future reveal deadline, posting a bond well above `MIN_BOND_ATOMS` so the forfeiture amount is unambiguous in the transaction/balance evidence;
- reveal only one side;
- after the transaction-time deadline, call `abort_non_reveal`;
- verify: batch `ABORTED`; the revealing party's balance increases by (its own bond back) + (the non-revealer's forfeited bond) — i.e. `2x` the posted bond; the non-revealer receives nothing;
- verify `get_assessment(assessment_id).abort_count == 1` and `resolved == false`;
- **retry is still possible** (not a trivial permanent DoS from one non-reveal): create a new batch for the same assessment reusing the exact locked `item_count`/`sample_size`/`min_pass_bps`/`bond_atoms`;
- repeat the non-reveal + abort sequence until `abort_count == MAX_ABORTS_PER_ASSESSMENT` (3);
- verify a further `create_batch` for the same assessment now reverts with the "permanently retired" error — the retry cap actually triggers, live, not just in direct-mode tests.

## H. Replay, state-machine, and assessment-identity rejection

Attempt, and verify every call is rejected deterministically:

- join twice;
- reveal twice;
- audit a resolved sample slot twice;
- settle before all samples are audited;
- settle a terminal batch again;
- reuse an already-used commitment hash (any assessment, either role);
- create a new batch for an assessment that already has an active (non-terminal, non-aborted) batch in progress;
- create a new batch for an assessment that already produced a resolved (CERTIFIED/REJECTED/INCONCLUSIVE) result — including with a different `sample_size`/`min_pass_bps` than the original, to confirm the resolved-lock is not bypassable by changing sampling parameters;
- retry an unresolved (aborted) assessment with sampling parameters or a bond that does not match the assessment's locked values.

## I. Validator independence

Use Studio validator traces/logs (or `genlayer receipt`'s per-round-participant execution records, which carry equivalent information — see `docs/DEPLOYMENT_EVIDENCE.md` for which was actually used) to capture evidence that leader and validators separately fetch the manifest/item and independently run the semantic judgement. Include a screenshot or log excerpt in the submission pack if the portal supports it. Clearly state whether this was directly observed from a live receipt/trace or only documented as expected behavior — do not present undemonstrated behavior as verified.
