"""
Direct-mode (GLSim-equivalent) GenVM execution tests for contracts/auditlot.py
(v2: bonded, assessment-locked fairness redesign).

Unlike tests/test_protocol_model.py (pure-Python re-implementation of the
deterministic math), these tests load and execute the actual contract file
through the real GenLayer SDK / GenVM storage and nondet machinery via the
`gltest` direct-mode runner.
"""

import hashlib
import json

import pytest

CONTRACT_PATH = "contracts/auditlot.py"

FUTURE_DEADLINE = "2030-01-01T00:00:00Z"
PAST_DEADLINE = "2020-01-01T00:00:00Z"

VALIDATOR_PROMPT_PATTERN = r"You are one validator in a blind semantic batch audit"
RUBRIC_TEXT = "Item must be a clean, complete deliverable satisfying the brief."
MIN_BOND_ATOMS = 10**15


# ---------------------------------------------------------------------------
# Fixture manifest / commitment helpers
# ---------------------------------------------------------------------------


def sha256_hex(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def commitment_of(secret: str, assessment_id: str, role: str) -> str:
    return hashlib.sha256(("AUDITLOT_COMMIT_V2|" + assessment_id + "|" + role + "|" + secret).encode()).hexdigest()


def make_items(count: int, prefix: str = "https://fixtures.example.org/item"):
    items = []
    bodies = {}
    for i in range(count):
        body = f"Deliverable {i} satisfies the frozen rubric with clean evidence.".encode("utf-8")
        url = f"{prefix}-{i}.txt"
        items.append({"id": f"item-{i}", "url": url, "sha256": sha256_hex(body)})
        bodies[url] = body
    return items, bodies


def canonical_manifest(items):
    manifest = {"version": "auditlot-1", "items": items}
    raw = json.dumps(manifest, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")
    return raw, sha256_hex(raw)


def mock_good_fixtures(direct_vm, manifest_url, manifest_body, items, bodies):
    direct_vm.mock_web(escape(manifest_url), {"status": 200, "body": manifest_body.decode("utf-8")})
    for item in items:
        direct_vm.mock_web(escape(item["url"]), {"status": 200, "body": bodies[item["url"]].decode("utf-8")})


def escape(url: str) -> str:
    import re

    return re.escape(url)


def _as_address(raw):
    from genlayer.py.types import Address

    return raw if isinstance(raw, Address) else Address(raw)


def install_transfer_recorder(direct_vm):
    """Install a _gl_call_hook that records every PostMessage (the wire
    format behind the EVM-style wallet emit_transfer(value=...) as EthSend) so bond
    forfeiture/refund targeting and amounts can be asserted in direct mode,
    which does not otherwise model native GEN balance movement."""
    transfers = []

    def hook(vm, request):
        if isinstance(request, dict):
            if "EthSend" in request:
                pm = request["EthSend"]
                transfers.append((pm.get("address"), int(pm.get("value", 0))))
        return {"ok": None}

    direct_vm._gl_call_hook = hook
    return transfers


# ---------------------------------------------------------------------------
# Shared setup
# ---------------------------------------------------------------------------


def _deploy(direct_deploy):
    return direct_deploy(CONTRACT_PATH)


def _assessment_id(contract, manifest_sha256, rubric=RUBRIC_TEXT):
    return contract.assessment_id_for(manifest_sha256, sha256_hex(rubric.strip().encode()))


def _create_batch(
    contract,
    direct_vm,
    producer,
    partner,
    manifest_url,
    manifest_sha256,
    item_count,
    sample_size,
    min_pass_bps=6667,
    reveal_deadline=FUTURE_DEADLINE,
    rubric=RUBRIC_TEXT,
    bond=MIN_BOND_ATOMS,
    producer_secret="producer-secret-alpha",
):
    assessment_id = _assessment_id(contract, manifest_sha256, rubric)
    commitment = commitment_of(producer_secret, assessment_id, "producer")
    direct_vm.sender = producer
    direct_vm.value = bond
    try:
        batch_id = contract.create_batch(
            manifest_url=manifest_url,
            manifest_sha256=manifest_sha256,
            rubric=rubric,
            entropy_partner=_as_address(partner),
            producer_commitment=commitment,
            reveal_deadline=reveal_deadline,
            item_count=item_count,
            sample_size=sample_size,
            min_pass_bps=min_pass_bps,
        )
    finally:
        direct_vm.value = 0
    return batch_id, assessment_id


def _join(contract, direct_vm, partner, batch_id, assessment_id, partner_secret="partner-secret-beta", bond=MIN_BOND_ATOMS):
    partner_commitment = commitment_of(partner_secret, assessment_id, "partner")
    direct_vm.sender = partner
    direct_vm.value = bond
    try:
        contract.join_entropy(batch_id, partner_commitment)
    finally:
        direct_vm.value = 0


def _create_and_match_and_reveal(
    contract,
    direct_vm,
    producer,
    partner,
    manifest_url,
    manifest_sha256,
    item_count,
    sample_size,
    min_pass_bps=6667,
    reveal_deadline=FUTURE_DEADLINE,
    rubric=RUBRIC_TEXT,
    bond=MIN_BOND_ATOMS,
    producer_secret="producer-secret-alpha",
    partner_secret="partner-secret-beta",
):
    batch_id, assessment_id = _create_batch(
        contract, direct_vm, producer, partner, manifest_url, manifest_sha256,
        item_count, sample_size, min_pass_bps, reveal_deadline, rubric, bond, producer_secret,
    )
    _join(contract, direct_vm, partner, batch_id, assessment_id, partner_secret, bond)

    direct_vm.sender = partner
    contract.reveal_entropy(batch_id, partner_secret)
    direct_vm.sender = producer
    contract.reveal_entropy(batch_id, producer_secret)

    return batch_id, assessment_id


def _audit_all(contract, batch_id, sample_size):
    for slot in range(sample_size):
        contract.audit_sample(batch_id, slot)


# ---------------------------------------------------------------------------
# B. Happy-path certification
# ---------------------------------------------------------------------------


def test_certified_batch_when_all_sampled_items_pass(direct_deploy, direct_vm, direct_owner, direct_alice):
    contract = _deploy(direct_deploy)
    items, bodies = make_items(6)
    manifest_body, manifest_sha = canonical_manifest(items)
    manifest_url = "https://fixtures.example.org/manifest.json"

    mock_good_fixtures(direct_vm, manifest_url, manifest_body, items, bodies)
    direct_vm.mock_llm(VALIDATOR_PROMPT_PATTERN, json.dumps({"outcome": "PASS", "reason": "meets rubric"}))

    batch_id, assessment_id = _create_and_match_and_reveal(
        contract, direct_vm, direct_owner, direct_alice,
        manifest_url, manifest_sha, item_count=6, sample_size=3, min_pass_bps=6667,
    )

    batch = contract.get_batch(batch_id)
    assert batch["status_name"] == "SAMPLE_READY"
    assert batch["assessment_id"] == assessment_id
    assert batch["bond_atoms"] == MIN_BOND_ATOMS
    assert len(batch["sample_indices"]) == 3
    assert len(set(batch["sample_indices"])) == 3

    _audit_all(contract, batch_id, 3)

    transfers = install_transfer_recorder(direct_vm)
    contract.settle(batch_id)

    final = contract.get_batch(batch_id)
    assert final["status_name"] == "CERTIFIED"
    assert final["pass_count"] == 3
    assert final["bonds_settled"] is True
    # Both bonds refunded in full: a fairly-drawn sample is never penalized
    # regardless of its outcome.
    assert (_as_address(direct_owner), MIN_BOND_ATOMS) in transfers
    assert (_as_address(direct_alice), MIN_BOND_ATOMS) in transfers

    assessment = contract.get_assessment(assessment_id)
    assert assessment["resolved"] is True
    assert assessment["resolved_batch_id"] == batch_id
    assert assessment["active_batch_id"] == 0

    cert = contract.get_certificate(batch_id)
    assert cert["status_name"] == "CERTIFIED"
    assert contract.is_certified(batch_id, final["certificate_sha256"]) is True


def test_rejected_batch_when_sampled_items_fail(direct_deploy, direct_vm, direct_owner, direct_alice):
    contract = _deploy(direct_deploy)
    items, bodies = make_items(6)
    manifest_body, manifest_sha = canonical_manifest(items)
    manifest_url = "https://fixtures.example.org/manifest-fail.json"

    mock_good_fixtures(direct_vm, manifest_url, manifest_body, items, bodies)
    direct_vm.mock_llm(VALIDATOR_PROMPT_PATTERN, json.dumps({"outcome": "FAIL", "reason": "violates rubric"}))

    batch_id, _ = _create_and_match_and_reveal(
        contract, direct_vm, direct_owner, direct_alice,
        manifest_url, manifest_sha, item_count=6, sample_size=3, min_pass_bps=6667,
    )
    _audit_all(contract, batch_id, 3)
    contract.settle(batch_id)

    final = contract.get_batch(batch_id)
    assert final["status_name"] == "REJECTED"
    assert final["fail_count"] == 3


def test_inconclusive_when_item_bytes_do_not_match_pinned_hash(direct_deploy, direct_vm, direct_owner, direct_alice):
    contract = _deploy(direct_deploy)
    items, bodies = make_items(6)
    manifest_body, manifest_sha = canonical_manifest(items)
    manifest_url = "https://fixtures.example.org/manifest-tamper.json"

    direct_vm.mock_web(escape(manifest_url), {"status": 200, "body": manifest_body.decode("utf-8")})
    for item in items:
        direct_vm.mock_web(escape(item["url"]), {"status": 200, "body": "TAMPERED CONTENT"})
    direct_vm.mock_llm(VALIDATOR_PROMPT_PATTERN, json.dumps({"outcome": "PASS", "reason": "n/a"}))

    batch_id, _ = _create_and_match_and_reveal(
        contract, direct_vm, direct_owner, direct_alice,
        manifest_url, manifest_sha, item_count=6, sample_size=3, min_pass_bps=6667,
    )
    _audit_all(contract, batch_id, 3)
    contract.settle(batch_id)

    final = contract.get_batch(batch_id)
    assert final["status_name"] == "INCONCLUSIVE"
    assert final["inconclusive_count"] == 3
    for slot in range(3):
        audit = contract.get_audit(batch_id, slot)
        assert audit["outcome_name"] == "INCONCLUSIVE"


# ---------------------------------------------------------------------------
# Bonding: amounts, matching, and refund/forfeiture accounting
# ---------------------------------------------------------------------------


def test_create_batch_rejects_bond_below_minimum(direct_deploy, direct_vm, direct_owner, direct_alice):
    contract = _deploy(direct_deploy)
    items, bodies = make_items(1)
    _, manifest_sha = canonical_manifest(items)
    assessment_id = _assessment_id(contract, manifest_sha)
    commitment = commitment_of("s", assessment_id, "producer")
    direct_vm.sender = direct_owner
    direct_vm.value = MIN_BOND_ATOMS - 1
    try:
        # create_batch/join_entropy never raise once payable -- see the note
        # on IAuditLot.Write in the contract. They refund in full and
        # return a sentinel (batch_id 0 / False) instead, so a refund
        # scheduled before a would-be revert isn't itself rolled back by
        # that revert. Callers must check the return value.
        batch_id = contract.create_batch(
            manifest_url="https://fixtures.example.org/manifest-lowbond.json",
            manifest_sha256=manifest_sha, rubric=RUBRIC_TEXT,
            entropy_partner=_as_address(direct_alice), producer_commitment=commitment,
            reveal_deadline=FUTURE_DEADLINE, item_count=1, sample_size=1, min_pass_bps=1,
        )
    finally:
        direct_vm.value = 0
    assert batch_id == 0


def test_create_batch_refunds_value_when_a_later_validation_fails(direct_deploy, direct_vm, direct_owner, direct_alice):
    # GenVM credits gl.message.value to the contract as part of message
    # delivery, before the method body runs, and does NOT roll that credit
    # back on revert -- confirmed live on Studionet the hard way: a first
    # version of this fix refunded and then re-raised, and the "refund"
    # never arrived, because re-raising still reverts the whole call and a
    # revert rolls back every normal side effect made during it, including
    # a refund transfer scheduled just before the raise. create_batch must
    # therefore never raise once payable -- it refunds and returns 0
    # instead, so the call is a *success* from GenVM's perspective and the
    # scheduled refund actually commits. This test attaches a valid bond
    # but an otherwise-invalid argument (self as entropy partner) so the
    # failure happens well after the bond-amount check, proving the refund
    # wrapper covers the whole method body, not just the bond check.
    contract = _deploy(direct_deploy)
    items, bodies = make_items(1)
    _, manifest_sha = canonical_manifest(items)
    assessment_id = _assessment_id(contract, manifest_sha)
    commitment = commitment_of("s", assessment_id, "producer")
    transfers = install_transfer_recorder(direct_vm)
    direct_vm.sender = direct_owner
    direct_vm.value = MIN_BOND_ATOMS
    try:
        batch_id = contract.create_batch(
            manifest_url="https://fixtures.example.org/manifest-refund-fail.json",
            manifest_sha256=manifest_sha, rubric=RUBRIC_TEXT,
            entropy_partner=_as_address(direct_owner), producer_commitment=commitment,
            reveal_deadline=FUTURE_DEADLINE, item_count=1, sample_size=1, min_pass_bps=1,
        )
    finally:
        direct_vm.value = 0
    assert batch_id == 0
    assert transfers == [(_as_address(direct_owner), MIN_BOND_ATOMS)]


def test_join_entropy_refunds_value_when_validation_fails(direct_deploy, direct_vm, direct_owner, direct_alice, direct_bob):
    contract = _deploy(direct_deploy)
    items, bodies = make_items(1)
    _, manifest_sha = canonical_manifest(items)
    batch_id, _ = _create_batch(
        contract, direct_vm, direct_owner, direct_alice,
        "https://fixtures.example.org/manifest-join-refund.json", manifest_sha,
        item_count=1, sample_size=1, min_pass_bps=1,
    )
    transfers = install_transfer_recorder(direct_vm)
    direct_vm.sender = direct_bob  # not the designated entropy partner
    direct_vm.value = MIN_BOND_ATOMS
    try:
        joined = contract.join_entropy(batch_id, commitment_of("x", "irrelevant", "partner"))
    finally:
        direct_vm.value = 0
    assert joined is False
    assert transfers == [(_as_address(direct_bob), MIN_BOND_ATOMS)]


def test_join_entropy_requires_exact_bond_match(direct_deploy, direct_vm, direct_owner, direct_alice):
    contract = _deploy(direct_deploy)
    items, bodies = make_items(1)
    _, manifest_sha = canonical_manifest(items)
    batch_id, assessment_id = _create_batch(
        contract, direct_vm, direct_owner, direct_alice,
        "https://fixtures.example.org/manifest-bondmismatch.json", manifest_sha,
        item_count=1, sample_size=1, min_pass_bps=1,
    )
    partner_commitment = commitment_of("partner-secret", assessment_id, "partner")
    direct_vm.sender = direct_alice
    direct_vm.value = MIN_BOND_ATOMS - 1
    try:
        joined = contract.join_entropy(batch_id, partner_commitment)
    finally:
        direct_vm.value = 0
    assert joined is False
    direct_vm.value = MIN_BOND_ATOMS + 1
    try:
        joined = contract.join_entropy(batch_id, partner_commitment)
    finally:
        direct_vm.value = 0
    assert joined is False


def test_settle_refunds_both_bonds_regardless_of_outcome(direct_deploy, direct_vm, direct_owner, direct_alice):
    contract = _deploy(direct_deploy)
    items, bodies = make_items(1)
    manifest_body, manifest_sha = canonical_manifest(items)
    manifest_url = "https://fixtures.example.org/manifest-refund.json"
    mock_good_fixtures(direct_vm, manifest_url, manifest_body, items, bodies)
    direct_vm.mock_llm(VALIDATOR_PROMPT_PATTERN, json.dumps({"outcome": "FAIL", "reason": "n/a"}))

    bond = MIN_BOND_ATOMS * 3
    batch_id, _ = _create_and_match_and_reveal(
        contract, direct_vm, direct_owner, direct_alice,
        manifest_url, manifest_sha, item_count=1, sample_size=1, min_pass_bps=9999, bond=bond,
    )
    contract.audit_sample(batch_id, 0)
    transfers = install_transfer_recorder(direct_vm)
    contract.settle(batch_id)
    assert contract.get_batch(batch_id)["status_name"] == "REJECTED"
    assert (_as_address(direct_owner), bond) in transfers
    assert (_as_address(direct_alice), bond) in transfers


def test_cancel_unmatched_refunds_producer_bond_in_full(direct_deploy, direct_vm, direct_owner, direct_alice):
    contract = _deploy(direct_deploy)
    items, bodies = make_items(1)
    _, manifest_sha = canonical_manifest(items)
    bond = MIN_BOND_ATOMS * 2
    batch_id, _ = _create_batch(
        contract, direct_vm, direct_owner, direct_alice,
        "https://fixtures.example.org/manifest-cancelrefund.json", manifest_sha,
        item_count=1, sample_size=1, min_pass_bps=1, bond=bond,
    )
    transfers = install_transfer_recorder(direct_vm)
    direct_vm.sender = direct_owner
    contract.cancel_unmatched(batch_id)
    assert transfers == [(_as_address(direct_owner), bond)]
    assert contract.get_batch(batch_id)["bonds_settled"] is True


# ---------------------------------------------------------------------------
# Cherry-picking prevention: canonical assessment identity + retry policy
# ---------------------------------------------------------------------------


def test_resolved_assessment_cannot_be_retried(direct_deploy, direct_vm, direct_owner, direct_alice):
    contract = _deploy(direct_deploy)
    items, bodies = make_items(1)
    manifest_body, manifest_sha = canonical_manifest(items)
    manifest_url = "https://fixtures.example.org/manifest-noretry.json"
    mock_good_fixtures(direct_vm, manifest_url, manifest_body, items, bodies)
    direct_vm.mock_llm(VALIDATOR_PROMPT_PATTERN, json.dumps({"outcome": "FAIL", "reason": "n/a"}))

    batch_id, assessment_id = _create_and_match_and_reveal(
        contract, direct_vm, direct_owner, direct_alice,
        manifest_url, manifest_sha, item_count=1, sample_size=1, min_pass_bps=9999,
        producer_secret="attempt-1-producer", partner_secret="attempt-1-partner",
    )
    contract.audit_sample(batch_id, 0)
    contract.settle(batch_id)
    assert contract.get_batch(batch_id)["status_name"] == "REJECTED"

    # The producer dislikes the real, fairly-sampled REJECTED result and
    # tries to create a brand-new batch for the exact same manifest+rubric,
    # hoping for a better draw. This must be structurally impossible, not
    # merely discouraged.
    retry_batch_id, _ = _create_batch(
        contract, direct_vm, direct_owner, direct_alice,
        manifest_url, manifest_sha, item_count=1, sample_size=1, min_pass_bps=9999,
        producer_secret="attempt-2-producer",
    )
    assert retry_batch_id == 0


def test_retry_after_real_result_is_blocked_even_with_different_sampling_parameters(direct_deploy, direct_vm, direct_owner, direct_alice):
    # Closing a related loophole: lowering the threshold (or changing
    # sample_size) for the SAME manifest+rubric after an unfavorable result
    # must not be a backdoor around the resolved-lock, since assessment
    # identity is keyed on (chain, contract, manifest, rubric) only.
    contract = _deploy(direct_deploy)
    items, bodies = make_items(1)
    manifest_body, manifest_sha = canonical_manifest(items)
    manifest_url = "https://fixtures.example.org/manifest-noretry-diffparams.json"
    mock_good_fixtures(direct_vm, manifest_url, manifest_body, items, bodies)
    direct_vm.mock_llm(VALIDATOR_PROMPT_PATTERN, json.dumps({"outcome": "FAIL", "reason": "n/a"}))

    batch_id, _ = _create_and_match_and_reveal(
        contract, direct_vm, direct_owner, direct_alice,
        manifest_url, manifest_sha, item_count=1, sample_size=1, min_pass_bps=9999,
    )
    contract.audit_sample(batch_id, 0)
    contract.settle(batch_id)

    retry_batch_id, _ = _create_batch(
        contract, direct_vm, direct_owner, direct_alice,
        manifest_url, manifest_sha, item_count=1, sample_size=1, min_pass_bps=1,
        producer_secret="attempt-lower-threshold",
    )
    assert retry_batch_id == 0


def test_retry_must_reuse_locked_sampling_parameters_and_bond(direct_deploy, direct_vm, direct_owner, direct_alice, direct_bob):
    # First attempt aborts (unresolved) so a retry is legal, but the retry
    # must match the first attempt's locked parameters exactly.
    contract = _deploy(direct_deploy)
    items, bodies = make_items(6)
    _, manifest_sha = canonical_manifest(items)
    manifest_url = "https://fixtures.example.org/manifest-lockedparams.json"

    batch_id, assessment_id = _create_batch(
        contract, direct_vm, direct_owner, direct_alice,
        manifest_url, manifest_sha, item_count=6, sample_size=3, min_pass_bps=6667,
    )
    direct_vm.sender = direct_owner
    contract.cancel_unmatched(batch_id)  # unresolved, does not lock/resolve the assessment

    retry_batch_id, _ = _create_batch(
        contract, direct_vm, direct_owner, direct_bob,
        manifest_url, manifest_sha, item_count=6, sample_size=4, min_pass_bps=6667,
        producer_secret="second-attempt",
    )
    assert retry_batch_id == 0

    # Reusing the exact same locked parameters succeeds.
    batch_id_2, _ = _create_batch(
        contract, direct_vm, direct_owner, direct_bob,
        manifest_url, manifest_sha, item_count=6, sample_size=3, min_pass_bps=6667,
        producer_secret="second-attempt-ok",
    )
    assert contract.get_batch(batch_id_2)["status_name"] == "OPEN"


def test_create_batch_rejects_reused_commitment(direct_deploy, direct_vm, direct_owner, direct_alice, direct_bob):
    contract = _deploy(direct_deploy)
    items, bodies = make_items(1)
    _, manifest_sha_a = canonical_manifest(items)
    manifest_url_a = "https://fixtures.example.org/manifest-reuse-a.json"
    batch_id_a, assessment_id_a = _create_batch(
        contract, direct_vm, direct_owner, direct_alice,
        manifest_url_a, manifest_sha_a, item_count=1, sample_size=1, min_pass_bps=1,
        producer_secret="shared-secret",
    )

    items_b, _ = make_items(1, prefix="https://fixtures.example.org/other-item")
    _, manifest_sha_b = canonical_manifest(items_b)
    manifest_url_b = "https://fixtures.example.org/manifest-reuse-b.json"
    assessment_id_b = _assessment_id(contract, manifest_sha_b)
    reused_commitment = commitment_of("shared-secret", assessment_id_a, "producer")
    # Even trying to reuse the exact same commitment hash the contract
    # already recorded for assessment A, this time nominally "for" a
    # different manifest B, must be rejected: a revealed secret becoming
    # public knowledge must never be safely reusable anywhere.
    direct_vm.sender = direct_owner
    direct_vm.value = MIN_BOND_ATOMS
    try:
        reused_batch_id = contract.create_batch(
            manifest_url=manifest_url_b, manifest_sha256=manifest_sha_b, rubric=RUBRIC_TEXT,
            entropy_partner=_as_address(direct_bob), producer_commitment=reused_commitment,
            reveal_deadline=FUTURE_DEADLINE, item_count=1, sample_size=1, min_pass_bps=1,
        )
    finally:
        direct_vm.value = 0
    assert reused_batch_id == 0


def test_only_one_active_batch_per_assessment_at_a_time(direct_deploy, direct_vm, direct_owner, direct_alice, direct_bob):
    contract = _deploy(direct_deploy)
    items, bodies = make_items(1)
    _, manifest_sha = canonical_manifest(items)
    manifest_url = "https://fixtures.example.org/manifest-oneactive.json"
    batch_id, _ = _create_batch(
        contract, direct_vm, direct_owner, direct_alice,
        manifest_url, manifest_sha, item_count=1, sample_size=1, min_pass_bps=1,
    )
    assert contract.get_batch(batch_id)["status_name"] == "OPEN"
    second_batch_id, _ = _create_batch(
        contract, direct_vm, direct_owner, direct_bob,
        manifest_url, manifest_sha, item_count=1, sample_size=1, min_pass_bps=1,
        producer_secret="second-while-first-active",
    )
    assert second_batch_id == 0


# ---------------------------------------------------------------------------
# G. Retry cap: bounded re-rolling, not a trivial permanent DoS
# ---------------------------------------------------------------------------


def test_abort_non_reveal_rejected_while_deadline_still_open(direct_deploy, direct_vm, direct_owner, direct_alice):
    # NOTE ON HARNESS LIMITATION: gltest direct-mode's VMContext.warp() only
    # patches Python's datetime.datetime.now(); it does not refresh the
    # injected consensus gl.message.raw.datetime this contract correctly
    # reads (confirmed empirically: that value is captured once per
    # deployed contract instance and does not advance with real wall-clock
    # time either). Direct mode therefore cannot simulate deadline passage.
    # The full non-reveal -> ABORTED transition, the resulting bond
    # forfeiture, and abort_count/MAX_ABORTS_PER_ASSESSMENT enforcement
    # across repeated real aborts are proven live on Studionet per
    # docs/LIVE_TEST_PLAN.md section G and docs/DEPLOYMENT_EVIDENCE.md. This
    # test covers what direct mode *can* verify: the guard rejects an abort
    # attempt before the deadline has actually passed.
    contract = _deploy(direct_deploy)
    items, bodies = make_items(1)
    _, manifest_sha = canonical_manifest(items)
    batch_id, assessment_id = _create_batch(
        contract, direct_vm, direct_owner, direct_alice,
        "https://fixtures.example.org/manifest-abort.json", manifest_sha,
        item_count=1, sample_size=1, min_pass_bps=1,
    )
    _join(contract, direct_vm, direct_alice, batch_id, assessment_id)
    direct_vm.sender = direct_alice
    contract.reveal_entropy(batch_id, "partner-secret-beta")
    with direct_vm.expect_revert("reveal deadline has not passed"):
        contract.abort_non_reveal(batch_id)
    batch = contract.get_batch(batch_id)
    assert batch["status_name"] == "MATCHED"


def test_abort_non_reveal_rejected_once_sample_ready(direct_deploy, direct_vm, direct_owner, direct_alice):
    contract = _deploy(direct_deploy)
    items, bodies = make_items(1)
    manifest_body, manifest_sha = canonical_manifest(items)
    manifest_url = "https://fixtures.example.org/manifest-abort-bypass.json"
    mock_good_fixtures(direct_vm, manifest_url, manifest_body, items, bodies)

    batch_id, _ = _create_and_match_and_reveal(
        contract, direct_vm, direct_owner, direct_alice,
        manifest_url, manifest_sha, item_count=1, sample_size=1, min_pass_bps=1,
    )
    assert contract.get_batch(batch_id)["status_name"] == "SAMPLE_READY"
    with direct_vm.expect_revert("batch cannot be aborted"):
        contract.abort_non_reveal(batch_id)


# ---------------------------------------------------------------------------
# E. Commitment / reveal edge cases
# ---------------------------------------------------------------------------


def test_reveal_with_wrong_secret_is_rejected_and_does_not_advance_state(direct_deploy, direct_vm, direct_owner, direct_alice):
    contract = _deploy(direct_deploy)
    items, bodies = make_items(1)
    _, manifest_sha = canonical_manifest(items)
    batch_id, assessment_id = _create_batch(
        contract, direct_vm, direct_owner, direct_alice,
        "https://fixtures.example.org/manifest-mismatch.json", manifest_sha,
        item_count=1, sample_size=1, min_pass_bps=1,
    )
    _join(contract, direct_vm, direct_alice, batch_id, assessment_id)

    with direct_vm.expect_revert("partner commitment mismatch"):
        direct_vm.sender = direct_alice
        contract.reveal_entropy(batch_id, "not-the-real-secret")

    batch = contract.get_batch(batch_id)
    assert batch["status_name"] == "MATCHED"
    assert batch["seed_sha256"] == ""


def test_reveal_before_matched_is_rejected(direct_deploy, direct_vm, direct_owner, direct_alice):
    contract = _deploy(direct_deploy)
    items, bodies = make_items(1)
    _, manifest_sha = canonical_manifest(items)
    batch_id, _ = _create_batch(
        contract, direct_vm, direct_owner, direct_alice,
        "https://fixtures.example.org/manifest-x.json", manifest_sha,
        item_count=1, sample_size=1, min_pass_bps=1,
    )
    with direct_vm.expect_revert("batch is not awaiting entropy"):
        direct_vm.sender = direct_owner
        contract.reveal_entropy(batch_id, "producer-secret-alpha")


def test_reveal_by_non_participant_is_rejected(direct_deploy, direct_vm, direct_owner, direct_alice, direct_bob):
    contract = _deploy(direct_deploy)
    items, bodies = make_items(1)
    _, manifest_sha = canonical_manifest(items)
    batch_id, assessment_id = _create_batch(
        contract, direct_vm, direct_owner, direct_alice,
        "https://fixtures.example.org/manifest-y.json", manifest_sha,
        item_count=1, sample_size=1, min_pass_bps=1,
    )
    _join(contract, direct_vm, direct_alice, batch_id, assessment_id)
    direct_vm.sender = direct_bob
    with direct_vm.expect_revert("caller is not an entropy participant"):
        contract.reveal_entropy(batch_id, "producer-secret-alpha")


def test_producer_cannot_reveal_twice(direct_deploy, direct_vm, direct_owner, direct_alice):
    contract = _deploy(direct_deploy)
    items, bodies = make_items(1)
    _, manifest_sha = canonical_manifest(items)
    batch_id, assessment_id = _create_batch(
        contract, direct_vm, direct_owner, direct_alice,
        "https://fixtures.example.org/manifest-z.json", manifest_sha,
        item_count=1, sample_size=1, min_pass_bps=1,
    )
    _join(contract, direct_vm, direct_alice, batch_id, assessment_id)
    direct_vm.sender = direct_owner
    contract.reveal_entropy(batch_id, "producer-secret-alpha")
    with direct_vm.expect_revert("producer already revealed"):
        contract.reveal_entropy(batch_id, "producer-secret-alpha")


def test_join_entropy_requires_designated_partner(direct_deploy, direct_vm, direct_owner, direct_alice, direct_bob):
    contract = _deploy(direct_deploy)
    items, bodies = make_items(1)
    _, manifest_sha = canonical_manifest(items)
    batch_id, assessment_id = _create_batch(
        contract, direct_vm, direct_owner, direct_alice,
        "https://fixtures.example.org/manifest-partner.json", manifest_sha,
        item_count=1, sample_size=1, min_pass_bps=1,
    )
    partner_commitment = commitment_of("intruder-secret", assessment_id, "partner")
    direct_vm.sender = direct_bob
    direct_vm.value = MIN_BOND_ATOMS
    try:
        joined = contract.join_entropy(batch_id, partner_commitment)
    finally:
        direct_vm.value = 0
    assert joined is False


def test_join_entropy_twice_is_rejected(direct_deploy, direct_vm, direct_owner, direct_alice):
    contract = _deploy(direct_deploy)
    items, bodies = make_items(1)
    _, manifest_sha = canonical_manifest(items)
    batch_id, assessment_id = _create_batch(
        contract, direct_vm, direct_owner, direct_alice,
        "https://fixtures.example.org/manifest-join2.json", manifest_sha,
        item_count=1, sample_size=1, min_pass_bps=1,
    )
    _join(contract, direct_vm, direct_alice, batch_id, assessment_id)
    partner_commitment_2 = commitment_of("partner-secret-2", assessment_id, "partner")
    direct_vm.sender = direct_alice
    direct_vm.value = MIN_BOND_ATOMS
    try:
        joined = contract.join_entropy(batch_id, partner_commitment_2)
    finally:
        direct_vm.value = 0
    assert joined is False


def test_create_batch_rejects_self_as_entropy_partner(direct_deploy, direct_vm, direct_owner):
    contract = _deploy(direct_deploy)
    items, bodies = make_items(1)
    _, manifest_sha = canonical_manifest(items)
    assessment_id = _assessment_id(contract, manifest_sha)
    commitment = commitment_of("s", assessment_id, "producer")
    direct_vm.sender = direct_owner
    direct_vm.value = MIN_BOND_ATOMS
    try:
        rejected_batch_id = contract.create_batch(
            manifest_url="https://fixtures.example.org/manifest-self.json",
            manifest_sha256=manifest_sha, rubric=RUBRIC_TEXT,
            entropy_partner=_as_address(direct_owner), producer_commitment=commitment,
            reveal_deadline=FUTURE_DEADLINE, item_count=1, sample_size=1, min_pass_bps=1,
        )
    finally:
        direct_vm.value = 0
    assert rejected_batch_id == 0


def test_create_batch_rejects_past_deadline(direct_deploy, direct_vm, direct_owner, direct_alice):
    contract = _deploy(direct_deploy)
    items, bodies = make_items(1)
    _, manifest_sha = canonical_manifest(items)
    assessment_id = _assessment_id(contract, manifest_sha)
    commitment = commitment_of("s", assessment_id, "producer")
    direct_vm.sender = direct_owner
    direct_vm.value = MIN_BOND_ATOMS
    try:
        rejected_batch_id = contract.create_batch(
            manifest_url="https://fixtures.example.org/manifest-past.json",
            manifest_sha256=manifest_sha, rubric=RUBRIC_TEXT,
            entropy_partner=_as_address(direct_alice), producer_commitment=commitment,
            reveal_deadline=PAST_DEADLINE, item_count=1, sample_size=1, min_pass_bps=1,
        )
    finally:
        direct_vm.value = 0
    assert rejected_batch_id == 0


@pytest.mark.parametrize(
    "field,value",
    [
        ("manifest_sha256", "not-a-digest"),
        ("manifest_sha256", "deadbeef"),
        ("producer_commitment", "short"),
    ],
)
def test_create_batch_rejects_malformed_digests(direct_deploy, direct_vm, direct_owner, direct_alice, field, value):
    contract = _deploy(direct_deploy)
    items, bodies = make_items(1)
    _, manifest_sha = canonical_manifest(items)
    assessment_id = _assessment_id(contract, manifest_sha)
    commitment = commitment_of("s", assessment_id, "producer")
    kwargs = dict(
        manifest_url="https://fixtures.example.org/manifest-digest.json",
        manifest_sha256=manifest_sha, rubric=RUBRIC_TEXT,
        entropy_partner=_as_address(direct_alice), producer_commitment=commitment,
        reveal_deadline=FUTURE_DEADLINE, item_count=1, sample_size=1, min_pass_bps=1,
    )
    kwargs[field] = value
    direct_vm.sender = direct_owner
    direct_vm.value = MIN_BOND_ATOMS
    try:
        rejected_batch_id = contract.create_batch(**kwargs)
    finally:
        direct_vm.value = 0
    assert rejected_batch_id == 0


@pytest.mark.parametrize(
    "field,value,message",
    [
        ("item_count", 0, "item_count out of range"),
        ("item_count", 10001, "item_count out of range"),
        ("sample_size", 0, "sample_size out of range"),
        ("sample_size", 26, "sample_size out of range"),
        ("min_pass_bps", 0, "min_pass_bps must be 1..10000"),
        ("min_pass_bps", 10001, "min_pass_bps must be 1..10000"),
    ],
)
def test_create_batch_rejects_out_of_range_dimensions(direct_deploy, direct_vm, direct_owner, direct_alice, field, value, message):
    contract = _deploy(direct_deploy)
    items, bodies = make_items(1)
    _, manifest_sha = canonical_manifest(items)
    assessment_id = _assessment_id(contract, manifest_sha)
    commitment = commitment_of("s", assessment_id, "producer")
    kwargs = dict(
        manifest_url="https://fixtures.example.org/manifest-dims.json",
        manifest_sha256=manifest_sha, rubric=RUBRIC_TEXT,
        entropy_partner=_as_address(direct_alice), producer_commitment=commitment,
        reveal_deadline=FUTURE_DEADLINE, item_count=1, sample_size=1, min_pass_bps=1,
    )
    kwargs[field] = value
    direct_vm.sender = direct_owner
    direct_vm.value = MIN_BOND_ATOMS
    try:
        rejected_batch_id = contract.create_batch(**kwargs)
    finally:
        direct_vm.value = 0
    assert rejected_batch_id == 0


# ---------------------------------------------------------------------------
# URL validation hardening
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "bad_url,message",
    [
        ("http://fixtures.example.org/manifest.json", "must use https"),
        ("https://user:pass@fixtures.example.org/manifest.json", "must not contain embedded credentials"),
        ("https://127.0.0.1/manifest.json", "must use a DNS hostname"),
        ("https://169.254.169.254/manifest.json", "must use a DNS hostname"),
        ("https://[::1]/manifest.json", "must use a DNS hostname"),
        ("https://localhost/manifest.json", "host is not permitted"),
        ("https://metadata.google.internal/manifest.json", "host is not permitted"),
        ("https://svc.internal/manifest.json", "host is not permitted"),
        ("https://fixtures.example.org:8443/manifest.json", "must use the default https port"),
    ],
)
def test_create_batch_rejects_dangerous_manifest_urls(direct_deploy, direct_vm, direct_owner, direct_alice, bad_url, message):
    contract = _deploy(direct_deploy)
    items, bodies = make_items(1)
    _, manifest_sha = canonical_manifest(items)
    assessment_id = _assessment_id(contract, manifest_sha)
    commitment = commitment_of("s", assessment_id, "producer")
    direct_vm.sender = direct_owner
    direct_vm.value = MIN_BOND_ATOMS
    try:
        rejected_batch_id = contract.create_batch(
            manifest_url=bad_url, manifest_sha256=manifest_sha, rubric=RUBRIC_TEXT,
            entropy_partner=_as_address(direct_alice), producer_commitment=commitment,
            reveal_deadline=FUTURE_DEADLINE, item_count=1, sample_size=1, min_pass_bps=1,
        )
    finally:
        direct_vm.value = 0
    assert rejected_batch_id == 0


def test_create_batch_accepts_ordinary_https_hostname_url(direct_deploy, direct_vm, direct_owner, direct_alice):
    contract = _deploy(direct_deploy)
    items, bodies = make_items(1)
    _, manifest_sha = canonical_manifest(items)
    batch_id, _ = _create_batch(
        contract, direct_vm, direct_owner, direct_alice,
        "https://fixtures.example.org/path/manifest.json", manifest_sha,
        item_count=1, sample_size=1, min_pass_bps=1,
    )
    assert contract.get_batch(batch_id)["status_name"] == "OPEN"


# ---------------------------------------------------------------------------
# Calendar date validation
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "bad_deadline",
    [
        "2030-02-30T00:00:00Z",  # no such day in any February
        "2030-04-31T00:00:00Z",  # April has 30 days
        "2029-02-29T00:00:00Z",  # 2029 is not a leap year
        "2030-13-01T00:00:00Z",  # no month 13
        "2030-00-01T00:00:00Z",  # no month 0
    ],
)
def test_create_batch_rejects_invalid_calendar_dates(direct_deploy, direct_vm, direct_owner, direct_alice, bad_deadline):
    contract = _deploy(direct_deploy)
    items, bodies = make_items(1)
    _, manifest_sha = canonical_manifest(items)
    assessment_id = _assessment_id(contract, manifest_sha)
    commitment = commitment_of("s", assessment_id, "producer")
    direct_vm.sender = direct_owner
    direct_vm.value = MIN_BOND_ATOMS
    try:
        rejected_batch_id = contract.create_batch(
            manifest_url="https://fixtures.example.org/manifest-baddate.json",
            manifest_sha256=manifest_sha, rubric=RUBRIC_TEXT,
            entropy_partner=_as_address(direct_alice), producer_commitment=commitment,
            reveal_deadline=bad_deadline, item_count=1, sample_size=1, min_pass_bps=1,
        )
    finally:
        direct_vm.value = 0
    assert rejected_batch_id == 0


