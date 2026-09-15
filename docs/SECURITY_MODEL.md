# Security model (v2)

This revises the v1 security model after a strict review identified that the
blind-sample fairness claim was not defensible as originally written. See
"What changed in v2 and why" below for the specific findings. Read this
document, not the v1 phrasing still visible in old commit history, as the
current claim.

## Why commit/reveal, not a randomness beacon

GenLayer's own consensus layer uses an elliptic-curve verifiable random
function (ECVRF) to select transaction activators, leaders, and validator
committees, with a seed chain kept per recipient contract. That mechanism is
real, but it is internal to protocol consensus: no documented `gl.*` API
exposes it, or any other verifiable-random-function or randomness-beacon
primitive, to Intelligent Contract code. This was verified directly against
`docs.genlayer.com` (the "Protocol Randomness" page, the GenVM/non-determinism
pages, and the host-function references) while designing v2; none of them
describe a contract-callable randomness source. AuditLot's blind sample
therefore still depends on entropy contributed by two off-chain parties
through commit/reveal, not on a platform-provided beacon. A future GenLayer
release that exposes verifiable per-transaction randomness to contracts would
be a strictly better foundation than what follows, and AuditLot should adopt
it if and when it exists.

## Protected properties

1. **No post-sample batch substitution.** The manifest and sampled item
   bodies are SHA-256 pinned; a changed manifest or item degrades that
   sample slot to `INCONCLUSIVE`, never a silent substitution.
2. **No unilateral sample selection.** Deriving the sample requires both the
   producer's and the entropy partner's secrets; neither party's secret
   alone determines anything. This property held in v1 and is unchanged.
3. **No duplicate sample slots.** Deterministic selection with rejection
   sampling yields unique indexes; see `tests/test_protocol_model.py` and
   `tests/direct/test_auditlot_direct.py::test_full_sample_covers_every_index_exactly_once`.
4. **No leader-only semantic verdict.** Validators independently refetch the
   pinned evidence and independently reproduce the outcome; a leader cannot
   substitute evidence or force agreement by shape-checking alone (see
   `tests/direct/test_auditlot_direct.py`'s `test_validator_independently_*`
   tests and the live validator-trace evidence in
   `docs/DEPLOYMENT_EVIDENCE.md`).
5. **No silent uncertainty.** Evidence failure, hash mismatch, malformed
   manifest, non-UTF-8 content, unparsable semantic judgement, or a missing
   required transaction timestamp all become `INCONCLUSIVE` or a hard
   revert -- never a laundered PASS or FAIL.
6. **No LLM-controlled final batch status.** Threshold arithmetic and
   terminal transitions are deterministic; the LLM only ever contributes a
   PASS/FAIL/INCONCLUSIVE label for one already-selected item.
7. **No free cherry-picking of a real result.** Once an assessment (the
   canonical `(chain, contract, manifest_sha256, rubric_sha256)` identity;
   see `assessment_id_for`) has produced one fully-sampled, fully-audited
   terminal result (`CERTIFIED`, `REJECTED`, or `INCONCLUSIVE`), no further
   batch may ever be created for that assessment, at any sample size or
   threshold. This is enforced in contract state
   (`Assessment.resolved`), not merely documented convention -- see
   `test_resolved_assessment_cannot_be_retried` and
   `test_retry_after_real_result_is_blocked_even_with_different_sampling_parameters`.

## What v1 got wrong, and what v2 actually guarantees about the reveal

v1's phrasing said the sample was unpredictable "as long as at least one
party selects a fresh unpredictable secret and withholds it until reveal."
That phrasing described the commitment step correctly but glossed over the
**reveal** step, where the real vulnerability lives:

> **The last-revealer preview.** Once the first party's secret is revealed
> (public, on-chain, from that point on), the *second* party to reveal can
> compute -- entirely off-chain, without submitting any transaction -- what
> the resulting sample would be for each candidate secret it is considering.
> If it dislikes the result, it simply never submits its own
> `reveal_entropy` call. The batch then sits in `MATCHED` until the reveal
> deadline passes, at which point anyone can call `abort_non_reveal`. In v1
> this cost the withholding party nothing beyond the wait and a fresh set of
> transactions to try again with a new batch (and, since v1 had no
> assessment-identity concept, an unbounded number of times).
>
> `tests/test_protocol_model.py::test_last_revealer_can_precompute_outcome_before_choosing_to_reveal`
> and `tests/direct/test_auditlot_direct.py::test_last_revealer_preview_is_real_and_is_what_bonding_prices`
> both demonstrate this preview mechanically: they compute the sample from
> the public first reveal plus a candidate second secret using the exact
> production seed formula, before that secret is ever revealed on-chain, and
> confirm it matches what the contract later derives.

