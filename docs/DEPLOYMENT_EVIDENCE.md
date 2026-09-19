# Deployment evidence

Target: Studionet, chain 61999.

Fill only with finalized live evidence. Do not fabricate entries.

This repository has been deployed twice. **v1 is superseded and must not be
used**: a strict review found its blind-sample fairness claim was not
defensible (see `docs/SECURITY_MODEL.md` for the full analysis). v2 is the
current, bonded, assessment-locked design in `contracts/auditlot.py`. The
two sections below are kept clearly separate so nobody mistakes v1 evidence
for a claim about v2's (different) contract address, bytecode, and
fairness guarantee.

---

## v2 (current) — bonded, assessment-locked fairness redesign

- **Contract address:** `0xb5FBe4396d38DeC89aC0bA9712E4Eaf0e17bE714` (Studionet, chain 61999, contract version v0.2.3)
- **Deployment transaction:** `0xc34651a1f676639597221a107dfa71edc1a40a717608231dad19c31b97d3628b`
- **Deployment finalized:** `TODO`
- **Source commit deployed:** `117da9d`
- **Deployer:** `0x3A3168d67A110dE79461939047a8f7334ff1423d`
- **Entropy partner account(s) used:** `TODO`

Deployment is gated on: the revised design passing all tests and CI (done —
see the repository's CI run for the commit this evidence file is checked in
alongside), and explicit approval for the exact deploy transaction from the
wallet owner, per this task's instructions. See the final report in this
session for what is pending.

### A. Deployment
- Verified: `genlayer schema` returns the contract's methods. (Two earlier attempts today only looked successful: a bad `--args '[]'` made the constructor crash, so no contract existed.)
- Refund check, verified live: a deliberately invalid `create_batch` with 1000 atoms attached (tx `0xb6ade7490060de40d61a5c02f8eb8798ee1a3346f9711b06f3793b73525538d6`) returned the sentinel, and after finalization the caller's balance was back to exactly its starting value and the contract balance was 0. The previous contract (`0x7Da416E0...D70f`, v0.2.2) lost such refunds because it used a contract-only transfer; that deployment is superseded.
- Not yet done: the live scenarios B-I below.

### B. Happy-path certification (CERTIFIED)
- `TODO`

### C. Rejected batch (REJECTED)
- `TODO`

### D. Inconclusive fail-closed path (INCONCLUSIVE)
- `TODO`

### E. Commitment mismatch
- `TODO`

### F. Sampling uniqueness
- `TODO`

### G. Non-reveal liveness, bond forfeiture, and the retry cap
- `TODO` -- must include: the forfeiture transaction and a balance/transfer
  readback showing the honest party received `2x` its bond; at least one
  successful retry after a single non-reveal abort (proving it is not a
  trivial permanent DoS); and the assessment actually hitting
  `MAX_ABORTS_PER_ASSESSMENT` and being permanently refused a further
  `create_batch` call.

### H. Replay, state-machine, and assessment-identity rejection
- `TODO` -- must include the resolved-lock rejection (retry after a real
  result, including with different sampling parameters) and the
  reused-commitment rejection, in addition to the v1-style replay checks.

### I. Validator independence
- `TODO` -- state plainly whether this was directly observed from a live
  `genlayer receipt`/trace for this v2 deployment, or only asserted.

---

## v1 (superseded) — do not use; kept for audit-trail continuity only

**This deployment used a contract with the last-revealer fairness gap
described in `docs/SECURITY_MODEL.md`. It has no bonding, no assessment
identity, and no retry cap: a producer could create unlimited batches for
the same manifest/rubric and publish only a favorable result. Do not treat
any claim below as applying to the current contract.**

Target: Studionet, chain 61999.

- Contract address: `0x601b8d1Db0fEC038c9281DB0c9897A2481bbeFc9`
- Deployment transaction: `0xc63cc41ab438e38c9772452735f5ad874036717582b967a6aeee8bb9f5d2ad72` — FINALIZED
- Deployer: account `bradbury-e2e`, `0x3A3168d67A110dE79461939047a8f7334ff1423d`
- Entropy partner used throughout: account `continuum`, `0x13AE0C28D06716D2908B5d84c3c0c3d815378f3B`
- Source commit deployed: `92df3aa90c9d4a038438242bca3a93341ac33430` (v1 contract, pre-fairness-redesign)