def test_create_batch_accepts_leap_year_feb_29(direct_deploy, direct_vm, direct_owner, direct_alice):
    contract = _deploy(direct_deploy)
    items, bodies = make_items(1)
    _, manifest_sha = canonical_manifest(items)
    batch_id, _ = _create_batch(
        contract, direct_vm, direct_owner, direct_alice,
        "https://fixtures.example.org/manifest-leap.json", manifest_sha,
        item_count=1, sample_size=1, min_pass_bps=1,
        reveal_deadline="2032-02-29T12:00:00Z",  # 2032 is a leap year
    )
    assert contract.get_batch(batch_id)["reveal_deadline"] == "2032-02-29T12:00:00Z"


# ---------------------------------------------------------------------------
# Missing/malformed transaction timestamp: fail closed, not fail open
# ---------------------------------------------------------------------------


def test_missing_transaction_timestamp_fails_closed(direct_deploy, direct_vm, direct_owner, direct_alice):
    # Blank the VM's datetime before the very first call (deploy), which is
    # when direct mode's injected consensus timestamp is captured for the
    # lifetime of this contract instance -- see the harness-limitation note
    # above. Every deadline-gated write must now revert with a clear,
    # accurate error rather than silently behaving as if the deadline had
    # already passed (the v1 bug) or as if it were still open.
    direct_vm._datetime = ""
    contract = _deploy(direct_deploy)
    items, bodies = make_items(1)
    _, manifest_sha = canonical_manifest(items)
    assessment_id = _assessment_id(contract, manifest_sha)
    commitment = commitment_of("s", assessment_id, "producer")
    direct_vm.sender = direct_owner
    direct_vm.value = MIN_BOND_ATOMS
    try:
        rejected_batch_id = contract.create_batch(
            manifest_url="https://fixtures.example.org/manifest-notime.json",
            manifest_sha256=manifest_sha, rubric=RUBRIC_TEXT,
            entropy_partner=_as_address(direct_alice), producer_commitment=commitment,
            reveal_deadline=FUTURE_DEADLINE, item_count=1, sample_size=1, min_pass_bps=1,
        )
    finally:
        direct_vm.value = 0
    assert rejected_batch_id == 0


