#!/usr/bin/env python3
"""Compute an AuditLot v2 entropy commitment.

v2 commitments are bound to the assessment identity (which itself binds
chain id, contract address, manifest_sha256, and rubric_sha256) and to the
caller's participant role, so a commitment cannot be replayed across
contracts, chains, assessments, or roles. Get the assessment_id for your
(manifest_sha256, rubric_sha256) pair by calling the deployed contract's
assessment_id_for view method -- do not hand-roll the hash yourself, since
that risks silently drifting from the contract's own formula.

Usage:
    genlayer call <contract> assessment_id_for --args <manifest_sha256> <rubric_sha256>
    python scripts/commit.py <assessment_id> <producer|partner> [secret]
"""
import hashlib
import secrets
import sys

if len(sys.argv) not in (3, 4):
    raise SystemExit(
        "usage: commit.py <assessment_id> <producer|partner> [secret]\n"
        "  assessment_id: from `genlayer call <contract> assessment_id_for --args <manifest_sha256> <rubric_sha256>`\n"
        "  role: 'producer' or 'partner'"
    )

assessment_id = sys.argv[1]
role = sys.argv[2]
if role not in ("producer", "partner"):
    raise SystemExit("role must be exactly 'producer' or 'partner'")
if len(assessment_id) != 64 or any(c not in "0123456789abcdef" for c in assessment_id.lower()):
    raise SystemExit("assessment_id must be a 64-char lowercase sha256 hex digest")

secret = sys.argv[3] if len(sys.argv) == 4 else secrets.token_urlsafe(32)
commitment = hashlib.sha256(
    ("AUDITLOT_COMMIT_V2|" + assessment_id + "|" + role + "|" + secret).encode()
).hexdigest()
print("assessment_id:", assessment_id)
print("role:", role)
print("secret:", secret)
print("commitment:", commitment)
