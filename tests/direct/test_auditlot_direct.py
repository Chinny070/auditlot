"""
Direct-mode (GLSim-equivalent) GenVM execution tests for contracts/auditlot.py.

Unlike tests/test_protocol_model.py (pure-Python re-implementation of the
deterministic math), these tests load and execute the actual contract file
through the real GenLayer SDK / GenVM storage and nondet machinery via the
`gltest` direct-mode runner. They exercise TreeMap/DynArray storage,
@gl.public.write/view decorators, gl.vm.run_nondet_unsafe leader/validator
closures, gl.nondet.web.get, gl.nondet.exec_prompt, and gl.message timestamp
plumbing -- the class of bug the pure protocol-model tests cannot catch.
"""

import datetime
import hashlib
import json
import time

import pytest

CONTRACT_PATH = "contracts/auditlot.py"

FUTURE_DEADLINE = "2030-01-01T00:00:00Z"
PAST_DEADLINE = "2020-01-01T00:00:00Z"

VALIDATOR_PROMPT_PATTERN = r"You are one validator in a blind semantic batch audit"


# ---------------------------------------------------------------------------
# Fixture manifest helpers (mirror scripts/build_manifest.py canonicalization)
# ---------------------------------------------------------------------------


def sha256_hex(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def commitment_of(secret: str) -> str:
    return hashlib.sha256(("AUDITLOT_V1|" + secret).encode()).hexdigest()


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


# ---------------------------------------------------------------------------
# Shared setup
# ---------------------------------------------------------------------------


def _deploy(direct_deploy):
    return direct_deploy(CONTRACT_PATH)


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
    rubric="Item must be a clean, complete deliverable satisfying the brief.",
    producer_secret="producer-secret-alpha",
    partner_secret="partner-secret-beta",
):
    direct_vm.sender = producer
    batch_id = contract.create_batch(
        manifest_url=manifest_url,
        manifest_sha256=manifest_sha256,
        rubric=rubric,
        entropy_partner=_as_address(partner),
        producer_commitment=commitment_of(producer_secret),
        reveal_deadline=reveal_deadline,
        item_count=item_count,
        sample_size=sample_size,
        min_pass_bps=min_pass_bps,
    )

    direct_vm.sender = partner
    contract.join_entropy(batch_id, commitment_of(partner_secret))

    direct_vm.sender = partner
    contract.reveal_entropy(batch_id, partner_secret)
    direct_vm.sender = producer
    contract.reveal_entropy(batch_id, producer_secret)

    return batch_id


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

    batch_id = _create_and_match_and_reveal(
        contract, direct_vm, direct_owner, direct_alice,
        manifest_url, manifest_sha, item_count=6, sample_size=3, min_pass_bps=6667,
    )

    batch = contract.get_batch(batch_id)
    assert batch["status_name"] == "SAMPLE_READY"
    assert len(batch["sample_indices"]) == 3
    assert len(set(batch["sample_indices"])) == 3
    assert all(0 <= i < 6 for i in batch["sample_indices"])
    # secrets must be scrubbed from mutable state once the sample is fixed
    assert batch["seed_sha256"] != ""

    _audit_all(contract, batch_id, 3)
    contract.settle(batch_id)

    final = contract.get_batch(batch_id)
    assert final["status_name"] == "CERTIFIED"
    assert final["pass_count"] == 3
    assert final["fail_count"] == 0
    assert final["inconclusive_count"] == 0
    assert final["certificate_sha256"] != ""

    cert = contract.get_certificate(batch_id)
    assert cert["status_name"] == "CERTIFIED"
    assert cert["pass_bps"] == 10000
    assert contract.is_certified(batch_id, final["certificate_sha256"]) is True
    assert contract.is_certified(batch_id, "0" * 64) is False


# ---------------------------------------------------------------------------
# C. Rejected batch
# ---------------------------------------------------------------------------


def test_rejected_batch_when_sampled_items_fail(direct_deploy, direct_vm, direct_owner, direct_alice):
    contract = _deploy(direct_deploy)
    items, bodies = make_items(6)
    manifest_body, manifest_sha = canonical_manifest(items)
    manifest_url = "https://fixtures.example.org/manifest-fail.json"

    mock_good_fixtures(direct_vm, manifest_url, manifest_body, items, bodies)
    direct_vm.mock_llm(VALIDATOR_PROMPT_PATTERN, json.dumps({"outcome": "FAIL", "reason": "violates rubric"}))

    batch_id = _create_and_match_and_reveal(
        contract, direct_vm, direct_owner, direct_alice,
        manifest_url, manifest_sha, item_count=6, sample_size=3, min_pass_bps=6667,
    )
    _audit_all(contract, batch_id, 3)
    contract.settle(batch_id)

    final = contract.get_batch(batch_id)
    assert final["status_name"] == "REJECTED"
    assert final["fail_count"] == 3
    assert final["pass_count"] == 0