# ---------------------------------------------------------------------------
# F. Sampling uniqueness
# ---------------------------------------------------------------------------


def test_full_sample_covers_every_index_exactly_once(direct_deploy, direct_vm, direct_owner, direct_alice):
    contract = _deploy(direct_deploy)
    items, bodies = make_items(10)
    manifest_body, manifest_sha = canonical_manifest(items)
    manifest_url = "https://fixtures.example.org/manifest-full.json"
    mock_good_fixtures(direct_vm, manifest_url, manifest_body, items, bodies)

    batch_id, _ = _create_and_match_and_reveal(
        contract, direct_vm, direct_owner, direct_alice,
        manifest_url, manifest_sha, item_count=10, sample_size=10, min_pass_bps=1,
    )
    batch = contract.get_batch(batch_id)
    assert sorted(batch["sample_indices"]) == list(range(10))


def test_entropy_changes_the_sample(direct_deploy, direct_vm, direct_owner, direct_alice, direct_bob, direct_charlie):
    contract = _deploy(direct_deploy)
    items, bodies = make_items(100)
    manifest_body, manifest_sha = canonical_manifest(items)
    manifest_url = "https://fixtures.example.org/manifest-entropy.json"
    mock_good_fixtures(direct_vm, manifest_url, manifest_body, items, bodies)

    batch_a, assessment_id = _create_batch(
        contract, direct_vm, direct_owner, direct_alice,
        manifest_url, manifest_sha, item_count=100, sample_size=10, min_pass_bps=1,
        producer_secret="secret-A1",
    )
    _join(contract, direct_vm, direct_alice, batch_a, assessment_id, partner_secret="secret-A2")
    direct_vm.sender = direct_alice
    contract.reveal_entropy(batch_a, "secret-A2")
    direct_vm.sender = direct_owner
    contract.reveal_entropy(batch_a, "secret-A1")
    indices_a = contract.get_batch(batch_a)["sample_indices"]

    # A different assessment (different manifest) so a second live batch can
    # exist independently and prove entropy sensitivity.
    items_b, bodies_b = make_items(100, prefix="https://fixtures.example.org/itemB")
    manifest_body_b, manifest_sha_b = canonical_manifest(items_b)
    manifest_url_b = "https://fixtures.example.org/manifest-entropy-b.json"
    mock_good_fixtures(direct_vm, manifest_url_b, manifest_body_b, items_b, bodies_b)
    batch_b, assessment_id_b = _create_batch(
        contract, direct_vm, direct_bob, direct_charlie,
        manifest_url_b, manifest_sha_b, item_count=100, sample_size=10, min_pass_bps=1,
        producer_secret="secret-B1",
    )
    _join(contract, direct_vm, direct_charlie, batch_b, assessment_id_b, partner_secret="secret-B2")
    direct_vm.sender = direct_charlie
    contract.reveal_entropy(batch_b, "secret-B2")
    direct_vm.sender = direct_bob
    contract.reveal_entropy(batch_b, "secret-B1")
    indices_b = contract.get_batch(batch_b)["sample_indices"]

    assert indices_a != indices_b


