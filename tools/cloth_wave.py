"""Ribbon (handwear streamer) wave rig -- rebuild after an app restart.

Rebuilds the multi-segment ribbon chain that makes the arm streamers travel in a
lagging wave instead of swinging as one rigid arc.

Hard-won rules (2026-10-03):
  * `deform` root/tip are NORMALIZED fractions of the target's own bounds for a
    WARP target (canvas pixels only for a mesh target). Passing canvas pixels to
    a warp is a silent no-op: the bend lands off the unit domain.
  * A key must list EVERY axis the object is directly bound to. Axes accumulate
    down the chain, so each later key carries all earlier ones.
  * Do NOT pass an explicit `bounds` to canvas warp for these meshes -- the
    exporter then reports them collapsed and millions of px off canvas.
    `add_to: parent_of_selected` without bounds builds the chain cleanly.

Layout per side: DeformPair_Handwear -> L1 -> L2 -> L3 -> mesh, each segment
bending a deeper span on its own parameter, giving a phase-graduated wave.

Physics is not authored here: the pendulum that drives the three parameters lives
in tools/patch_cloth_physics.py and is re-applied by tools/export.py on every
export (run that first, then this, then export again).

Usage: python tools/cloth_wave.py
"""
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "..", "tools"))
from psd2live_mcp import Mcp  # noqa: E402

MESH = {"L": "ArtMeshHandwearL", "R": "ArtMeshHandwearR"}
SEGS = [  # seg, param, degrees, root_frac, tip_frac  (fractions of warp height)
    (1, "ParamClothSway",  7.0, 0.18, 0.94),
    (2, "ParamClothSway2", 11.0, 0.42, 1.00),
    (3, "ParamClothSway3", 15.0, 0.62, 1.00),
]
PARAMS = ["ParamClothSway", "ParamClothSway2", "ParamClothSway3"]
BODY = {"ParamBodyAngleX": 0.0, "ParamBodyAngleZ": 0.0}

STATE_TOP = {"deform", "form", "settings", "layer", "layer_mesh", "appearance",
             "structure", "rig", "export", "export_psd", "preview"}
STATE_IN_REQUEST = {"paint", "parameter", "asset", "path", "physics", "canvas"}

state = None
m = Mcp()
m.initialize()


def call(tool, args):
    global state
    args = dict(args)
    if tool in STATE_IN_REQUEST:
        req = dict(args.get("request") or {})
        req.setdefault("state", state)
        args["request"] = req
    elif tool in STATE_TOP:
        args.setdefault("state", state)
    r = m.call(tool, args)
    res = (r or {}).get("result", {}) or {}
    sc = res.get("structuredContent")
    if sc is None:
        for c in res.get("content") or []:
            if c.get("type") == "text":
                try:
                    sc = json.loads(c["text"])
                except Exception:
                    sc = {"text": c["text"]}
    if isinstance(sc, dict) and sc.get("state"):
        state = sc["state"]
    if res.get("isError") or (isinstance(sc, dict) and sc.get("error")):
        print("  !!", json.dumps(sc, ensure_ascii=False)[:200])
    return sc


def all_objects(query="warp"):
    """inspect scope=objects paginates 24 per page via an `offset` cursor, and an
    EMPTY query returns meshes only -- so a single un-paged call silently misses
    every warp in the rig. Walk all pages."""
    out, off = [], 0
    while True:
        r = call("inspect", {"scope": "objects", "query": query, "offset": off})
        items = r.get("items") or []
        out.extend(items)
        nxt = r.get("next")
        if not items or nxt is None or nxt == off:
            break
        off = nxt
    return out


def existing_params():
    """Parameter ids already declared (the inspect scope uses `id`, not `parameter_id`)."""
    r = call("inspect", {"scope": "parameters"})
    out = set()
    for it in (r.get("items") or r.get("parameters") or []):
        for k in ("id", "parameter_id", "Id", "ParameterId"):
            if it.get(k):
                out.add(it[k])
    return out


def existing_targets():
    """All object targets currently in the project, e.g. {"warp:AgentClothL1", ...}."""
    return {it.get("target") for it in all_objects() if it.get("target")}


def main():
    global state
    state = call("inspect", {"scope": "project"})["state"]
    print("state", state)

    present = existing_targets()
    have_params = existing_params()

    # Re-running this script must be a no-op, not an error spew. Anything the
    # workspace already has is skipped; only genuinely missing pieces are built.
    for i, pid in enumerate(PARAMS):
        if pid in have_params:
            print(f"  = param {pid} exists")
            continue
        call("parameter", {"request": {
            "mode": "create", "parameter_id": pid,
            "name": "飘带摆动" if i == 0 else f"飘带摆动{i+1}",
            "min": -1, "max": 1, "default": 0}})
        print(f"  + param {pid} created")
        have_params.add(pid)
    present = existing_targets()

    for side in ("L", "R"):
        bound = dict(BODY)
        for seg, param, deg, rf, tf in SEGS:
            wid = f"AgentCloth{side}{seg}"
            tgt = "warp:" + wid
            if tgt not in present:
                # NOTE: no explicit "state" here -- call() injects the live one.
                call("canvas", {"request": {
                    "mode": "warp", "id": wid,
                    "name": f"DeformCloth{side}{seg}", "meshes": [MESH[side]],
                    "add_to": "parent_of_selected",
                    "size_strategy": "selection_bounds", "rows": 6, "columns": 3}})
                print(f"  + warp {wid}")
            else:
                print(f"  = warp {wid} exists")
            for sign in (1.0, -1.0):
                key = dict(bound)
                key[param] = sign
                call("deform", {"changes": [{
                    "target": tgt, "key": key,
                    "operations": [{"type": "arc", "degrees": deg * sign,
                                    "root": [0.5, rf], "tip": [0.5, tf],
                                    "root_pin": 0.05}]}]})
            bound[param] = 0.0
            print(f"  {side}{seg} arc +-{deg}deg on {param} (normalized)")
        print(f"  {side} chain complete")

    with open(os.path.join(HERE, "state.txt"), "w", encoding="utf-8") as f:
        f.write(state or "")
    print("final", state)


if __name__ == "__main__":
    main()
