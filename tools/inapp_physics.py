"""Author the cloth pendulums INSIDE the PSD2Live project (app-preview parity).

Why: the silky multi-node wave that ships on the web is authored post-export by
patch_cloth_physics.py -- it never existed inside the app, so the app preview
showed dead-still ribbons while the webpage swayed ("项目不一致").

The 1.3.0 MCP physics tool can only express a SINGLE input->output pendulum
(put rejects inputs/outputs/vertices/weights/normalization -- probed), so the
in-app rig is the older three-graduated-pendulum design: same three output
parameters, same dominant input (ParamBodyAngleX), graduated length/delay so
the wave still travels.  It is a close preview approximation, not bit-identical
to the shipped dynamics.

IDs are "PhysicsClothPreview*" ON PURPOSE: patch_cloth_physics.py strips every
"PhysicsCloth*" group from the exported physics3.json before writing the
canonical multi-node one, so these preview groups never reach the web build and
the shipped effect stays exactly as tuned.

Idempotent: existing groups with these ids are replaced via put semantics.
"""
import sys, json
sys.path.insert(0, "tools")
from psd2live_mcp import Mcp

# id, name, output, length, mobility, delay, acceleration, output_scale
# Tuning is the visually-validated v1 set (docs ch.11 history).
GROUPS = [
    ("PhysicsClothPreview1", "飘带摆动(预览1)", "ParamClothSway",  6.0, 0.94, 1.00, 1.1, 2.6),
    ("PhysicsClothPreview2", "飘带摆动(预览2)", "ParamClothSway2", 11.0, 0.93, 0.85, 1.3, 3.0),
    ("PhysicsClothPreview3", "飘带摆动(预览3)", "ParamClothSway3", 16.0, 0.90, 0.70, 1.5, 3.4),
]
INPUT = "ParamBodyAngleX"


def sc(r):
    return (r or {}).get("result", {}).get("structuredContent")


def main():
    m = Mcp(); m.initialize()
    st = sc(m.call("inspect", {"scope": "project"}))["state"]
    for gid, name, out, length, mob, delay, acc, scale in GROUPS:
        r = m.call("physics", {"request": {
            "mode": "put", "id": gid, "name": name, "state": st,
            "input_parameter": INPUT, "output_parameter": out,
            "length": length, "mobility": mob, "delay": delay,
            "acceleration": acc, "output_scale": scale}})
        res = (r or {}).get("result", {})
        if res.get("isError"):
            txt = " ".join((c.get("text") or "") for c in res.get("content", []))
            raise SystemExit(f"{gid} FAILED: {txt[:300]}")
        st = res["structuredContent"]["state"]
        print(f"  ok {gid}: {INPUT} -> {out}  len={length} delay={delay} scale={scale}")
    s = sc(m.call("inspect", {"scope": "physics"}))
    print("app physics groups now:", [g["id"] for g in s.get("groups", [])])
    print("done. run: python tools/export.py")


if __name__ == "__main__":
    main()
