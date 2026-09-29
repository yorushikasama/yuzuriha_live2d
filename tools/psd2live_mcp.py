r"""MCP client for the running PSD2Live instance.

PSD2Live serves a Streamable HTTP MCP endpoint on http://127.0.0.1:23871/mcp,
authenticated with a bearer token it keeps in Java Preferences
(HKCU\Software\JavaSoft\Prefs\io\github\psd2live\agent).  Java escapes '/'
in preference values, so the raw registry string is unescaped before use --
otherwise every token lookup 401s.

Usage:
    python psd2live_mcp.py tools
    python psd2live_mcp.py call <tool> '<json-args>'
"""
from __future__ import annotations

import json
import sys
import urllib.error
import urllib.request
import winreg

ENDPOINT = "http://127.0.0.1:23871/mcp"
PREFS_KEY = r"Software\JavaSoft\Prefs\io\github\psd2live\agent"
TOKEN_VALUE = "agent_mcp_bearer_token"


def decode_java_pref(value: str) -> str:
    """Undo the '/' escaping Java Preferences applies on Windows."""
    out, i = [], 0
    while i < len(value):
        if value[i] == "/" and i + 1 < len(value):
            i += 1
            out.append("/" if value[i] == "/" else value[i].upper())
        else:
            out.append(value[i])
        i += 1
    return "".join(out)


def token() -> str:
    with winreg.OpenKey(winreg.HKEY_CURRENT_USER, PREFS_KEY) as k:
        v, _ = winreg.QueryValueEx(k, TOKEN_VALUE)
    return decode_java_pref(v)


class Mcp:
    def __init__(self):
        self.tok = token()
        self.sid = None
        self.proto = None

    def _post(self, payload, notify=False):
        headers = {
            "Accept": "application/json, text/event-stream",
            "Authorization": f"Bearer {self.tok}",
            "Content-Type": "application/json",
        }
        if self.sid:
            headers["Mcp-Session-Id"] = self.sid
        if self.proto:
            headers["MCP-Protocol-Version"] = self.proto
        req = urllib.request.Request(ENDPOINT, data=json.dumps(payload).encode(),
                                     headers=headers, method="POST")
        try:
            with urllib.request.urlopen(req, timeout=120) as r:
                sid = r.headers.get("Mcp-Session-Id")
                if sid:
                    self.sid = sid
                body = r.read().decode()
                ctype = r.headers.get("Content-Type", "")
        except urllib.error.HTTPError as e:
            return {"_http_error": e.code, "_body": e.read().decode()[:400]}
        if notify or not body.strip():
            return None
        return self._parse(body, ctype)

    @staticmethod
    def _parse(body, ctype):
        if "text/event-stream" in ctype.lower():
            out = []
            for line in body.splitlines():
                if line.startswith("data:"):
                    chunk = line[5:].strip()
                    if chunk:
                        out.append(json.loads(chunk))
            return out[-1] if out else None
        return json.loads(body)

    def rpc(self, method, params=None, rid=1):
        return self._post({"jsonrpc": "2.0", "id": rid, "method": method,
                           "params": params or {}})

    def initialize(self):
        r = self.rpc("initialize", {
            "protocolVersion": "2024-11-05",
            "capabilities": {},
            "clientInfo": {"name": "zc-psd2live", "version": "1.0"},
        })
        if isinstance(r, dict) and "result" in r:
            self.proto = r["result"].get("protocolVersion", "2024-11-05")
        self._post({"jsonrpc": "2.0", "method": "notifications/initialized"}, notify=True)
        return r

    def tools(self):
        r = self.rpc("tools/list", {}, rid=2)
        return (r or {}).get("result", {}).get("tools", [])

    def call(self, name, args=None, rid=3):
        return self.rpc("tools/call", {"name": name, "arguments": args or {}}, rid=rid)


if __name__ == "__main__":
    m = Mcp()
    init = m.initialize()
    if not isinstance(init, dict) or "result" not in init:
        print("initialize failed:", json.dumps(init, ensure_ascii=False)[:400])
        sys.exit(1)
    info = init["result"].get("serverInfo", {})
    print(f"connected: {info.get('name')} {info.get('version')}", file=sys.stderr)
    cmd = sys.argv[1] if len(sys.argv) > 1 else "tools"
    if cmd == "tools":
        for t in m.tools():
            print(f"\n### {t['name']}")
            desc = (t.get("description") or "").strip().splitlines()
            for line in desc[:4]:
                print("   ", line)
    elif cmd == "call":
        # Emit only the tool's structured payload so callers can pipe the output.
        # Args may be given as "@file.json": a shell here eats the backslashes in
        # Windows paths, but a file passes them through intact.
        raw = sys.argv[3] if len(sys.argv) > 3 else "{}"
        if raw.startswith("@"):
            raw = open(raw[1:], encoding="utf-8").read()
        args = json.loads(raw)
        r = m.call(sys.argv[2], args)
        sc = (r or {}).get("result", {}).get("structuredContent")
        print(json.dumps(sc if sc is not None else r, ensure_ascii=False, indent=1))
