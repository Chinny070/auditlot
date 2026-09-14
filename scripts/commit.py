#!/usr/bin/env python3
import hashlib, secrets, sys

if len(sys.argv) > 1:
    secret = sys.argv[1]
else:
    secret = secrets.token_urlsafe(32)
commitment = hashlib.sha256(("AUDITLOT_V1|" + secret).encode()).hexdigest()
print("secret:", secret)
print("commitment:", commitment)
