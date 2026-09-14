import hashlib
import unittest


def commitment(secret: str) -> str:
    return hashlib.sha256(("AUDITLOT_V1|" + secret).encode()).hexdigest()


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
    def test_commitment_domain_separation(self):
        self.assertEqual(commitment('abc'), hashlib.sha256(b'AUDITLOT_V1|abc').hexdigest())

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


if __name__ == '__main__':
    unittest.main()