### Live fixtures used by v1

- Item text commit: `3c2c1c2bb0a86518b6f0e8d7b1657058be487f6e`
- Manifest commit: `b00eb2ad1af207e8923fa9784a8f84c6fdc80ef9`

| Fixture | Manifest URL | `manifest_sha256` |
|---|---|---|
| Certified | `.../b00eb2ad.../fixtures/certified/manifest.json` | `d93cd2099ce611513f210af950a8e8aa0644df73cf10a47497312e7609e6c8d6` |
| Rejected | `.../b00eb2ad.../fixtures/rejected/manifest.json` | `a5a514c5b48c873e9d0e4b5f799d80eb1bf8a9b516377fac823037b53f2af1e8` |
| Inconclusive | `.../b00eb2ad.../fixtures/inconclusive/manifest.json` | `acb70cf9edc22aab009532b18422a65834516e13c1e0b437630d0bc973626709` |

These same fixture files and pinned URLs are reused for v2's live matrix
(the fixture text/manifests themselves were never wrong; only the sampling
protocol was).

### B. Happy-path — batch 1, CERTIFIED

- `create_batch` tx (`batch_id = 1`): `0x34b504a68ecb5a741bca0df3a766cdc6e67b3dc7c907cc117047d9ea419ccc5b` — FINALIZED
- Intermediate transaction hashes (join/reveal x2/audit x3/settle) were not
  individually captured due to a CLI output-capture mistake on this, the
  first live batch of the session. The batch's finalized terminal on-chain
  state was independently re-read afterward:
- Sample indices: `[5, 4, 3]`
- Audited items: `item-5` → PASS, `item-4` → PASS, `item-3` → PASS
- `certificate_sha256`: `689fdb534bd01baa087fc4d8d21e55737d41944c25577dadf5f98a0afc73042d`
- Final `get_certificate(1)`: `CERTIFIED`, `pass_count: 3`, `pass_bps: 10000`

### C. Rejected — batch 2, REJECTED

- `create_batch` (`batch_id = 2`): `0xc6ffcc677c2e664b776afc465fd3f20a89a3b561ef55a0b1987fcf9edfd9021b`
- `join_entropy`: `0xd59fc91feada9260567ea6d3a950517b35c169eaf02dd702751947a3e5205de8`
- partner `reveal_entropy`: `0xf93b26bb10c8f24aa0705127fb0404c9b8b65a7ff58b86f2268f65b02a2deb3c`
- producer `reveal_entropy`: `0x267464cde116ae2c65f90ccd5617cd9580495648fd5cc0461398d72b1a9cb266`
- Sample indices: `[1, 0, 4]`
- `audit_sample(2,0)`: `0x97fdfca76ad5e7133dbac898ca667c396e239d7410ec4ab8a95ae08c3648d288` → `item-1` FAIL
- `audit_sample(2,1)`: `0x5431255b9fec134713e1fc5cedbc176ad623c9d1c6bac769e1efcbcd9ac4195e` → `item-0` FAIL
- `audit_sample(2,2)`: `0x597189e1dff31c0cf1514cb38a2c5f55c070c27d5c7d1d874f656be15f59b7f0` → `item-4` FAIL
- `settle`: `0x640891716e46bb7f4f9e8ba5e8e0ea3747a1ef65595a226f09157fcbf0e7c74c` — FINALIZED
- `certificate_sha256`: `588a8995ed58b150811a188f1e0d2c20415be0a36726494d960a18f69049b080`
- Final `get_certificate(2)`: `REJECTED`, `fail_count: 3`, `pass_bps: 0`

### D. Inconclusive — batch 3, INCONCLUSIVE

