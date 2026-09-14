# Agent handoff — finish AuditLot for Chinny070/auditlot

You are receiving a prepared AuditLot repository archive. Do not return only a plan or checklist. Work through the repository, execute the checks, fix any real contract/runtime issues you find, deploy the final contract, record evidence, and push the finished repository to `Chinny070/auditlot`.

## Non-negotiable scope

AuditLot is a **standalone GenLayer Intelligent Contract primitive**. It intentionally has **no frontend**. Do not add React, Next.js, Vite, a dashboard, landing page, wallet UI, or any other product frontend.

The only target network is **Studionet, chain ID 61999**. Keep the repository, deployment commands, evidence, and final submission on that network. Do not change the network or migrate the contract to another Studio environment.

Preserve the core primitive:

- immutable batch manifest pinned by SHA-256;
- immutable per-item SHA-256 values in the manifest;
- producer + independent entropy-partner commit/reveal;
- deterministic domain-separated sample derivation;
- unique sample indexes with rejection sampling to avoid modulo bias;
- sample selection only after both commitments are fixed;
- permissionless calls to audit each selected sample;
- validators independently refetch the exact manifest and exact selected item;
- validators independently reproduce `PASS`, `FAIL`, or `INCONCLUSIVE` against the frozen rubric;
- evidence identity/hash fields are consensus-bound;
- one inconclusive sample makes the batch terminal result inconclusive;
- final pass-rate threshold and certificate hash are deterministic;
- uncertainty is never coerced into a pass or fail.

Do not turn AuditLot into a generic AI scorer, marketplace, escrow, project dashboard, or full app.

## Work to complete

Start by reading `README.md`, `docs/ARCHITECTURE.md`, `docs/SECURITY_MODEL.md`, `docs/LIVE_TEST_PLAN.md`, `SUBMISSION.md`, and `contracts/auditlot.py` in full.

Run:

```bash
python scripts/preflight.py
python -m unittest discover -s tests -v
```

Then use the stable Studionet-compatible GenLayer tooling to run the GenVM linter and the strongest available Direct Mode/GLSim tests against the actual contract. The archive's local tests are protocol-model checks; they do not substitute for GenVM execution. Fix any real syntax, storage-type, decorator, serialization, validator, or runtime incompatibility you discover, but preserve the protocol invariants above.

Keep the stable dependency line appropriate for the 61999 target. Do not silently upgrade the contract into a different network/toolchain family just because a newer prerelease exists.

Create public immutable HTTPS fixtures for the live demo: a canonical manifest plus enough small UTF-8 text items to exercise `CERTIFIED`, `REJECTED`, and `INCONCLUSIVE`. Hash the exact hosted bytes with `scripts/build_manifest.py` or an equivalent deterministic helper. Do not use mutable test data whose response bytes can drift during validator re-fetches.

Deploy `contracts/auditlot.py` to Studionet using chain ID 61999 from Chinny's funded deployer. Do not claim deployment until the transaction is finalized and the deployed address is readable.

Execute the complete live matrix in `docs/LIVE_TEST_PLAN.md`, including commitment mismatch, unique sampling, non-reveal abort, duplicate audit rejection, early settlement rejection, a certified batch, a rejected batch, and an inconclusive hash/evidence path. Capture finalized transaction hashes and the deployed contract address in `docs/DEPLOYMENT_EVIDENCE.md`.

Inspect validator traces/logs for at least one semantic sample audit and confirm that the validator independently refetches the evidence and independently evaluates the semantic outcome rather than merely checking the leader's JSON shape. Record concise evidence of that in the deployment document.

Before pushing, run all checks again and perform a repository-wide review for secrets, generated caches, accidental environment files, dead experimental code, misleading claims, and network mistakes. Keep `.env`, private keys, seed phrases, wallet credentials, local caches, virtual environments, and node_modules out of git.

Push the final result to the existing `main` branch of `Chinny070/auditlot`. Do not create an unrelated replacement repository. If the remote gained files after this archive was produced, fetch first and integrate safely rather than force-overwriting someone else's work.

Finish by reporting only verifiable results: final commit SHA, deployed Studionet address, finalized deployment transaction, test/lint results, live lifecycle batch IDs/transactions, any remaining limitation, and the exact submission-ready description. Do not fabricate evidence or mark TODO fields complete unless the live action actually happened.