# ---------------------------------------------------------------------------
# H. Replay / state-machine rejection
# ---------------------------------------------------------------------------


def test_audit_sample_before_ready_is_rejected(direct_deploy, direct_vm, direct_owner, direct_alice):
    contract = _deploy(direct_deploy)
    items, bodies = make_items(1)
    _, manifest_sha = canonical_manifest(items)
    batch_id, _ = _create_batch(
        contract, direct_vm, direct_owner, direct_alice,
        "https://fixtures.example.org/manifest-notready.json", manifest_sha,
        item_count=1, sample_size=1, min_pass_bps=1,
    )
    with direct_vm.expect_revert("batch sample is not ready"):
        contract.audit_sample(batch_id, 0)


def test_duplicate_audit_of_same_slot_is_rejected(direct_deploy, direct_vm, direct_owner, direct_alice):
    contract = _deploy(direct_deploy)
    items, bodies = make_items(1)
    manifest_body, manifest_sha = canonical_manifest(items)
    manifest_url = "https://fixtures.example.org/manifest-dupaudit.json"
    mock_good_fixtures(direct_vm, manifest_url, manifest_body, items, bodies)
    direct_vm.mock_llm(VALIDATOR_PROMPT_PATTERN, json.dumps({"outcome": "PASS", "reason": "ok"}))

    batch_id, _ = _create_and_match_and_reveal(
        contract, direct_vm, direct_owner, direct_alice,
        manifest_url, manifest_sha, item_count=1, sample_size=1, min_pass_bps=1,
    )
    contract.audit_sample(batch_id, 0)
    with direct_vm.expect_revert("sample slot already audited"):
        contract.audit_sample(batch_id, 0)


