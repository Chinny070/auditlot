# Security model

## Protected properties

AuditLot is designed to protect the following properties:

1. **No post-sample batch substitution.** The manifest and sampled item bodies are SHA-256 pinned.
2. **No unilateral sample selection.** Sampling requires two precommitted secrets.
3. **No duplicate sample slots.** Deterministic selection yields unique indexes.
4. **No leader-only semantic verdict.** Validators independently refetch the evidence and independently reproduce the outcome.
5. **No silent uncertainty.** Evidence failure, hash mismatch, malformed manifest, non-UTF-8 content, or unparsable semantic judgement becomes `INCONCLUSIVE`.
6. **No LLM-controlled final batch status.** Threshold arithmetic and terminal transitions are deterministic.

## Trust assumptions

### At least one honest entropy contributor

If producer and entropy partner collude, they can search over secret pairs before creating the commitments. V1 therefore makes the guarantee explicitly conditional: the sample is unpredictable to an adversary that does not know at least one committed secret.

### Public immutable hosting

The contract expects the manifest and item URLs to remain retrievable with exactly the pinned bytes during the audit. Content-addressed or immutable hosting is strongly preferred.

### Rubric quality

AuditLot proves performance against the rubric the producer froze. A weak or self-serving rubric yields a weak certificate. Consumers must inspect or pin an acceptable rubric hash.

### Statistical scope

Sampling reduces cost; it does not inspect unsampled items. AuditLot deliberately does not claim a statistical confidence interval because that depends on the user's sampling assumptions, batch construction, and acceptable defect model.

## Prompt injection

Sampled item text is explicitly labelled hostile data in the validator prompt. The prompt instructs the model not to follow commands contained in the item. More importantly, a single leader cannot release an outcome alone: validators independently fetch and judge the same pinned item.

This reduces but does not mathematically eliminate model-level prompt-injection risk. High-stakes consumers should use clear, bounded rubrics and conservative thresholds.

## Failure modes

| Failure | Result |
|---|---|
| manifest URL unavailable | sampled audit becomes `INCONCLUSIVE` |
| manifest body changed | `INCONCLUSIVE` |
| sampled item unavailable | `INCONCLUSIVE` |
| sampled item body changed | `INCONCLUSIVE` |
| malformed manifest | `INCONCLUSIVE` |
| validator semantic disagreement | consensus does not finalize that audit call |
| one entropy participant never reveals | batch can be marked `ABORTED` after deadline |
| sampled defect rate exceeds threshold | `REJECTED` |
| any sample is unresolved/inconclusive | batch `INCONCLUSIVE` |

## Non-goals

AuditLot does not verify legal ownership, exhaustive completeness of a real-world batch, authorship, licence rights, or hidden off-chain facts. It is a blind sampling and semantic certification primitive, not a universal truth oracle.