**This is not fixable by reordering who reveals first**, and it is not
fixable by adding more commitment rounds: on a sequential blockchain without
a trusted third party, a verifiable delay function, or a randomness beacon,
whichever party acts *last* in any finite protocol always has the option to
inspect the would-be outcome before deciding whether to act at all. GenLayer
exposes none of those stronger primitives to contract code today (see
above), so AuditLot v2 does not claim to eliminate the preview. It prices and
bounds it instead:

- **Bonding.** `create_batch` is payable; the value attached becomes the
  batch's `bond_atoms` (minimum `MIN_BOND_ATOMS`). `join_entropy` must
  attach exactly the same amount. Both bonds sit in the contract until the
  batch resolves.
- **Forfeiture on one-sided non-reveal.** If the deadline passes with
  exactly one party having revealed, the non-revealing party's bond is paid
  in full to the party who did reveal (who also gets its own bond back --
  net `2x bond_atoms`). Withholding after seeing an unfavorable preview now
  has a real, priced cost, not merely a wasted wait.
- **No penalty when neither party ever reveals.** If neither party reveals,
  neither ever gained the informational advantage the preview provides,
  so both bonds are simply returned; there is nothing to punish.
- **Retry cap, not a fresh unlimited assessment.** A non-reveal abort does
  not resolve the assessment (no real sample was ever drawn), so a retry is
  allowed -- but only up to `MAX_ABORTS_PER_ASSESSMENT` (3) times, and only
  reusing the exact `item_count`/`sample_size`/`min_pass_bps`/`bond_atoms`
  locked by the assessment's first attempt. After the cap, the assessment
  is permanently retired unresolved. This bounds how many free "looks" a
  withholding party can ever take for the same manifest and rubric, while
  still tolerating a small number of legitimate failures (an offline or
  briefly unresponsive partner, not necessarily malicious) without
  permanently denying the producer service after a single non-reveal --
  see `test_abort_non_reveal_rejected_while_deadline_still_open` and the
  live evidence in `docs/DEPLOYMENT_EVIDENCE.md` for the cap actually
  triggering after repeated real aborts.

### The precise, narrowly-qualified claim

AuditLot v2's sample is unpredictable to **both** parties at the moment they
submit their commitments. After both commitments are fixed, whichever party
ends up revealing second gains a one-sided ability to preview the resulting
sample before deciding whether to reveal at all. AuditLot v2 does **not**
claim this sample is cryptographically unbiased against a rational adversary
who is willing to forfeit its bond up to `MAX_ABORTS_PER_ASSESSMENT` times.
It claims the sample is unbiased against any adversary for whom the posted
bond exceeds the value it expects to gain by resampling, and it structurally
caps the number of real "free look, then abort" attempts at
`MAX_ABORTS_PER_ASSESSMENT`, after which the assessment is permanently
retired without ever producing a certified, rejected, or inconclusive
result the producer could publish. **Do not read any statement in this
repository as claiming unconditional unbiasedness; none is made.**

