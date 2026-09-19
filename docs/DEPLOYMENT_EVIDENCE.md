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
- **Deployment finalized:** yes (`FINALIZED`, `MAJORITY_AGREE`; created 2026-09-19 11:40 UTC)
- **Source commit deployed:** `117da9d`
- **Deployer:** `0x3A3168d67A110dE79461939047a8f7334ff1423d`
- **Producer:** `bradbury-e2e` `0x3A3168d67A110dE79461939047a8f7334ff1423d`. **Entropy partner:** account `continuum` `0x13AE0C28D06716D2908B5d84c3c0c3d815378f3B`.

Live matrix executed on 2026-09-19 against this contract, using the official `genlayer-js` SDK for payable calls (the `genlayer` CLI cannot attach value to a write) and the official `genlayer deploy` for deployment. Transaction hashes below come from the recorded run log, not from memory. The contract was deployed with the source at commit `117da9d`; later commits change documentation only.

### A. Deployment
- Verified: `genlayer schema` returns the contract's methods. (Two earlier attempts today only looked successful: a bad `--args '[]'` made the constructor crash, so no contract existed.)
- Refund check, verified live: a deliberately invalid `create_batch` with 1000 atoms attached (tx `0xb6ade7490060de40d61a5c02f8eb8798ee1a3346f9711b06f3793b73525538d6`) returned the sentinel, and after finalization the caller's balance was back to exactly its starting value and the contract balance was 0. The previous contract (`0x7Da416E0...D70f`, v0.2.2) lost such refunds because it used a contract-only transfer; that deployment is superseded.
- The live scenarios B-I below were all executed on this contract.

### B. Happy-path certification (CERTIFIED) - batch 1
  - create_batch: `0x02046fcbc2b72ffc657e217dff47f81250545a12c2f7c201e8dbee88ee90905c` -> returned 1
  - join_entropy: `0x281e453483ef4c9da88f0c616021d3ea4190d97d78432d4f871169abdd3e59e9` -> returned true
  - reveal partner: `0x8584e613728381e6507b28c2eabd0c10d6f19574476d9ba2a65cef330bc999f3` -> returned null
  - reveal producer: `0xe60bca781f9d9058fe58928f6fc14ea1e9f337b768a05416f31c6921db5b15fc` -> returned null
  - audit_sample slot 0: `0x7bb49610b50264a122d0faf62ca102724bb875455385196cd556b941da247d72` -> returned null
  - audit_sample slot 1: `0xe310b56c6b2c9acabc0e15e818d34714a8a1c87029026f67764f30df45ab32f6` -> returned null
  - audit_sample slot 2: `0x6738f8ea535a9a0ef75c36ac64ad1a14a371d7d2ea3f54ee25f311aeae0e7126` -> returned null
  - settle: `0x43af3977ebd47db1a27d9b2227adc08a87fb82bc90a53a45f329f587d6d86355` -> returned null
- Sample indices `[2,4,0]`; all three audited items PASS (item-2, item-4, item-0).
- `get_certificate(1)`: CERTIFIED, pass_count 3, pass_bps 10000, certificate_sha256 `0f7c2e4f6f38228e0a016fabc15f2dcc3decc4572e3b628837f62131841c661b`.
- `get_assessment`: resolved = true, resolved_batch_id = 1.
- Both bonds refunded in full: after the settle transaction finalized, producer and partner balances were exactly equal to their pre-batch balances and the contract balance was 0.
### C. Rejected batch (REJECTED) - batch 2
  - create_batch: `0x8d1e6cefb91f2875571472fd044594f1010d7a322647acafc71e97f7924d3e23` -> returned 2
  - join_entropy: `0x1f7cede41282e6a3a20eee1f7a83930c80a4e964a2c6b8a39c7f90278fdce13b` -> returned true
  - reveal partner: `0x52bc13f476d30b59cb33b2f3cae66d9687f195eda9d9ff807ce7af31d5c71fbf` -> returned null
  - reveal producer: `0x32e502373315cca0cb07aa0e67e15f5693acd73b818fff8d4334440cc6652d60` -> returned null
  - audit_sample slot 0: `0xc600324302a6d62bf69ca153494a9026e77751f2b8885aa168b5af646aab79a8` -> returned null
  - audit_sample slot 1: `0x4420e69553983e06b4aaaefb7b312a059d187eb60a6405c8537127c085853061` -> returned null
  - audit_sample slot 2: `0xcc11761c5a93a17ae1064bdd1bc2da45768d2feb3255e47dd6257d492fa76e42` -> returned null
  - settle: `0xfe7e99bef58d373189f47abf74bf7c7d2f8f98f661f594656dd6255b5768ae72` -> returned null