def test_settle_before_all_audited_is_rejected(direct_deploy, direct_vm, direct_owner, direct_alice):
    contract = _deploy(direct_deploy)
    items, bodies = make_items(6)
    manifest_body, manifest_sha = canonical_manifest(items)
    manifest_url = "https://fixtures.example.org/manifest-earlysettle.json"
    mock_good_fixtures(direct_vm, manifest_url, manifest_body, items, bodies)
    direct_vm.mock_llm(VALIDATOR_PROMPT_PATTERN, json.dumps({"outcome": "PASS", "reason": "ok"}))

    batch_id, _ = _create_and_match_and_reveal(
        contract, direct_vm, direct_owner, direct_alice,
        manifest_url, manifest_sha, item_count=6, sample_size=3, min_pass_bps=1,
    )
    contract.audit_sample(batch_id, 0)
    with direct_vm.expect_revert("every sampled slot must be audited"):
        contract.settle(batch_id)


def test_settle_twice_is_rejected(direct_deploy, direct_vm, direct_owner, direct_alice):
    contract = _deploy(direct_deploy)
    items, bodies = make_items(1)
    manifest_body, manifest_sha = canonical_manifest(items)
    manifest_url = "https://fixtures.example.org/manifest-settletwice.json"
    mock_good_fixtures(direct_vm, manifest_url, manifest_body, items, bodies)
    direct_vm.mock_llm(VALIDATOR_PROMPT_PATTERN, json.dumps({"outcome": "PASS", "reason": "ok"}))

    batch_id, _ = _create_and_match_and_reveal(
        contract, direct_vm, direct_owner, direct_alice,
        manifest_url, manifest_sha, item_count=1, sample_size=1, min_pass_bps=1,
    )
    contract.audit_sample(batch_id, 0)
    contract.settle(batch_id)
    with direct_vm.expect_revert("batch is not settleable"):
        contract.settle(batch_id)