A cryptographically stronger fix (e.g. timelock/VDF-encrypted reveals that
unlock automatically after a fixed, permissionless amount of computation
regardless of either party's cooperation, removing the discretionary "do I
submit this transaction" decision entirely) is a known, more robust approach
to this class of problem. It is out of scope for v2: no VDF/timelock library
is available inside GenVM's Python/WASM sandbox as of this writing, and
implementing one from scratch inside a deterministic contract is a
substantial, high-risk undertaking well beyond fixing the fairness gap this
revision targets. If GenVM ever exposes such a primitive, or the protocol
randomness seed chain described above, either would be a better foundation
than bonding and should replace it.

## Trust assumptions

### Value is credited before the method body runs, not atomically with success

Confirmed live on Studionet while testing v2: GenVM credits a payable call's
`gl.message.value` to the receiving contract's balance as part of message
delivery, **before** the target method's code runs, and that credit is
**not** rolled back if the method subsequently reverts (whether via a clean
`gl.vm.UserError` or an uncaught exception). This is unlike typical EVM
atomic-revert semantics, where a reverted call undoes the value transfer
along with everything else.

A first version of `create_batch`/`join_entropy` in v2 did not account for
this: a rejected call (wrong bond amount, invalid argument, anything)
permanently stranded the caller's attached GEN in the contract, since a
failed `create_batch` never produces a batch record to attach a refund to.
This was found by reproducing it live, not by any test suite -- the
direct-mode harness does not model native value movement at all (see
`tests/direct/test_auditlot_direct.py`'s `install_transfer_recorder` helper
and its docstring), so this class of bug is invisible to it.

**First attempted fix (also wrong, also disproven live):** wrapping the
body in a try/except that calls `_refund_value()` and then re-raises the
original exception. This looked correct in the direct-mode test suite,
which does not model value at all, but failed live: GenVM does not give a
reverting call atomic-except-for-the-initial-credit semantics the way the
credit itself is exempt from rollback. Every *other* side effect scheduled
during a call that ultimately reverts is rolled back along with it --
including a refund transfer scheduled by the failure handler itself. Live
`eth_getBalance` polling after a deliberately-rejected small-value call
showed the contract's balance never dropped and the sender was never
refunded, confirming the scheduled refund was itself undone by the revert.

**Actual fix:** `create_batch` and `join_entropy` must never let an
exception escape once they are payable. Both methods now catch every
failure internally, refund `gl.message.value` to `gl.message.sender_address`
via `_refund_value()`, emit a `CreateBatchRejected` / `JoinEntropyRejected`
event describing the reason, and **return a sentinel value normally**
(`u256(0)` for `create_batch`, `False` for `join_entropy`) instead of
raising. Because the call then completes successfully from GenVM's
perspective, the refund is a normal side effect of a *successful* call and
is not rolled back.

This is a real, integrator-facing behavior change: callers of these two
methods must check the return value (or listen for the `*Rejected` event),
not rely on the call reverting, to detect rejection. Every other write
method (`reveal_entropy`, `abort_non_reveal`, `cancel_unmatched`,
`audit_sample`, `settle`) is unaffected and still raises normally on
failure, since none of them are payable. Any integrator building their own
payable GenLayer contract should assume the same platform behavior applies
to them: never assume a reverted payable call is a no-op with respect to
value, and never assume a refund scheduled inside a failure path that ends
in `raise` will actually be delivered -- only a normally-returning call
commits its side effects.

### Bond value is meaningful

The forfeiture deterrent is only as strong as the bond itself. AuditLot does
not fix a bond amount; the producer chooses it (subject to `MIN_BOND_ATOMS`)
and the entropy partner must match it exactly to participate. A producer who
posts a token minimum bond on a batch whose certified outcome is worth far
more to it than that bond gets a correspondingly weak fairness guarantee.
Downstream consumers who care about this should check `bond_atoms` on
`get_batch`/`get_assessment`, not just the terminal status.

### At least one honest, resource-constrained entropy contributor

If producer and entropy partner collude before committing, they can search
over secret pairs to target a favorable sample even at commitment time --
this was true in v1 and remains true in v2; no on-chain mechanism can detect
collusion between two consenting parties. v2's guarantee is conditional on
the two parties not colluding, exactly as v1's was, but is now additionally
conditional on the bond exceeding the withholding party's incentive to
re-roll, as described above.

### Public immutable hosting

The contract expects the manifest and item URLs to remain retrievable with
exactly the pinned bytes during the audit. Content-addressed or immutable
hosting is strongly preferred; AuditLot's own live-demo fixtures use
commit-SHA-pinned `raw.githubusercontent.com` URLs for exactly this reason.

### Rubric quality

AuditLot proves performance against the rubric the producer froze. A weak or
self-serving rubric yields a weak certificate. Consumers must inspect or pin
an acceptable rubric hash.

### URL validation is defense-in-depth, not a verified runtime guarantee

`validate_url` (in `contracts/auditlot.py`) rejects, deterministically and in
contract code: non-https URLs, embedded userinfo/credentials, bare IPv4/IPv6
literal hosts, a small curated set of well-known internal/metadata
hostnames (`localhost`, `metadata.google.internal`, and any `.local`/
`.internal` suffix), and any non-default port. It cannot perform real DNS
resolution -- that would be non-deterministic and could disagree between
validators -- so it cannot detect a DNS name that resolves to a private or
loopback address, nor can it evaluate an HTTP redirect chain a fetch might
follow.

Whether GenVM's own `gl.nondet.web.get` runtime additionally enforces
server-side-request-forgery protections (private-IP blocking after DNS
resolution, redirect-chain limits, DNS-rebinding protection) is **not
documented** in GenLayer's own developer documentation as of this writing
(`docs.genlayer.com`'s Web Access and non-determinism pages describe how to
call the web-fetch functions, not what network-level restrictions the
runtime enforces). This document does **not** claim any such runtime
protection exists; it was not possible to verify one way or the other from
official documentation, and no such claim should be inferred from the
presence of contract-level validation. Operators and integrators who need
that guarantee should verify their specific GenVM node's runtime behavior
directly rather than relying on this contract's validation as a complete
mitigation.

### Statistical scope

Sampling reduces cost; it does not inspect unsampled items. AuditLot
deliberately does not claim a statistical confidence interval because that
depends on the user's sampling assumptions, batch construction, and
acceptable defect model.

## Prompt injection

Sampled item text is explicitly labelled hostile data in the validator
prompt. The prompt instructs the model not to follow commands contained in
the item. More importantly, a single leader cannot release an outcome alone:
validators independently fetch and judge the same pinned item.

This reduces but does not mathematically eliminate model-level
prompt-injection risk. High-stakes consumers should use clear, bounded
rubrics and conservative thresholds.

## Failure modes

| Failure | Result |
|---|---|
| manifest URL unavailable | sampled audit becomes `INCONCLUSIVE` |
| manifest body changed | `INCONCLUSIVE` |
| sampled item unavailable | `INCONCLUSIVE` |
| sampled item body changed | `INCONCLUSIVE` |
| malformed manifest, or declared `item_count` does not match the real manifest | `INCONCLUSIVE` |
| validator semantic disagreement | consensus does not finalize that audit call |
| one entropy participant reveals, the other never does | batch `ABORTED`; non-revealer's bond forfeited to the revealer |
| neither entropy participant reveals | batch `ABORTED`; both bonds refunded, no forfeiture |
| sampled defect rate exceeds threshold | `REJECTED` |
| any sample is unresolved/inconclusive | batch `INCONCLUSIVE` |
| the assessment already has a resolved (real, audited) result | `create_batch` reverts; no retry possible, ever |
| the assessment has hit `MAX_ABORTS_PER_ASSESSMENT` non-reveal aborts | `create_batch` reverts; assessment permanently retired, unresolved |
| required transaction timestamp is unavailable or malformed at a deadline check | the call reverts (`EXTERNAL: transaction timestamp unavailable`), never silently treated as "deadline passed" or "still open" |

## What this certificate does and does not mean

A `CERTIFIED`/`REJECTED`/`INCONCLUSIVE` result from `get_certificate` is a
statement about exactly one thing: *a deterministic, blind sample of size
`sample_size` drawn from this exact `manifest_sha256` under this exact
`rubric_sha256`, using this exact random seed, achieved this terminal result
under GenLayer consensus, for this specific assessment and batch.* It does
**not** mean:

- every unsampled item in the manifest is good, or bad;
- the manifest exhaustively represents every real-world deliverable the
  producer holds;
- the same manifest would certify under a different rubric, sample size, or
  threshold (those changes create a *different* assessment, which -- per the
  resolved-lock above -- can coexist with this one but is a distinct,
  separately-verifiable claim, not a re-roll of this one);
- any statistical confidence beyond the sample policy the caller chose.

Consumers who need to distinguish "the manifest that was audited" from "the
producer's full real-world dataset" must independently verify the manifest's
completeness; AuditLot has no visibility into anything outside the pinned
manifest.

## Non-goals

AuditLot does not verify legal ownership, exhaustive completeness of a
real-world batch, authorship, licence rights, or hidden off-chain facts. It
is a blind sampling and semantic certification primitive, not a universal
truth oracle.