- Sample indices `[4,1,2]`; audit outcomes: FAIL, FAIL, FAIL.
- Terminal status REJECTED; fail_count 3, inconclusive_count 0; certificate_sha256 `88a5e4ad176771353a7e7b31d4c1323b691792bb01a0ff225a78c89cdd54dd95`.
- Both bonds refunded in full (balances back to the pre-batch values, contract balance 0).
### D. Inconclusive fail-closed path (INCONCLUSIVE) - batch 3
  - create_batch: `0x2d4f75dc4ae75b7b4910012dd640d0d3a76da7ce5225be4b9150bd739e21d382` -> returned 3
  - join_entropy: `0x951730041205685532d6365182dce01643b4b0fb1550656ec470e5947479420d` -> returned true
  - reveal partner: `0x6bf9ba4f78277835aa64694a4327fc02c0ceeb460a8ef51250321e61d8cf3108` -> returned null
  - reveal producer: `0xae0d0655753ffcff075b5936e55259461e81d6e47d6e81dfcf57cae81abf4ff1` -> returned null
  - audit_sample slot 0: `0xbc074db3e8b7ea14c814c226ebeec7e9e0bf90a22d859956a6264a6bfc9fb471` -> returned null
  - audit_sample slot 1: `0xdc8d2444b99fa4010086365d58fd56bec3abd317e97cb68809f02fc277d247e7` -> returned null
  - audit_sample slot 2: `0x6bc268d1fc947f6f0a032530c35c5f0f7a4769dd2a5cdabf2e3d60b13e98b116` -> returned null
  - settle: `0xde3543108f616bab684ebc61814c2b47b2ae72926f4aa632fed8e036dda93cdb` -> returned null
- Sample indices `[3,4,1]`; audit outcomes: INCONCLUSIVE (item hash mismatch), INCONCLUSIVE (item hash mismatch), INCONCLUSIVE (item hash mismatch).
- Terminal status INCONCLUSIVE; fail_count 0, inconclusive_count 3; certificate_sha256 `4d8c9270a8ace72658541b840522d791f0569a8ccfe3946ca3fc6d251a89aaa5`.
- Both bonds refunded in full (balances back to the pre-batch values, contract balance 0).
- Malformed/mismatching evidence never produced PASS or FAIL.
### E. Commitment mismatch and state-machine checks - batch 4
  - create_batch: `0x7cdd4f8d0828a5a2a056c537822b0d301d11589198b0ed4207295ee57aac2f23` -> returned 4
  - join_entropy: `0x21fd22455d09d379397e97736bba7eeee549534e994b13c0238cd80ffd0d6908` -> returned true
  - duplicate join_entropy (expect false + refund): `0x187063ce83b52bba4b3eb260cedb0ca083036667a843db5ffd2be18b6b53e5f2` -> returned false
  - reveal with WRONG secret (expect revert): `0x3a5ce0579e7260615b1c83618dc9a60472de81daadbe55984f1abc9dcb536d0c` -> reverted: EXPECTED: partner commitment mismatch
  - audit_sample while MATCHED (expect revert): `0x3449b821c1d02d58fb98b2f2275ca82086d88d1778b0feb7e1c3babf4ff8e598` -> reverted: EXPECTED: batch sample is not ready
  - abort_non_reveal after deadline (neither revealed -> both refunded): `0x3c7f4767537bb32016705b617f1fc308d7dda8af7b3200ebdc551dbf20127ab7` -> returned null