def test_cancel_unmatched_only_by_producer_while_open(direct_deploy, direct_vm, direct_owner, direct_alice, direct_bob):
    contract = _deploy(direct_deploy)
    items, bodies = make_items(1)
    _, manifest_sha = canonical_manifest(items)
    batch_id, _ = _create_batch(
        contract, direct_vm, direct_owner, direct_alice,
        "https://fixtures.example.org/manifest-cancel.json", manifest_sha,
        item_count=1, sample_size=1, min_pass_bps=1,
    )
    direct_vm.sender = direct_bob
    with direct_vm.expect_revert("only producer may cancel"):
        contract.cancel_unmatched(batch_id)

    direct_vm.sender = direct_owner
    contract.cancel_unmatched(batch_id)
    assert contract.get_batch(batch_id)["status_name"] == "CANCELLED"

    with direct_vm.expect_revert("only unmatched batches may be cancelled"):
        contract.cancel_unmatched(batch_id)


# ---------------------------------------------------------------------------
# I. Validator independence
# ---------------------------------------------------------------------------


def test_validator_independently_agrees_when_it_reaches_the_same_result(direct_deploy, direct_vm, direct_owner, direct_alice):
    contract = _deploy(direct_deploy)
    items, bodies = make_items(1)
    manifest_body, manifest_sha = canonical_manifest(items)
    manifest_url = "https://fixtures.example.org/manifest-valagree.json"
    mock_good_fixtures(direct_vm, manifest_url, manifest_body, items, bodies)
    direct_vm.mock_llm(VALIDATOR_PROMPT_PATTERN, json.dumps({"outcome": "PASS", "reason": "leader reason"}))

    batch_id, _ = _create_and_match_and_reveal(
        contract, direct_vm, direct_owner, direct_alice,
        manifest_url, manifest_sha, item_count=1, sample_size=1, min_pass_bps=1,
    )
    contract.audit_sample(batch_id, 0)

    direct_vm.clear_mocks()
    mock_good_fixtures(direct_vm, manifest_url, manifest_body, items, bodies)
    direct_vm.mock_llm(VALIDATOR_PROMPT_PATTERN, json.dumps({"outcome": "PASS", "reason": "a completely different independent rationale"}))
    assert direct_vm.run_validator() is True


