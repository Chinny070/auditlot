# Live Studionet test plan

Target network: **Studionet, chain 61999**.

Do not submit until every finalized transaction below has been recorded in `DEPLOYMENT_EVIDENCE.md`.

## A. Deployment

- deploy `contracts/auditlot.py`;
- confirm deployment finalizes;
- record contract address and tx hash;
- read `next_batch_id`/initial state through Studio.

## B. Happy-path certification

Create a six-item immutable manifest with a rubric that four or more known-good items satisfy. Use sample size 3 and threshold 6667 bps.

- producer creates batch with secret commitment;
- designated entropy partner joins with independent commitment;
- reveal partner secret;
- reveal producer secret;
- verify `SAMPLE_READY` and three unique indexes;
- audit all three slots;
- settle;
- verify terminal certificate and counts.

Expected terminal state: `CERTIFIED` when every sampled item is PASS.

## C. Rejected batch

Create an intentionally failing batch/rubric combination where sampled failures force the pass ratio below the threshold.

Expected: `REJECTED`.

## D. Inconclusive fail-closed path

After committing a manifest, alter one sampled item's hosted bytes or use a deliberately mismatching item hash.

Expected sampled result: `INCONCLUSIVE`.
Expected terminal batch: `INCONCLUSIVE`.

## E. Commitment mismatch

- join with valid partner commitment;
- attempt to reveal a different partner secret.

Expected: deterministic user error; no state advancement.

## F. Sampling uniqueness

Use `item_count=10`, `sample_size=10`.
Expected: exactly 10 unique indexes, each 0..9.

## G. Non-reveal liveness

- create and match a batch with a short future reveal deadline;
- reveal only one side;
- after the transaction-time deadline, call `abort_non_reveal`.

Expected: `ABORTED`.

## H. Replay and state-machine rejection

Attempt:

- join twice;
- reveal twice;
- audit a resolved sample slot twice;
- settle before all samples are audited;
- settle a terminal batch again.

Every call must be rejected deterministically.

## I. Validator independence

Use Studio validator traces/logs to capture evidence that leader and validators separately fetch the manifest/item and independently run the semantic judgement. Include a screenshot or log excerpt in the submission pack if the portal supports it.
