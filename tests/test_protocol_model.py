import hashlib
import unittest


def commitment(secret: str, assessment_id: str, role: str) -> str:
    return hashlib.sha256(
        ("AUDITLOT_COMMIT_V2|" + assessment_id + "|" + role + "|" + secret).encode()
    ).hexdigest()


def assessment_id(chain_id: int, contract_address: str, manifest_sha256: str, rubric_sha256: str) -> str:
    return hashlib.sha256(
        (
            "AUDITLOT_ASSESSMENT_V2|"
            + str(chain_id)
            + "|"
            + contract_address
            + "|"
            + manifest_sha256
            + "|"
            + rubric_sha256
        ).encode()
    ).hexdigest()


def sample(seed: str, n: int, k: int):
    out=[]; counter=0; modulus=1<<256; limit=modulus-(modulus % n)
    while len(out)<k:
        x=int.from_bytes(hashlib.sha256(f"AUDITLOT_SAMPLE_V1|{seed}|{counter}".encode()).digest(),'big')
        counter+=1
        if x>=limit: continue
        i=x % n
        if i not in out: out.append(i)
    return out


def settle(pass_count, fail_count, inconclusive_count, sample_size, threshold):
    if inconclusive_count:
        return 'INCONCLUSIVE'
    return 'CERTIFIED' if (pass_count*10000)//sample_size >= threshold else 'REJECTED'


class ProtocolModelTests(unittest.TestCase):
    def test_commitment_domain_separation_by_role(self):
        aid = assessment_id(61999, "0xabc", "m" * 64, "r" * 64)
        self.assertNotEqual(
            commitment("s", aid, "producer"),
            commitment("s", aid, "partner"),
        )

    def test_commitment_domain_separation_by_assessment(self):
        aid_a = assessment_id(61999, "0xabc", "m" * 64, "r" * 64)
        aid_b = assessment_id(61999, "0xabc", "n" * 64, "r" * 64)
        self.assertNotEqual(
            commitment("s", aid_a, "producer"),
            commitment("s", aid_b, "producer"),
        )

    def test_assessment_id_domain_separation_by_chain_and_contract(self):
        base = assessment_id(61999, "0xabc", "m" * 64, "r" * 64)
        other_chain = assessment_id(1337, "0xabc", "m" * 64, "r" * 64)
        other_contract = assessment_id(61999, "0xdef", "m" * 64, "r" * 64)
        self.assertNotEqual(base, other_chain)
        self.assertNotEqual(base, other_contract)

    def test_sample_is_deterministic_and_unique(self):
        seed='a'*64
        a=sample(seed,100,25); b=sample(seed,100,25)
        self.assertEqual(a,b)
        self.assertEqual(len(a),25)
        self.assertEqual(len(set(a)),25)
        self.assertTrue(all(0<=x<100 for x in a))

    def test_full_sample_is_permutation(self):
        values=sample('b'*64,10,10)
        self.assertEqual(set(values),set(range(10)))

    def test_entropy_changes_sample(self):
        self.assertNotEqual(sample('a'*64,100,10), sample('c'*64,100,10))

    def test_inconclusive_fails_closed(self):
        self.assertEqual(settle(9,0,1,10,9000),'INCONCLUSIVE')

    def test_threshold_boundary(self):
        self.assertEqual(settle(9,1,0,10,9000),'CERTIFIED')
        self.assertEqual(settle(8,2,0,10,9000),'REJECTED')

    def test_last_revealer_can_precompute_outcome_before_choosing_to_reveal(self):
        """Model of the residual last-revealer preview: this is the attack
        AuditLot v2 bounds and prices (bond forfeiture + a capped number of
        retries per assessment) rather than eliminates outright, because no
        randomness beacon is available to contracts on this platform. This
        test documents, rather than hides, that the preview is possible in
        principle: whichever party reveals second can compute the sample
        privately before deciding whether to submit its own reveal."""
        aid = assessment_id(61999, "0xabc", "m" * 64, "r" * 64)
        batch_id = 7
        producer_secret = "producer-secret"
        partner_secret_good = "partner-secret-good"
        partner_secret_bad = "partner-secret-bad"

        def seed_of(partner_secret: str) -> str:
            return hashlib.sha256(
                (
                    "AUDITLOT_SEED_V2|" + aid + "|" + str(batch_id) + "|" + producer_secret + "|" + partner_secret
                ).encode()
            ).hexdigest()

        # The producer reveals first (public). The entropy partner, knowing
        # its own two candidate secrets, can compute both possible resulting
        # samples *before* deciding which reveal transaction (if any) to
        # submit -- demonstrating the preview is real, not merely theoretical.
        sample_good = sample(seed_of(partner_secret_good), 6, 3)
        sample_bad = sample(seed_of(partner_secret_bad), 6, 3)
        self.assertNotEqual(sample_good, sample_bad)
        # A partner who computed both in advance and disliked one of them
        # would simply never reveal that one -- which is exactly the
        # behavior AuditLot v2 prices via bond forfeiture and caps via
        # MAX_ABORTS_PER_ASSESSMENT rather than pretending is impossible.


if __name__ == '__main__':
    unittest.main()