- `create_batch` (`batch_id = 3`): `0x002892925c5369c1b8a93ccd431dc39c0ba83ed0c2f5d64bef43231668e708eb`
- `join_entropy`: `0xdb8c451cab6cc23946e216d54135e539c11d48845d96e6feb5928521d3976063`
- partner `reveal_entropy`: `0x26da23b24ff8d33482c2f37f2883b75e6e9da813454a7946421c3aad26dc8440`
- producer `reveal_entropy`: `0xe889801c51a4c27616fd1060d19a8734c30da50427245b45040f4cb802ca214a`
- Sample indices: `[5, 1, 4]`
- `audit_sample(3,0)`: `0x6dd5d56672c9a0f14b877ad066381a3f763ce304648eb5150d0fe5ed798857d0` → INCONCLUSIVE, `item hash mismatch`
- `audit_sample(3,1)`: `0xb8258adcdb28aa536445401baabb9735a260262a3ded25d5a70ac7bd441f84fb` → INCONCLUSIVE, `item hash mismatch`
- `audit_sample(3,2)`: `0x109868745b0754971cf3fd26346b7a78de8afd6a1a18da71e59d9359694d2203` → INCONCLUSIVE, `item hash mismatch`
- `settle`: `0x0d0e8f09231f4ec87f6dd55e0804c5d0e61ade008429d93fa14134c4f5abba86` — FINALIZED
- `certificate_sha256`: `062349d8af3a0c9f03573a22ad45a9b801da2bc99cde8fba9aeb1b4c88a32b5f`
- Final `get_certificate(3)`: `INCONCLUSIVE`, `inconclusive_count: 3`

### E. Commitment mismatch — batch 4

- `create_batch` (`batch_id = 4`): `0x15df2069c02ce9dd9032675c3521804cf659f6abb74702707d8d587f8710bf3a`
- `join_entropy`: `0xb03780fd1e4c7e0fcfbb46fc95e6d33685954c4fe7f5c551e1b353c61f96a8c2`
- `reveal_entropy` with a wrong secret: `0x945c8352829f156390bf08e25172835dba1a5a2de02aefb8d7145b2a7a1e4471` → `EXPECTED: partner commitment mismatch`; batch stayed `MATCHED`
- `audit_sample(4,0)` while `MATCHED`: `0x79326fc4901f9e309ad9cb5c579ca15b9e371840c9aeb1a434a2b4d8b5ca1c7a` → `EXPECTED: batch sample is not ready`
- duplicate `join_entropy(4, ...)`: `0x5093cc3757be4fb75eba48b995e2379358bc2658438f78a583da9e811dacae5b` → `EXPECTED: batch is not open`

### F. Sampling uniqueness — batch 5

`item_count=10, sample_size=10`.

- `create_batch` (`batch_id = 5`): `0x286258394d22619a19b692ee7d952b25d9f88d89ef7f5f64ff7da337c3c90244`
- `join_entropy`: `0xb869efd0f93a314f09bfec0040b4c4dfd6a3ca5406c60a84c0988f81ad13e20b`
- partner `reveal_entropy`: `0xbd6372f96b1ca7b378d47672bc1570a9440ecc57f13fbe84c3457ee64fbc6f7d`
- producer `reveal_entropy`: `0xe4f518de7a906804c67ac067c39c6fc8f055550c04ea850c99e8a3e09e1f0f14`
- `sample_indices`: `[0, 1, 4, 2, 5, 6, 8, 3, 9, 7]` — full permutation of `0..9`

### H. Replay / state-machine rejection

