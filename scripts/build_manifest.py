#!/usr/bin/env python3
"""Build canonical AuditLot manifest JSON from a simple input file.

Input JSON: [{"id":"x","url":"https://...","file":"local/path.txt"}, ...]
The helper hashes each local file's exact bytes and emits a canonical manifest.
"""
import hashlib, json, pathlib, sys

if len(sys.argv) != 3:
    raise SystemExit("usage: build_manifest.py <input.json> <manifest.json>")
source = json.loads(pathlib.Path(sys.argv[1]).read_text())
items=[]
for row in source:
    data=pathlib.Path(row["file"]).read_bytes()
    items.append({
        "id": str(row["id"]),
        "url": str(row["url"]),
        "sha256": hashlib.sha256(data).hexdigest(),
    })
manifest={"version":"auditlot-1","items":items}
raw=json.dumps(manifest, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")
pathlib.Path(sys.argv[2]).write_bytes(raw)
print("item_count:", len(items))
print("manifest_sha256:", hashlib.sha256(raw).hexdigest())
