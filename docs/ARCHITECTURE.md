# Architecture (v2)

## Primitive boundary

AuditLot is deliberately one contract. It does not own a UI, catalogue,
marketplace, file host, or off-chain worker. Producers host immutable text
artefacts and a manifest; AuditLot binds those artefacts to a fair sample and
consensus-backed semantic outcomes.

## Assessment vs. batch

v2 introduces a second identity layer above the batch:

- A **batch** (`batch_id`, unchanged from v1) is one concrete attempt: one
  producer, one entropy partner, one pair of commitments, one bond, one
  sample, up to one terminal result.
- An **assessment** (`assessment_id`) is the canonical identity of *what is
  being tested*: `sha256("AUDITLOT_ASSESSMENT_V2|" + chain_id + "|" +
  contract_address + "|" + manifest_sha256 + "|" + rubric_sha256)`, available
  via the `assessment_id_for` view method so integrators never have to
  reimplement the hash themselves. Every batch belongs to exactly one
  assessment. An assessment can have many batch attempts over time (retries
  after a non-reveal abort), but can be *resolved* -- produce one real,
  fully-sampled, fully-audited terminal result -- at most once, ever. See
  `docs/SECURITY_MODEL.md` for why this exists (it closes the "create a new
  batch for the same manifest+rubric until a favorable sample appears"
  cherry-picking path) and its precise boundary (`item_count`/`sample_size`/
  `min_pass_bps`/`bond_atoms` are locked to the assessment's first attempt,
  so lowering the threshold on a retry is not a backdoor around the lock).

## State machine

```text
OPEN
  ├─ producer cancel (bond refunded) → CANCELLED
  └─ entropy partner joins (matches producer's bond) → MATCHED
                              ├─ deadline expires, ≤1 side revealed
                              │  (non-revealer's bond forfeited to the
                              │  revealer if exactly one revealed; both
                              │  refunded if neither did) → ABORTED
                              └─ both valid reveals → SAMPLE_READY
                                                    ├─ audits pending
                                                    └─ all audits complete → settle
                                                                          (both bonds refunded in full,
                                                                           regardless of terminal status;
                                                                           assessment marked resolved)
                                                                          ├─ CERTIFIED
                                                                          ├─ REJECTED
                                                                          └─ INCONCLUSIVE
```

Terminal states never reopen. `ABORTED` and `CANCELLED` do **not** mark the
assessment resolved (no real sample was ever drawn), so -- subject to the
`MAX_ABORTS_PER_ASSESSMENT` cap on non-reveal aborts specifically -- a new
batch may be created for the same assessment. `CERTIFIED`, `REJECTED`, and
`INCONCLUSIVE` do mark it resolved, permanently.

## Bonding

`create_batch` and `join_entropy` are both `@gl.public.write.payable`. The
GEN value attached to `create_batch` becomes the batch's (and, on first
attempt, the assessment's locked) `bond_atoms`, subject to a floor of
`MIN_BOND_ATOMS`. `join_entropy` must attach exactly that amount. Bonds are
held by the contract until the batch reaches a terminal state:

- `settle()` (CERTIFIED/REJECTED/INCONCLUSIVE): both bonds refunded in full,
  unconditionally on the semantic outcome -- a fairly-drawn REJECTED or
  INCONCLUSIVE result is never itself penalized, only a failure to reveal
  is.
- `abort_non_reveal()` with exactly one side revealed: that side's bond is
  paid to the side that revealed, in addition to its own bond back.
- `abort_non_reveal()` with neither side revealed, or `cancel_unmatched()`
  on a never-joined `OPEN` batch: full refund, no forfeiture.

Payouts use an EVM-style transfer (`gl.evm.contract_interface`, the `_Wallet`
helper, then `.emit_transfer(value=...)`), an asynchronous scheduled message,
not a synchronous balance mutation within the same call -- callers should not
assume the recipient's balance has already moved by the time the settling
transaction returns. The earlier `gl.get_contract_at(recipient).emit_transfer`
form only delivers to GenVM contracts; live testing on Studionet showed it
silently loses value sent to a plain wallet address, so it must not be used
for bond payouts.

## Blind sampling

The producer commits a secret before the entropy partner commits; the
partner only ever sees a one-way digest at that point. Commitments are
domain-separated:

```text
assessment_id = sha256("AUDITLOT_ASSESSMENT_V2|" + chain_id + "|" + contract_address + "|" + manifest_sha256 + "|" + rubric_sha256)
commitment    = sha256("AUDITLOT_COMMIT_V2|" + assessment_id + "|" + role + "|" + secret)   # role: "producer" | "partner"
```