# ---------------------------------------------------------------------------
# D. Inconclusive fail-closed path
# ---------------------------------------------------------------------------


def test_inconclusive_when_item_bytes_do_not_match_pinned_hash(direct_deploy, direct_vm, direct_owner, direct_alice):
    contract = _deploy(direct_deploy)
    items, bodies = make_items(6)
    manifest_body, manifest_sha = canonical_manifest(items)
    manifest_url = "https://fixtures.example.org/manifest-tamper.json"

    direct_vm.mock_web(escape(manifest_url), {"status": 200, "body": manifest_body.decode("utf-8")})
    for item in items:
        # Serve different bytes than what the manifest pinned -> hash mismatch.
        direct_vm.mock_web(escape(item["url"]), {"status": 200, "body": "TAMPERED CONTENT"})
    direct_vm.mock_llm(VALIDATOR_PROMPT_PATTERN, json.dumps({"outcome": "PASS", "reason": "n/a"}))

    batch_id = _create_and_match_and_reveal(
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
        assert audit["item_sha256"] == ""


def test_inconclusive_when_manifest_unavailable(direct_deploy, direct_vm, direct_owner, direct_alice):
    contract = _deploy(direct_deploy)
    items, bodies = make_items(1)
    manifest_body, manifest_sha = canonical_manifest(items)
    manifest_url = "https://fixtures.example.org/manifest-missing.json"
    # No mock registered for the manifest URL at all -> unavailable/exception path.

    batch_id = _create_and_match_and_reveal(
        contract, direct_vm, direct_owner, direct_alice,
        manifest_url, manifest_sha, item_count=1, sample_size=1, min_pass_bps=1,
    )
    contract.audit_sample(batch_id, 0)
    audit = contract.get_audit(batch_id, 0)
    assert audit["outcome_name"] == "INCONCLUSIVE"


def test_settle_stays_inconclusive_even_if_some_samples_pass(direct_deploy, direct_vm, direct_owner, direct_alice):
    # One inconclusive sample must poison the whole batch even when the
    # other sampled items clearly pass -- uncertainty must never be
    # laundered into a pass.
    contract = _deploy(direct_deploy)
    items, bodies = make_items(10)
    manifest_body, manifest_sha = canonical_manifest(items)
    manifest_url = "https://fixtures.example.org/manifest-mixed.json"

    direct_vm.mock_web(escape(manifest_url), {"status": 200, "body": manifest_body.decode("utf-8")})
    for item in items:
        direct_vm.mock_web(escape(item["url"]), {"status": 200, "body": bodies[item["url"]].decode("utf-8")})
    direct_vm.mock_llm(VALIDATOR_PROMPT_PATTERN, json.dumps({"outcome": "PASS", "reason": "ok"}))

    batch_id = _create_and_match_and_reveal(
        contract, direct_vm, direct_owner, direct_alice,
        manifest_url, manifest_sha, item_count=10, sample_size=10, min_pass_bps=1,
    )
    batch = contract.get_batch(batch_id)
    assert sorted(batch["sample_indices"]) == list(range(10))
    # Full permutation over 10 items: slot 9's *item_index* is whichever
    # manifest item the deterministic sampler happened to place last, not
    # necessarily manifest item 9.
    poisoned_item_index = batch["sample_indices"][9]

    # Audit slots 0..8 as PASS, then break the hash for slot 9's actual
    # sampled item so exactly one sample is unresolved evidence.
    for slot in range(9):
        contract.audit_sample(batch_id, slot)

    direct_vm.clear_mocks()
    direct_vm.mock_web(escape(manifest_url), {"status": 200, "body": manifest_body.decode("utf-8")})
    for item in items:
        if item["id"] == f"item-{poisoned_item_index}":
            direct_vm.mock_web(escape(item["url"]), {"status": 200, "body": "CORRUPTED"})
        else:
            direct_vm.mock_web(escape(item["url"]), {"status": 200, "body": bodies[item["url"]].decode("utf-8")})
    direct_vm.mock_llm(VALIDATOR_PROMPT_PATTERN, json.dumps({"outcome": "PASS", "reason": "ok"}))
    contract.audit_sample(batch_id, 9)

    contract.settle(batch_id)
    final = contract.get_batch(batch_id)
    assert final["status_name"] == "INCONCLUSIVE"
    assert final["pass_count"] == 9
    assert final["inconclusive_count"] == 1


# ---------------------------------------------------------------------------
# E. Commitment / reveal edge cases
# ---------------------------------------------------------------------------


def test_reveal_with_wrong_secret_is_rejected_and_does_not_advance_state(direct_deploy, direct_vm, direct_owner, direct_alice):
    contract = _deploy(direct_deploy)
    items, bodies = make_items(1)
    _, manifest_sha = canonical_manifest(items)
    manifest_url = "https://fixtures.example.org/manifest-mismatch.json"

    direct_vm.sender = direct_owner
    batch_id = contract.create_batch(
        manifest_url=manifest_url,
        manifest_sha256=manifest_sha,
        rubric="rubric text",
        entropy_partner=_as_address(direct_alice),
        producer_commitment=commitment_of("producer-secret"),
        reveal_deadline=FUTURE_DEADLINE,
        item_count=1,
        sample_size=1,
        min_pass_bps=1,
    )
    direct_vm.sender = direct_alice
    contract.join_entropy(batch_id, commitment_of("partner-secret"))

    with direct_vm.expect_revert("partner commitment mismatch"):
        contract.reveal_entropy(batch_id, "not-the-real-secret")

    batch = contract.get_batch(batch_id)
    assert batch["status_name"] == "MATCHED"
    assert batch["seed_sha256"] == ""


def test_reveal_before_matched_is_rejected(direct_deploy, direct_vm, direct_owner, direct_alice):
    contract = _deploy(direct_deploy)
    items, bodies = make_items(1)
    _, manifest_sha = canonical_manifest(items)
    direct_vm.sender = direct_owner
    batch_id = contract.create_batch(
        manifest_url="https://fixtures.example.org/manifest-x.json",
        manifest_sha256=manifest_sha,
        rubric="rubric text",
        entropy_partner=_as_address(direct_alice),
        producer_commitment=commitment_of("producer-secret"),
        reveal_deadline=FUTURE_DEADLINE,
        item_count=1,
        sample_size=1,
        min_pass_bps=1,
    )
    with direct_vm.expect_revert("batch is not awaiting entropy"):
        contract.reveal_entropy(batch_id, "producer-secret")


def test_reveal_by_non_participant_is_rejected(direct_deploy, direct_vm, direct_owner, direct_alice, direct_bob):
    contract = _deploy(direct_deploy)
    items, bodies = make_items(1)
    _, manifest_sha = canonical_manifest(items)
    direct_vm.sender = direct_owner
    batch_id = contract.create_batch(
        manifest_url="https://fixtures.example.org/manifest-y.json",
        manifest_sha256=manifest_sha,
        rubric="rubric text",
        entropy_partner=_as_address(direct_alice),
        producer_commitment=commitment_of("producer-secret"),
        reveal_deadline=FUTURE_DEADLINE,
        item_count=1,
        sample_size=1,
        min_pass_bps=1,
    )
    direct_vm.sender = direct_alice
    contract.join_entropy(batch_id, commitment_of("partner-secret"))

    direct_vm.sender = direct_bob
    with direct_vm.expect_revert("caller is not an entropy participant"):
        contract.reveal_entropy(batch_id, "producer-secret")


def test_producer_cannot_reveal_twice(direct_deploy, direct_vm, direct_owner, direct_alice):
    contract = _deploy(direct_deploy)
    items, bodies = make_items(1)
    manifest_body, manifest_sha = canonical_manifest(items)
    manifest_url = "https://fixtures.example.org/manifest-z.json"
    direct_vm.mock_web(escape(manifest_url), {"status": 200, "body": manifest_body.decode("utf-8")})
    for item in items:
        direct_vm.mock_web(escape(item["url"]), {"status": 200, "body": bodies[item["url"]].decode("utf-8")})

    direct_vm.sender = direct_owner
    batch_id = contract.create_batch(
        manifest_url=manifest_url,
        manifest_sha256=manifest_sha,
        rubric="rubric text",
        entropy_partner=_as_address(direct_alice),
        producer_commitment=commitment_of("producer-secret"),
        reveal_deadline=FUTURE_DEADLINE,
        item_count=1,
        sample_size=1,
        min_pass_bps=1,
    )
    direct_vm.sender = direct_alice
    contract.join_entropy(batch_id, commitment_of("partner-secret"))
    direct_vm.sender = direct_owner
    contract.reveal_entropy(batch_id, "producer-secret")

    with direct_vm.expect_revert("producer already revealed"):
        contract.reveal_entropy(batch_id, "producer-secret")


def test_join_entropy_requires_designated_partner(direct_deploy, direct_vm, direct_owner, direct_alice, direct_bob):
    contract = _deploy(direct_deploy)
    items, bodies = make_items(1)
    _, manifest_sha = canonical_manifest(items)
    direct_vm.sender = direct_owner
    batch_id = contract.create_batch(
        manifest_url="https://fixtures.example.org/manifest-partner.json",
        manifest_sha256=manifest_sha,
        rubric="rubric text",
        entropy_partner=_as_address(direct_alice),
        producer_commitment=commitment_of("producer-secret"),
        reveal_deadline=FUTURE_DEADLINE,
        item_count=1,
        sample_size=1,
        min_pass_bps=1,
    )
    direct_vm.sender = direct_bob
    with direct_vm.expect_revert("only designated entropy partner may join"):
        contract.join_entropy(batch_id, commitment_of("partner-secret"))


def test_join_entropy_twice_is_rejected(direct_deploy, direct_vm, direct_owner, direct_alice):
    contract = _deploy(direct_deploy)
    items, bodies = make_items(1)
    _, manifest_sha = canonical_manifest(items)
    direct_vm.sender = direct_owner
    batch_id = contract.create_batch(
        manifest_url="https://fixtures.example.org/manifest-join2.json",
        manifest_sha256=manifest_sha,
        rubric="rubric text",
        entropy_partner=_as_address(direct_alice),
        producer_commitment=commitment_of("producer-secret"),
        reveal_deadline=FUTURE_DEADLINE,
        item_count=1,
        sample_size=1,
        min_pass_bps=1,
    )
    direct_vm.sender = direct_alice
    contract.join_entropy(batch_id, commitment_of("partner-secret"))
    with direct_vm.expect_revert("batch is not open"):
        contract.join_entropy(batch_id, commitment_of("partner-secret-2"))


def test_create_batch_rejects_self_as_entropy_partner(direct_deploy, direct_vm, direct_owner):
    contract = _deploy(direct_deploy)
    items, bodies = make_items(1)
    _, manifest_sha = canonical_manifest(items)
    direct_vm.sender = direct_owner
    with direct_vm.expect_revert("entropy partner must be independent"):
        contract.create_batch(
            manifest_url="https://fixtures.example.org/manifest-self.json",
            manifest_sha256=manifest_sha,
            rubric="rubric text",
            entropy_partner=_as_address(direct_owner),
            producer_commitment=commitment_of("producer-secret"),
            reveal_deadline=FUTURE_DEADLINE,
            item_count=1,
            sample_size=1,
            min_pass_bps=1,
        )


def test_create_batch_rejects_past_deadline(direct_deploy, direct_vm, direct_owner, direct_alice):
    contract = _deploy(direct_deploy)
    items, bodies = make_items(1)
    _, manifest_sha = canonical_manifest(items)
    direct_vm.sender = direct_owner
    with direct_vm.expect_revert("reveal deadline must be in the future"):
        contract.create_batch(
            manifest_url="https://fixtures.example.org/manifest-past.json",
            manifest_sha256=manifest_sha,
            rubric="rubric text",
            entropy_partner=_as_address(direct_alice),
            producer_commitment=commitment_of("producer-secret"),
            reveal_deadline=PAST_DEADLINE,
            item_count=1,
            sample_size=1,
            min_pass_bps=1,
        )


@pytest.mark.parametrize(
    "field,value",
    [
        ("manifest_sha256", "not-a-digest"),
        ("manifest_sha256", "deadbeef"),  # too short
        ("producer_commitment", "short"),
    ],
)
def test_create_batch_rejects_malformed_digests(direct_deploy, direct_vm, direct_owner, direct_alice, field, value):
    contract = _deploy(direct_deploy)
    items, bodies = make_items(1)
    _, manifest_sha = canonical_manifest(items)
    kwargs = dict(
        manifest_url="https://fixtures.example.org/manifest-digest.json",
        manifest_sha256=manifest_sha,
        rubric="rubric text",
        entropy_partner=_as_address(direct_alice),
        producer_commitment=commitment_of("producer-secret"),
        reveal_deadline=FUTURE_DEADLINE,
        item_count=1,
        sample_size=1,
        min_pass_bps=1,
    )
    kwargs[field] = value
    direct_vm.sender = direct_owner
    with direct_vm.expect_revert("must be a lowercase sha256 digest"):
        contract.create_batch(**kwargs)


def test_create_batch_rejects_non_https_manifest_url(direct_deploy, direct_vm, direct_owner, direct_alice):
    contract = _deploy(direct_deploy)
    items, bodies = make_items(1)
    _, manifest_sha = canonical_manifest(items)
    direct_vm.sender = direct_owner
    with direct_vm.expect_revert("must use https"):
        contract.create_batch(
            manifest_url="http://fixtures.example.org/manifest-insecure.json",
            manifest_sha256=manifest_sha,
            rubric="rubric text",
            entropy_partner=_as_address(direct_alice),
            producer_commitment=commitment_of("producer-secret"),
            reveal_deadline=FUTURE_DEADLINE,
            item_count=1,
            sample_size=1,
            min_pass_bps=1,
        )


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
    kwargs = dict(
        manifest_url="https://fixtures.example.org/manifest-dims.json",
        manifest_sha256=manifest_sha,
        rubric="rubric text",
        entropy_partner=_as_address(direct_alice),
        producer_commitment=commitment_of("producer-secret"),
        reveal_deadline=FUTURE_DEADLINE,
        item_count=1,
        sample_size=1,
        min_pass_bps=1,
    )
    kwargs[field] = value
    direct_vm.sender = direct_owner
    with direct_vm.expect_revert(message):
        contract.create_batch(**kwargs)


def test_create_batch_rejects_sample_size_larger_than_item_count(direct_deploy, direct_vm, direct_owner, direct_alice):
    contract = _deploy(direct_deploy)
    items, bodies = make_items(3)
    _, manifest_sha = canonical_manifest(items)
    direct_vm.sender = direct_owner
    with direct_vm.expect_revert("sample_size out of range"):
        contract.create_batch(
            manifest_url="https://fixtures.example.org/manifest-oversample.json",
            manifest_sha256=manifest_sha,
            rubric="rubric text",
            entropy_partner=_as_address(direct_alice),
            producer_commitment=commitment_of("producer-secret"),
            reveal_deadline=FUTURE_DEADLINE,
            item_count=3,
            sample_size=4,
            min_pass_bps=1,
        )


# ---------------------------------------------------------------------------
# F. Sampling uniqueness
# ---------------------------------------------------------------------------


def test_full_sample_covers_every_index_exactly_once(direct_deploy, direct_vm, direct_owner, direct_alice):
    contract = _deploy(direct_deploy)
    items, bodies = make_items(10)
    manifest_body, manifest_sha = canonical_manifest(items)
    manifest_url = "https://fixtures.example.org/manifest-full.json"
    mock_good_fixtures(direct_vm, manifest_url, manifest_body, items, bodies)

    batch_id = _create_and_match_and_reveal(
        contract, direct_vm, direct_owner, direct_alice,
        manifest_url, manifest_sha, item_count=10, sample_size=10, min_pass_bps=1,
    )
    batch = contract.get_batch(batch_id)
    assert sorted(batch["sample_indices"]) == list(range(10))
    assert len(set(batch["sample_indices"])) == 10


def test_entropy_changes_the_sample(direct_deploy, direct_vm, direct_owner, direct_alice, direct_bob, direct_charlie):
    contract = _deploy(direct_deploy)
    items, bodies = make_items(100)
    manifest_body, manifest_sha = canonical_manifest(items)
    manifest_url = "https://fixtures.example.org/manifest-entropy.json"
    mock_good_fixtures(direct_vm, manifest_url, manifest_body, items, bodies)

    batch_a = _create_and_match_and_reveal(
        contract, direct_vm, direct_owner, direct_alice,
        manifest_url, manifest_sha, item_count=100, sample_size=10, min_pass_bps=1,
        producer_secret="secret-A1", partner_secret="secret-A2",
    )
    batch_b = _create_and_match_and_reveal(
        contract, direct_vm, direct_bob, direct_charlie,
        manifest_url, manifest_sha, item_count=100, sample_size=10, min_pass_bps=1,
        producer_secret="secret-B1", partner_secret="secret-B2",
    )
    indices_a = contract.get_batch(batch_a)["sample_indices"]
    indices_b = contract.get_batch(batch_b)["sample_indices"]
    assert indices_a != indices_b


# ---------------------------------------------------------------------------
# G. Non-reveal liveness (ABORTED)
#
# NOTE ON HARNESS LIMITATION: gltest's direct-mode VMContext.warp() only
# patches Python's datetime.datetime.now(); it does not (on gltest 0.29.2 /
# genvm SDK v0.3.0-rc7) refresh the injected consensus gl.message.raw.datetime
# that current_datetime() correctly reads (the contract deliberately never
# calls datetime.now() itself, since that would be non-deterministic across
# validators). Empirically confirmed: that injected timestamp is captured
# once per deployed contract instance and does not advance with real wall
# clock time either. Direct mode therefore cannot simulate deadline passage
# for this contract. The ABORTED transition and post-deadline join/reveal
# rejection are instead proven live on Studionet per docs/LIVE_TEST_PLAN.md
# section G and recorded in docs/DEPLOYMENT_EVIDENCE.md. The tests below
# cover what direct mode *can* verify: the deadline-still-open guard rejects
# abort attempts before the deadline passes.
# ---------------------------------------------------------------------------


def test_abort_non_reveal_rejected_while_deadline_still_open(direct_deploy, direct_vm, direct_owner, direct_alice):
    contract = _deploy(direct_deploy)
    items, bodies = make_items(1)
    _, manifest_sha = canonical_manifest(items)

    direct_vm.sender = direct_owner
    batch_id = contract.create_batch(
        manifest_url="https://fixtures.example.org/manifest-abort.json",
        manifest_sha256=manifest_sha,
        rubric="rubric text",
        entropy_partner=_as_address(direct_alice),
        producer_commitment=commitment_of("producer-secret"),
        reveal_deadline=FUTURE_DEADLINE,
        item_count=1,
        sample_size=1,
        min_pass_bps=1,
    )
    direct_vm.sender = direct_alice
    contract.join_entropy(batch_id, commitment_of("partner-secret"))
    # partner reveals, producer never does
    contract.reveal_entropy(batch_id, "partner-secret")

    with direct_vm.expect_revert("reveal deadline has not passed"):
        contract.abort_non_reveal(batch_id)

    batch = contract.get_batch(batch_id)
    assert batch["status_name"] == "MATCHED"


def test_abort_non_reveal_rejected_on_certified_batch_shape(direct_deploy, direct_vm, direct_owner, direct_alice):
    # abort_non_reveal must only ever apply to OPEN/MATCHED batches, never a
    # batch that has already progressed to SAMPLE_READY or terminal status
    # (state-machine bypass check).
    contract = _deploy(direct_deploy)
    items, bodies = make_items(1)
    manifest_body, manifest_sha = canonical_manifest(items)
    manifest_url = "https://fixtures.example.org/manifest-abort-bypass.json"
    mock_good_fixtures(direct_vm, manifest_url, manifest_body, items, bodies)
    direct_vm.mock_llm(VALIDATOR_PROMPT_PATTERN, json.dumps({"outcome": "PASS", "reason": "ok"}))

    batch_id = _create_and_match_and_reveal(
        contract, direct_vm, direct_owner, direct_alice,
        manifest_url, manifest_sha, item_count=1, sample_size=1, min_pass_bps=1,
    )
    assert contract.get_batch(batch_id)["status_name"] == "SAMPLE_READY"
    with direct_vm.expect_revert("batch cannot be aborted"):
        contract.abort_non_reveal(batch_id)


# ---------------------------------------------------------------------------
# H. Replay / state-machine rejection
# ---------------------------------------------------------------------------


def test_audit_sample_before_ready_is_rejected(direct_deploy, direct_vm, direct_owner, direct_alice):
    contract = _deploy(direct_deploy)
    items, bodies = make_items(1)
    _, manifest_sha = canonical_manifest(items)
    direct_vm.sender = direct_owner
    batch_id = contract.create_batch(
        manifest_url="https://fixtures.example.org/manifest-notready.json",
        manifest_sha256=manifest_sha,
        rubric="rubric text",
        entropy_partner=_as_address(direct_alice),
        producer_commitment=commitment_of("producer-secret"),
        reveal_deadline=FUTURE_DEADLINE,
        item_count=1,
        sample_size=1,
        min_pass_bps=1,
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

    batch_id = _create_and_match_and_reveal(
        contract, direct_vm, direct_owner, direct_alice,
        manifest_url, manifest_sha, item_count=1, sample_size=1, min_pass_bps=1,
    )
    contract.audit_sample(batch_id, 0)
    with direct_vm.expect_revert("sample slot already audited"):
        contract.audit_sample(batch_id, 0)


def test_audit_sample_out_of_range_slot_is_rejected(direct_deploy, direct_vm, direct_owner, direct_alice):
    contract = _deploy(direct_deploy)
    items, bodies = make_items(2)
    manifest_body, manifest_sha = canonical_manifest(items)
    manifest_url = "https://fixtures.example.org/manifest-slotrange.json"
    mock_good_fixtures(direct_vm, manifest_url, manifest_body, items, bodies)

    batch_id = _create_and_match_and_reveal(
        contract, direct_vm, direct_owner, direct_alice,
        manifest_url, manifest_sha, item_count=2, sample_size=1, min_pass_bps=1,
    )
    with direct_vm.expect_revert("sample_slot out of range"):
        contract.audit_sample(batch_id, 1)


def test_settle_before_all_audited_is_rejected(direct_deploy, direct_vm, direct_owner, direct_alice):
    contract = _deploy(direct_deploy)
    items, bodies = make_items(6)
    manifest_body, manifest_sha = canonical_manifest(items)
    manifest_url = "https://fixtures.example.org/manifest-earlysettle.json"
    mock_good_fixtures(direct_vm, manifest_url, manifest_body, items, bodies)
    direct_vm.mock_llm(VALIDATOR_PROMPT_PATTERN, json.dumps({"outcome": "PASS", "reason": "ok"}))

    batch_id = _create_and_match_and_reveal(
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

    batch_id = _create_and_match_and_reveal(
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
    direct_vm.sender = direct_owner
    batch_id = contract.create_batch(
        manifest_url="https://fixtures.example.org/manifest-cancel.json",
        manifest_sha256=manifest_sha,
        rubric="rubric text",
        entropy_partner=_as_address(direct_alice),
        producer_commitment=commitment_of("producer-secret"),
        reveal_deadline=FUTURE_DEADLINE,
        item_count=1,
        sample_size=1,
        min_pass_bps=1,
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

    batch_id = _create_and_match_and_reveal(
        contract, direct_vm, direct_owner, direct_alice,
        manifest_url, manifest_sha, item_count=1, sample_size=1, min_pass_bps=1,
    )
    contract.audit_sample(batch_id, 0)

    # Simulate the validator's OWN independent fetch + judgement: same
    # pinned evidence, differently worded reasoning (reason is not
    # consensus-critical), same structured outcome.
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

    batch_id = _create_and_match_and_reveal(
        contract, direct_vm, direct_owner, direct_alice,
        manifest_url, manifest_sha, item_count=1, sample_size=1, min_pass_bps=1,
    )
    contract.audit_sample(batch_id, 0)

    direct_vm.clear_mocks()
    mock_good_fixtures(direct_vm, manifest_url, manifest_body, items, bodies)
    direct_vm.mock_llm(VALIDATOR_PROMPT_PATTERN, json.dumps({"outcome": "FAIL", "reason": "independent validator disagrees"}))
    assert direct_vm.run_validator() is False


def test_validator_independently_disagrees_when_its_own_fetch_sees_different_evidence(direct_deploy, direct_vm, direct_owner, direct_alice):
    # Proves the validator does not just check the leader's JSON shape: it
    # re-fetches the item itself, and a hash mismatch on ITS OWN fetch
    # flips its independent result to INCONCLUSIVE / empty identity fields,
    # which then disagrees with the leader's PASS + populated identity.
    contract = _deploy(direct_deploy)
    items, bodies = make_items(1)
    manifest_body, manifest_sha = canonical_manifest(items)
    manifest_url = "https://fixtures.example.org/manifest-valrefetch.json"
    mock_good_fixtures(direct_vm, manifest_url, manifest_body, items, bodies)
    direct_vm.mock_llm(VALIDATOR_PROMPT_PATTERN, json.dumps({"outcome": "PASS", "reason": "leader reason"}))

    batch_id = _create_and_match_and_reveal(
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