- A wrong reveal secret reverted with `partner commitment mismatch` and the batch stayed MATCHED; `audit_sample` while MATCHED reverted; a duplicate `join_entropy` returned false and its attached bond was refunded.
- Batch 4 was then left un-revealed past its deadline and `abort_non_reveal` (neither side revealed) returned both bonds; status ABORTED, assessment abort_count 1.
### F. Sampling uniqueness - batch 5 (item_count 10, sample_size 10)
  - create_batch item_count=10 sample_size=10: `0xce687ee9363f6cd49c6beaf06184b3038806970f411390b4585c617c1f39521f` -> returned 5
  - join_entropy: `0x177a0242274626862202c169a272b10ff4cd3fa40a5a0bcf1ba84557dadb07cb` -> returned true
  - reveal partner: `0x21f2fc6be9f0399335fd276d915b5b6804660353a120dbe714fd3422f7a3ae64` -> returned null
  - reveal producer: `0x531164270c154fce6cb2068fd1d8f859ef2e9749b3adefa0e7f0b07b39d28dbe` -> returned null
- `sample_indices` = `[9,7,2,1,0,3,5,4,6,8]`: 10 unique values, all within 0..9.
- Batch 5 was deliberately not audited/settled, so its two 0.001 GEN bonds remain locked in the contract (visible as the only residual contract balance).
### G. Non-reveal liveness, bond forfeiture, and the retry cap (bond 0.005 GEN each)
  - create_batch (bond 5000000000000000): `0x23678aad0e3f2729340eab59e5dc537d361bab2a8f5ca27a50b143b26adcfdcc` -> returned 6
  - join_entropy: `0xebb680ac459d3eee8fbd536930c65c1a5b920349e0e3ef7bbe04cee571a9f4f7` -> returned true
  - ONLY producer reveals: `0x05d5c46082c0888aa0b9366f0fbc5c1c42bb536513e047e1a971607e90b71bb6` -> returned null
  - abort_non_reveal BEFORE the deadline (expect revert): `0x38243b52c9372f7d6c42aa53039f74064bc0a0bd5cd771bd372a4edf75f66846` -> reverted: EXPECTED: reveal deadline has not passed
  - abort_non_reveal after deadline: `0x46f24cd610a7de39c0ccb30a603c651ab8492f6a9c0b7c218138e4e9330fa69e` -> returned null
  - retry with DIFFERENT sample_size (expect 0 + refund; locked params): `0x6ed695812d2786ab9b258790f1d5dd88573a4839381fd46ef8b388c8f19e16a5` -> returned 0
  - retry with DIFFERENT bond (expect 0 + refund; locked bond): `0x45a6ee6390cdff623bd6aaa942b2196b821ee2398acfcc76d51885f0fae5ce02` -> returned 0
  - create_batch (bond 5000000000000000): `0x8878e7d586ef7ac8361dbfb2abdde80cb8a2d94bcec689e79499764f0b8dcdab` -> returned 7
  - join_entropy: `0x9f9890b0214e72fe50725218727da7140ba0f8f851a3786b6f5f279cb75fc1ee` -> returned true
  - ONLY partner reveals: `0xca55e9b5603666f3496cff12b4e74ae749cbbd2c31b32ef922dc76f1341ff09b` -> returned null
  - abort_non_reveal after deadline: `0xba7f35a45c4e86c5fecfcdcead2873a5c3ec25d39a853f5c2b3121a6f7b1abb8` -> returned null
  - create_batch (bond 5000000000000000): `0x182e5d842b504bc3f09e78139a48dcc0c01560a28ee55d36de4afd65493addd9` -> returned 8
  - join_entropy: `0xa8c89f51636b72b6c8ad71ae1c76b6ea08fa508245711db050715098e8ba045d` -> returned true
  - abort_non_reveal after deadline: `0xc9c5caa6ecfaf39d88341556dd32bda4f8a9f9d1101098ebd541e23d41177f4d` -> returned null
  - create_batch after 3 aborts (expect 0 + refund: permanently retired): `0x52db2f47d665c1ca4448b6454662afe8743ec50eb6f7f16109512657b7c8670d` -> returned 0

