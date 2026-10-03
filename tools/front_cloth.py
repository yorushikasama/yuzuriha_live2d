"""Bind the two FRONT ribbons (ArtMeshTopwear / ArtMeshTopwear2).

Diagnosis (2026-10-03): the user reported only the back ribbon swaying while
"the two in front" stayed rigid. Measured by isolating each drawable:

  ArtMeshHandwearL / R  -> one ribbon each, long, already on AgentClothL/R1-3
  ArtMeshTopwear        -> front-left ribbon, hangs on DeformBodyZBreath (rigid)
  ArtMeshTopwear2       -> front-right ribbon, hangs on DeformBodyZBreath (rigid)
  ArtMeshTopwear3       -> the central dress body, must stay rigid

So the two front ribbons simply were never in any deform chain. This builds the
same three-segment nested warp chain for each, driven by the SAME cloth params
so all four ribbons move together.

1.3.0 rules this script depends on (learned the hard way):
  * `canvas warp` must NOT be given an explicit `bounds`; that collapses the
    target meshes. Use `add_to: parent_of_selected` with no bounds.
  * `deform` coordinates are NORMALIZED 0..1 of the target's own bounds for
    warp targets (canvas pixels only for mesh targets).
  * a deform key must list EVERY axis the object is directly bound to; the
    axes accumulate down the chain, so later segments carry all earlier ones.
"""
import sys, json
sys.path.insert(0, "tools")
from psd2live_mcp import Mcp

# id, mesh, name prefix
TARGETS = [
    ("T1", "ArtMeshTopwear",  "DeformClothT1"),
    ("T2", "ArtMeshTopwear2", "DeformClothT2"),
]

# seg, param, degrees, root_frac_y, tip_frac_y
# The front ribbons are short and hang from the chest, so they bend lower
# (deeper root) and less than the long back streamers.
SEGS = [
    (1, "ParamClothSway",  6.0, 0.34, 0.86),
    (2, "ParamClothSway2", 9.0, 0.55, 0.94),
    (3, "ParamClothSway3", 12.0, 0.70, 1.00),
]

BODY = {"ParamBodyAngleX": 0.0, "ParamBodyAngleZ": 0.0}


def sc(r):
    return (r or {}).get("result", {}).get("structuredContent")


def need(r, label):
    res = (r or {}).get("result", {})
    if res.get("isError"):
        txt = " ".join((c.get("text") or "") for c in res.get("content", []))
        raise SystemExit(f"{label} FAILED: {txt[:500]}")
    st = res.get("structuredContent", {}).get("state")
    print(f"  ok {label} -> {st}")
    return st


def proj_state(m):
    return sc(m.call("inspect", {"scope": "project"}))["state"]


def all_objects(m, query="warp"):
    """inspect scope=objects paginates 24 per page via an `offset` cursor, and an
    EMPTY query returns meshes only -- a single un-paged call silently misses every
    warp. Walk all pages."""
    out, off = [], 0
    while True:
        s_ = sc(m.call("inspect", {"scope": "objects", "query": query, "offset": off}))
        items = s_.get("items") or []
        out.extend(items)
        nxt = s_.get("next")
        if not items or nxt is None or nxt == off:
            break
        off = nxt
    return out


def existing(m):
    return {it.get("target") for it in all_objects(m) if it.get("target")}


def build():
    m = Mcp(); m.initialize()
    st = proj_state(m)
    present = existing(m)

    for tag, mesh, name in TARGETS:
        for seg, _param, _deg, _rf, _tf in SEGS:
            wid = f"AgentCloth{tag}{seg}"
            if "warp:" + wid in present:
                print(f"  = warp {wid} exists")
                continue
            st = need(m.call("canvas", {"request": {
                "mode": "warp", "id": wid, "state": st, "name": name + str(seg),
                "meshes": [mesh], "add_to": "parent_of_selected",
                "size_strategy": "selection_bounds",
                "rows": 6, "columns": 3}}), f"warp {wid}")
            present = existing(m)

        # arc keyforms, cumulative key axes
        bound = dict(BODY)
        for seg, param, deg, rf, tf in SEGS:
            wid = f"AgentCloth{tag}{seg}"
            for sign in (1.0, -1.0):
                key = dict(bound); key[param] = sign
                st = need(m.call("deform", {"state": st, "changes": [{
                    "target": "warp:" + wid,
                    "key": key,
                    "operations": [{"type": "arc", "degrees": deg * sign,
                                    "root": [0.5, rf], "tip": [0.5, tf],
                                    "root_pin": 0.05}]}]}), f"{wid} {param}{sign:+g}")
            bound[param] = 0.0

    print("done. now run: python tools/export.py")


if __name__ == "__main__":
    build()