`assessment_id` already transitively binds chain, contract, manifest, and
rubric, so the commitment formula only needs to add role and an explicit
protocol-version tag; there is no separate chain/contract term to keep in
sync by hand. Every commitment the contract accepts is also recorded in a
global used-commitment set and rejected if seen again, on *any* assessment,
by *either* role -- not just documented as an off-chain "always use a fresh
secret" convention. This matters beyond hygiene: once a secret is revealed
it is permanently public in transaction history, so reusing it on a retry
would hand a later counterparty (or the reuser's own earlier counterparty)
a known constant instead of real entropy.

Once both reveals are validated:

```text
seed = sha256(
  "AUDITLOT_SEED_V2" |
  assessment_id |
  batch_id |
  producer_secret |
  partner_secret
)
```

Unique indexes are generated by domain-separated repeated SHA-256 with
rejection sampling to avoid modulo bias (unchanged from v1; this part was
never the problem -- see `docs/SECURITY_MODEL.md` for the reveal-order issue
that was).

**Security property, precisely stated:** if both parties choose fresh,
independent, unpredictable secrets, neither can determine the sample before
both commitments are fixed. **This does not, by itself, mean the process is
fair against a party that waits to reveal until it has computed the result**
-- see `docs/SECURITY_MODEL.md`'s "last-revealer preview" section for what
v2 actually does about that (bonding + a capped retry count), and for the
exact, narrowly-qualified claim AuditLot makes about it. Do not read this
paragraph in isolation as a claim of unconditional unbiasedness.

**Liveness property:** a participant can still refuse to reveal. The batch
then ends `ABORTED` after the frozen reveal deadline, with the bond
consequences above. `MAX_ABORTS_PER_ASSESSMENT` bounds how many times this
can happen for the same assessment before it is permanently retired
unresolved -- see `docs/SECURITY_MODEL.md` for why that number is small but
non-zero (large enough to tolerate one honestly-unavailable partner without
permanent denial of service, small enough to bound deliberate re-rolling).

## Immutable evidence

A batch pins the exact SHA-256 response body of its JSON manifest. Each
manifest item pins the exact SHA-256 response body of its UTF-8 text
artefact. Every validator independently fetches both and checks those
digests before semantic evaluation.

A changed manifest or changed item therefore produces `INCONCLUSIVE`, never
a silently substituted audit. So does a declared `item_count` that does not
match the manifest actually hosted at `manifest_url` at audit time.

`validate_url` additionally rejects, in contract code, a set of dangerous
URL shapes (embedded credentials, bare IP-literal hosts, a curated
forbidden-host list, non-default ports) as defense-in-depth; see
`docs/SECURITY_MODEL.md` for exactly what this does and does not verify
about GenVM's own runtime behavior.

## Equivalence principle

For each sampled slot:

1. leader independently fetches the manifest;
2. leader checks the pinned manifest hash and item count;
3. leader selects the already-deterministic sampled item;
4. leader independently fetches the item and checks its pinned hash;
5. leader asks the LLM for `PASS`, `FAIL`, or `INCONCLUSIVE` against the
   frozen rubric;
6. validator independently repeats steps 1-5;
7. validator accepts only when outcome and evidence identity/hash fields
   agree exactly.

Reason prose is retained for review but is not consensus-critical.

This is substantive re-observation. Validators do not merely schema-check
the leader; see the live validator-trace evidence in
`docs/DEPLOYMENT_EVIDENCE.md` and the `test_validator_independently_*`
direct-mode tests.

## Batch settlement

Consensus never returns `CERTIFIED` or `REJECTED` directly. It returns one
sampled-item outcome at a time.

Deterministic state counts those outcomes and applies the frozen threshold.
Any inconclusive sample makes the batch inconclusive. This preserves
uncertainty rather than laundering unavailable evidence into a pass.

## Certificate

The terminal certificate hash commits to:

- assessment id (which itself binds chain, contract, manifest, and rubric);
- batch id;
- manifest digest;
- rubric digest;
- sampling seed digest;
- threshold;
- terminal status;
- ordered sample index/outcome/item-hash tuples.

```text
certificate = sha256(
  "AUDITLOT_CERT_V2" | assessment_id | batch_id | manifest_sha256 |
  rubric_sha256 | seed_sha256 | min_pass_bps | terminal_status |
  outcomes...
)
```

manifest/rubric digests are included explicitly (in addition to being
transitively encoded in `assessment_id`) so the hash preimage is
independently reconstructible from its own listed components, without
requiring a trusting lookup of what `assessment_id` encodes.

Downstream builders can pin this certificate hash when consuming a batch
result. See `docs/SECURITY_MODEL.md`'s "What this certificate does and does
not mean" for the precise, bounded scope of that guarantee -- it is a
statement about this one sample of this one manifest under this one rubric,
not about dataset completeness or unsampled items.
