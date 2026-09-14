#!/usr/bin/env python3
from pathlib import Path
import ast, sys
root=Path(__file__).resolve().parents[1]
contract=root/'contracts/auditlot.py'
ast.parse(contract.read_text())
forbidden=["619"+"97", "studio"+"-dev"]
violations=[]
for p in root.rglob('*'):
    if not p.is_file() or '.git' in p.parts:
        continue
    if p.suffix.lower() in {'.zip','.png','.jpg','.jpeg','.pdf'}:
        continue
    text=p.read_text(errors='ignore')
    for token in forbidden:
        if token.lower() in text.lower():
            violations.append(f"{p.relative_to(root)} contains forbidden network token")
if violations:
    print('\n'.join(violations))
    raise SystemExit(1)
readme=(root/'README.md').read_text()
assert '61999' in readme and 'studionet' in readme.lower()
assert not (root/'frontend').exists(), 'frontend directory must not exist'
print('preflight: PASS')
print('target network: studionet / 61999')
print('frontend: intentionally absent')
