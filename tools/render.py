"""Render an authoritative pose sheet from PSD2Live itself.

The tool returns the image as MCP image content, not structuredContent, so the
raw JSON-RPC response has to be walked for the base64 blob.
"""
import base64
import json
import os
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
from psd2live_mcp import Mcp  # noqa: E402

# Args come from the shell, which eats the backslashes in Windows paths, so a
# request may be given as "@file.json" and read from disk instead.
_raw = sys.argv[1] if len(sys.argv) > 1 else "{}"
if _raw.startswith("@"):
    _raw = open(_raw[1:], encoding="utf-8").read()
REQ = json.loads(_raw)
OUT = sys.argv[2] if len(sys.argv) > 2 else os.path.join(HERE, "sheet.png")

m = Mcp()
m.initialize()
r = m.call("view", {"request": REQ})

res = (r or {}).get("result", {})
print("isError:", res.get("isError"), file=sys.stderr)

imgs = []
for c in res.get("content", []) or []:
    t = c.get("type")
    if t == "image":
        imgs.append(c.get("data"))
        print("image:", c.get("mimeType"), "b64len", len(c.get("data") or ""), file=sys.stderr)
    elif t == "text":
        print("text:", (c.get("text") or "")[:800], file=sys.stderr)

sc = res.get("structuredContent")
if sc is not None:
    print("structured:", json.dumps(sc, ensure_ascii=False)[:1500], file=sys.stderr)
if not imgs and not sc:
    print("raw:", json.dumps(r, ensure_ascii=False)[:1500], file=sys.stderr)

if imgs:
    with open(OUT, "wb") as f:
        f.write(base64.b64decode(imgs[0]))
    print("wrote", OUT, os.path.getsize(OUT), file=sys.stderr)