def test_validator_independently_disagrees_on_different_semantic_outcome(direct_deploy, direct_vm, direct_owner, direct_alice):
    contract = _deploy(direct_deploy)
    items, bodies = make_items(1)
    manifest_body, manifest_sha = canonical_manifest(items)
    manifest_url = "https://fixtures.example.org/manifest-valdisagree.json"
    mock_good_fixtures(direct_vm, manifest_url, manifest_body, items, bodies)
    direct_vm.mock_llm(VALIDATOR_PROMPT_PATTERN, json.dumps({"outcome": "PASS", "reason": "leader reason"}))

    batch_id, _ = _create_and_match_and_reveal(
        contract, direct_vm, direct_owner, direct_alice,
        manifest_url, manifest_sha, item_count=1, sample_size=1, min_pass_bps=1,
    )
    contract.audit_sample(batch_id, 0)

    direct_vm.clear_mocks()
    mock_good_fixtures(direct_vm, manifest_url, manifest_body, items, bodies)
    direct_vm.mock_llm(VALIDATOR_PROMPT_PATTERN, json.dumps({"outcome": "FAIL", "reason": "independent validator disagrees"}))
    assert direct_vm.run_validator() is False


def test_validator_independently_disagrees_when_its_own_fetch_sees_different_evidence(direct_deploy, direct_vm, direct_owner, direct_alice):
    contract = _deploy(direct_deploy)
    items, bodies = make_items(1)
    manifest_body, manifest_sha = canonical_manifest(items)
    manifest_url = "https://fixtures.example.org/manifest-valrefetch.json"
    mock_good_fixtures(direct_vm, manifest_url, manifest_body, items, bodies)
    direct_vm.mock_llm(VALIDATOR_PROMPT_PATTERN, json.dumps({"outcome": "PASS", "reason": "leader reason"}))

    batch_id, _ = _create_and_match_and_reveal(
        contract, direct_vm, direct_owner, direct_alice,
        manifest_url, manifest_sha, item_count=1, sample_size=1, min_pass_bps=1,
    )
    contract.audit_sample(batch_id, 0)

    direct_vm.clear_mocks()
    direct_vm.mock_web(escape(manifest_url), {"status": 200, "body": manifest_body.decode("utf-8")})
    for item in items:
        direct_vm.mock_web(escape(item["url"]), {"status": 200, "body": "a validator observed different bytes"})
    direct_vm.mock_llm(VALIDATOR_PROMPT_PATTERN, json.dumps({"outcome": "PASS", "reason": "would still pass if it got this far"}))
    assert direct_vm.run_validator() is False