| Scenario | Batch | Tx | Result |
|---|---|---|---|
| Audit a terminal (`CERTIFIED`) batch again | 1 | `0x711d36f11a79df354f5cf1a751424a5c9075589c9291bc911c835cce39d97c0f` | `EXPECTED: batch sample is not ready` |
| Settle an already-`CERTIFIED` batch again | 1 | `0xff8f10b17b8f7edd4fc60e4a89fe8001fb1ea5268821647c1fced558ab3ccab4` | `EXPECTED: batch is not settleable` |
| Settle before every sampled slot is audited | 5 | `0x73226741c277bc30de228195b3de0b93e295cfdd517fad56f5214680226e8f8d` | `EXPECTED: every sampled slot must be audited` |
| First audit of slot 0 (declared `item_count=10` vs. real 6-item manifest) | 5 | `0x8049710afc6dd099e49f185c7573470f73e459c8d60f4a4c1d3aa4a71a5dbf3b` | `INCONCLUSIVE`, `manifest item count mismatch` |
| Duplicate audit of the same slot | 5 | `0x099efc99b50bf75e51c1be5d09eebd95964332c8b08098ae0464f8f4d0948a01` | `EXPECTED: sample slot already audited` |
| Duplicate `join_entropy` on a `MATCHED` batch | 4 | `0x5093cc3757be4fb75eba48b995e2379358bc2658438f78a583da9e811dacae5b` | `EXPECTED: batch is not open` |
| Duplicate `reveal_entropy` (same entropy partner, twice) | 6 | `0xf7e681d656d2a4319e23288c9bb81f3fa31b6d7fed19cf7ee060567a733ae029` | `EXPECTED: entropy partner already revealed` |
| `cancel_unmatched` by a non-producer | 7 | `0xffdbff72611ddc2feb2072b0f9fdc1eaba526a9d0a2b05f981e081d367ead736` | `EXPECTED: only producer may cancel` |
| `cancel_unmatched` by the producer on `OPEN` | 7 | `0xacbfa91a2e1e31080cac6fe6fae79222b4aa67bb221bcdfc4f954fcf27699da2` | succeeds → `CANCELLED` |
| `cancel_unmatched` again on `CANCELLED` | 7 | `0x59fa7d59cd4a0762ec296f8c5514656ca2bb239770f2e541f0fbeff1ecbf7307` | `EXPECTED: only unmatched batches may be cancelled` |

### G. Non-reveal liveness — batch 6, ABORTED

- `create_batch` (`batch_id = 6`, `reveal_deadline = "2026-09-14T12:02:00Z"`): `0x32a27b0f59e28fac115458fbcdaef88a6734fce18768dbfa3dfd884176beeb7b`
- `join_entropy`: `0x29adb4432febff9c37b6bad744c75138bdf4b6eb47e16cc045dd55a0aeb38c33`
- partner `reveal_entropy` (producer deliberately never reveals): `0xf21dfa74b35eaa91e866a7b685702867f3880f206c08583f18ae1d254e18d580`
- `abort_non_reveal` before deadline: `0xe8fb1c167a81596e611de1d09596da6e43ccec57bbaf72fa4c2d70ede3a97fd2` → `EXPECTED: reveal deadline has not passed`
- `abort_non_reveal` after deadline: `0xbbe19d058da80b75b2467880553e305ac9f577a9235291e9d4e243b21589e917` — FINALIZED, succeeds → `ABORTED`. **v1 had no bond, so nothing was forfeited here** — this is exactly the free-retry gap v2 closes.
- `abort_non_reveal` again (already `ABORTED`): `0xbe69841e07a9111aaf78a7a30d6785078e5687ce41dde655430c15ace3e220f0` → `EXPECTED: batch cannot be aborted`
- `settle` on the `ABORTED` batch: `0x1b40fe2a81ac503ff4f51b13fa3388bf7f9cd75e7a929b392ef12da9f23fd499` → `EXPECTED: batch is not settleable`

### I. Validator independence — batch 2, slot 0

`genlayer receipt 0x97fdfca76ad5e7133dbac898ca667c396e239d7410ec4ab8a95ae08c3648d288` (5 round validators, `result_name: 'MAJORITY_AGREE'`):

- Leader independently fetched the pinned manifest and `item-1.txt`, verified both SHA-256 digests, and returned `{"item_id":"item-1","item_sha256":"d2e4635a...","outcome":2,"reason":"...lacks a version tag... mentions a competitor product by name ('RivalCorp Suite')... includes a command to share."}`.
- 3 of 4 non-leader validators actually re-executed (`vote: 'agree'`, `execution_result: 'SUCCESS'`) — each independently re-fetching the manifest/item and independently re-running the LLM judgement inside the contract's own `validator_fn`, agreeing only because their own outcome and identity fields matched the leader's.
- The remaining 2 validators show `vote: 'idle'`, `error_code: 'CONSENSUS_VALIDATOR_QUORUM_REACHED'` — Studio's standard optimistic-execution skip once quorum is reached, not a validator-logic weakness.

This was directly observed from a live `genlayer receipt` call, not merely asserted. `genlayer trace`'s `gen_dbg_traceTransaction` RPC returned "Method not found" on Studionet; `genlayer receipt`'s per-round-participant execution records were used instead, which carry equivalent information (per-validator execution result, vote, and the leader's return payload).
