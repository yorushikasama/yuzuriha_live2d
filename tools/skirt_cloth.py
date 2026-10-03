"""Give the two SKIRT TAILS of ArtMeshTopwear3 their own cloth sway.

User report (2026-10-03): the two ribbon tails flanking the legs -- boxed in
green on their screenshot -- still did not move.  Diagnosis by solo-render
colour sampling: those tails are the LOWER HALF of ArtMeshTopwear3 (mean RGB
~211/139/107, bright orange, matching the dress), not the legwear (mean R 91,
the black stockings) and not Topwear/Topwear2 (the outer front ribbons, already
bound).  Topwear3 = bodice + split skirt: one mesh, two tails below the split.

So the chain is rooted AT THE SPLIT (~32% down the mesh bounds): everything
above stays rigid (the arc is identity above its root), only the two tails
bend.  Degrees are smaller than the free-hanging ribbons because a skirt is
shorter and must not swing across the legs.

1.3.0 rules (see front_cloth.py docstring): no explicit `bounds` on canvas warp,
warp targets take NORMALIZED coords, deform keys must list every bound axis.
Idempotent: re-running prints "=" (exists) / "+" (created), never errors.
"""
import sys, json
sys.path.insert(0, "tools")
from psd2live_mcp import Mcp

MESH = "ArtMeshTopwear3"
TARGET = ("D", MESH, "DeformClothSkirt")

# seg, param, degrees, root_frac_y, tip_frac_y
# root 0.32 == the skirt split; bodice above stays rigid.
SEGS = [
    (1, "ParamClothSway",  4.0, 0.32, 1.00),
    (2, "ParamClothSway2", 6.0, 0.55, 1.00),
    (3, "ParamClothSway3", 8.0, 0.75, 1.00),
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


def all_objects(m, query="warp"):
    """inspect scope=objects paginates 24/page via `offset`; an EMPTY query
    returns meshes only. Walk every page or half the rig is invisible."""
    out, off = [], 0
    while True:
        s = sc(m.call("inspect", {"scope": "objects", "query": query, "offset": off}))
        items = s.get("items") or []
        out.extend(items)
        nxt = s.get("next")
        if not items or nxt is None or nxt == off:
            break
        off = nxt
    return out


def build():
    m = Mcp(); m.initialize()
    st = sc(m.call("inspect", {"scope": "project"}))["state"]
    tag, mesh, name = TARGET
    present = {it.get("target") for it in all_objects(m) if it.get("target")}

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
        present = {it.get("target") for it in all_objects(m) if it.get("target")}

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