# ---------------------------------------------------------------------------
# Last-revealer preview: what the redesign bounds vs. what it structurally
# closes. See the G-section note above for why the *reveal-time* preview
# itself cannot be forced/observed in direct mode (no real deadline
# passage), and docs/LIVE_TEST_PLAN.md / docs/DEPLOYMENT_EVIDENCE.md for the
# live proof of the full withhold -> abort -> forfeiture -> capped-retry
# sequence. This test proves the piece direct mode *can* fully exercise:
# the mathematical fact that a party holding both the already-revealed
# counterpart secret and its own candidate secret(s) can compute the
# resulting sample for each candidate before ever calling reveal_entropy,
# i.e. that the preview is real and not mitigated by the seed formula
# itself -- which is exactly why AuditLot v2 does not claim the sample is
# unbiased against a rational withholding adversary, only that withholding
# is priced (bond forfeiture) and capped (MAX_ABORTS_PER_ASSESSMENT).
# ---------------------------------------------------------------------------


def test_last_revealer_preview_is_real_and_is_what_bonding_prices(direct_deploy, direct_vm, direct_owner, direct_alice):
    import hashlib as _hashlib

    contract = _deploy(direct_deploy)
    items, bodies = make_items(6)
    manifest_body, manifest_sha = canonical_manifest(items)
    manifest_url = "https://fixtures.example.org/manifest-preview.json"
    mock_good_fixtures(direct_vm, manifest_url, manifest_body, items, bodies)

    batch_id, assessment_id = _create_batch(
        contract, direct_vm, direct_owner, direct_alice,
        manifest_url, manifest_sha, item_count=6, sample_size=3, min_pass_bps=6667,
        producer_secret="producer-secret-alpha",
    )
    _join(contract, direct_vm, direct_alice, batch_id, assessment_id, partner_secret="partner-secret-beta")

    # Producer reveals first (public from this point on).
    direct_vm.sender = direct_owner
    contract.reveal_entropy(batch_id, "producer-secret-alpha")

    # The entropy partner -- BEFORE calling reveal_entropy at all -- can
    # locally recompute what the sample would become for its own known
    # candidate secret, using exactly the contract's own seed formula and
    # the now-public producer secret. No transaction is required to do this.
    def local_seed(partner_secret: str) -> str:
        return _hashlib.sha256(
            (
                "AUDITLOT_SEED_V2|" + assessment_id + "|" + str(int(batch_id))
                + "|producer-secret-alpha|" + partner_secret
            ).encode()
        ).hexdigest()

    def local_sample(seed: str, n: int, k: int):
        out, counter, modulus = [], 0, 1 << 256
        limit = modulus - (modulus % n)
        while len(out) < k:
            x = int.from_bytes(_hashlib.sha256(f"AUDITLOT_SAMPLE_V1|{seed}|{counter}".encode()).digest(), "big")
            counter += 1
            if x >= limit:
                continue
            i = x % n
            if i not in out:
                out.append(i)
        return out

    previewed = local_sample(local_seed("partner-secret-beta"), 6, 3)

    # Now the partner actually reveals and the contract independently
    # derives the same sample -- proving the local preview above was
    # accurate, i.e. genuinely predictive, not a coincidence.
    direct_vm.sender = direct_alice
    contract.reveal_entropy(batch_id, "partner-secret-beta")
    on_chain_sample = contract.get_batch(batch_id)["sample_indices"]
    assert on_chain_sample == previewed

    # This is precisely the information a withholding party would use to
    # decide whether to submit its reveal at all. AuditLot v2 does not (and
    # structurally cannot, absent a randomness beacon this platform does
    # not expose to contracts) prevent this preview; it prices withholding
    # via bond forfeiture and bounds it via MAX_ABORTS_PER_ASSESSMENT,
    # proven live in docs/DEPLOYMENT_EVIDENCE.md.