- Cycle 1 (revealed: producer): batch 6 ABORTED; measured balance change over the cycle: producer 5000000000000000, partner -5000000000000000, contract 0 atoms; assessment abort_count 1, resolved false.
- Cycle 2 (revealed: partner): batch 7 ABORTED; measured balance change over the cycle: producer 10000000000000000, partner 5000000000000000, contract -15000000000000000 atoms; assessment abort_count 2, resolved false.
- Cycle 3 (revealed: none): batch 8 ABORTED; measured balance change over the cycle: producer 0, partner 0, contract 0 atoms; assessment abort_count 3, resolved false.
- Reading the deltas: cycle 1 (only producer revealed) - producer +0.005 GEN (its own bond back plus the partner's forfeited bond, minus its own bond posted), partner -0.005 GEN. The cycle-2 producer/contract figures also include the two rejected retry refunds (0.005 + 0.010 GEN) that finalized during that window; net of those, cycle 2 (only partner revealed) mirrors cycle 1 with the roles swapped. Cycle 3 (nobody revealed): all zero, both bonds refunded.
- Over the whole scenario the producer and partner ended exactly even (each side was forfeited once and collected once).
- Not a trivial permanent denial of service: after the first abort the same assessment accepted a new batch (cycle 2) and a third (cycle 3). Retries with a different sample_size or bond were rejected with the attached value refunded (locked parameters). After the third abort, a fourth `create_batch` returned 0 with the value refunded: the assessment is permanently retired (final `get_assessment`: abort_count 3, resolved false).

### H. Replay, state-machine, and assessment-identity rejection
  - create_batch for assessment that already has an ACTIVE batch (expect 0 + refund): `0x5de414912df1b4e2341275910026eecef7bf58a8965df742b65bec84a348884c` -> returned 0
  - settle before all samples audited (expect revert): `0x79e4c8a366c4a78d1aa638620eca5d40cee7584e84741c02947fd93786e87c52` -> reverted: EXPECTED: every sampled slot must be audited
  - create_batch REUSING an already-used commitment on a new assessment (expect 0 + refund): `0x1ecd079f0580fd8de3d5feed4402494c1526d1c66c0a60a5a1478b11a44d3153` -> returned 0
  - reveal_entropy on settled batch 1 (expect revert): `0x013b968472c2d5aff314b1784a9fc5ff272a882c96d85a9923fd37f96c76d34d` -> reverted: EXPECTED: batch is not awaiting entropy
  - audit_sample slot 0 on settled batch 1 again (expect revert): `0x8a1f34d8dab4783c722b538a5be0650bcd7d182296e528dd21310ad7c62e4585` -> reverted: EXPECTED: batch sample is not ready
  - settle settled batch 1 again (expect revert): `0x7386150b7a99dfb29d8b832c08566fb42d77fcec28cecae40ddca8f94cd68fca` -> reverted: EXPECTED: batch is not settleable
  - create_batch for RESOLVED assessment, same params (expect 0 + refund): `0x6049b9f6d247a08ae67eb2018f537e95561f0ec5036d345dc87a0cc18030b024` -> returned 0
  - create_batch for RESOLVED assessment, DIFFERENT sample_size/threshold (expect 0 + refund): `0x350b914b9a6dd1a002923b10444c3d423ecb33dac25a3aac462a6761e7a0467c` -> returned 0
- Also covered above: duplicate `join_entropy` (E), reveal with wrong secret (E), retry with mismatched sampling parameters or bond (G).
- Every `create_batch`/`join_entropy` rejection listed returned the sentinel (0 / false) and its attached bond was refunded (checked by balance readback: no residual contract balance beyond batch 5's bonds).
- Not exercised live: `cancel_unmatched` (covered by Direct Mode tests only).

### I. Validator independence
- Observed, not just asserted, for what a receipt can show: the finalized `audit_sample` transaction `0x7bb49610b50264a122d0faf62ca102724bb875455385196cd556b941da247d72` (batch 1, slot 0) records one leader execution plus five separate validator records, each with its own node address, its own execution result and its own vote. Result `MAJORITY_AGREE`, status FINALIZED; three validators voted `agree`, two were recorded `idle` after quorum was reached. The leader record carries its own fetched item id/hash and verdict.
- Not observed: the per-validator web fetch itself. Studionet does not expose the debug trace method (`gen_dbg_traceTransaction` returns "Method not found"), so a live trace of each validator's HTTP request is not available. That each validator re-fetches and re-judges on its own is established by the contract code (the validator closure calls the web fetch and the LLM itself) and by Direct Mode tests where a validator disagrees when its own fetch sees different evidence or reaches a different semantic outcome. It is not separately proven by live logs.

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
