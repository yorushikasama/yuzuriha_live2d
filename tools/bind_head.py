"""Bind the head as one rigid unit that pivots on the neck.

Measured before the fix (canvas px of drift at ParamAngleX=20):
    face +70,-39 | front hair +76,-41 | back hair -1,0 | neck 0,0
i.e. the auto-rig applied the head turn several times over, at a different gain
on each branch, and as raw translation that carried the head off the neck.

The fix is the standard Live2D arrangement: exactly one deformer carries the
head turn, and everything on the head inherits it. So every branch warp's
angle keys are folded back to neutral, then a small, plausible turn is authored
on DeformHeadContainer alone.
"""
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
from p2l import call, get_state  # noqa: E402

XS = [-45.0, 0.0, 45.0]
YS = [-30.0, 0.0, 30.0]

# warp -> the angle axes it is keyed on
BRANCHES = {
    "warp:DeformFaceNinePose": "xy",
    "warp:DeformFaceContour": "x",
    "warp:DeformEyeShapeL": "xy",
    "warp:DeformEyeShapeR": "xy",
    "warp:DeformBrowShapeL": "xy",
    "warp:DeformBrowShapeR": "xy",
    "warp:DeformEarOcclusionL": "xy",
    "warp:DeformEarOcclusionR": "xy",
    "warp:DeformNoseShapeBoth": "xy",
    "warp:DeformMouthShapeBoth": "xy",
    "warp:DeformHairFrontFollow": "xy",
    "warp:DeformHairBackFollow": "xy",
}
CONTAINER = "warp:DeformHeadContainer"

# How far the head should travel at the full +-45 / +-30 range, in canvas px.
# The head is ~380px across, so ~1.2px per degree reads as a turn without
# pulling the chin off a 63px-wide neck.
PX_PER_DEG_X = 1.2
PX_PER_DEG_Y = 1.2


def keys_of(axes):
    """Non-neutral keys an object keyed on `axes` actually has."""
    ks = []
    if "x" in axes:
        ks += [(x, y) for x in (-45.0, 45.0) for y in YS]
    if "y" in axes:
        ks += [(0.0, y) for y in (-30.0, 30.0)]
    return ks


def key_obj(axes, x, y):
    k = {}
    if "x" in axes:
        k["ParamAngleX"] = x
    if "y" in axes:
        k["ParamAngleY"] = y
    return k


def send(changes, label):
    changed = []
    for i in range(0, len(changes), 64):
        res, sc = call("form", {"changes": changes[i:i + 64]})
        if res.get("isError") or "error" in (sc or {}):
            print(f"ERR {label}: {json.dumps(sc, ensure_ascii=False)[:400]}")
            sys.exit(1)
        changed += (sc or {}).get("changed", [])
    print(f"{label}: {len(changes)} copies -> {json.dumps(sorted(set(changed)), ensure_ascii=False)}")


def flatten(target, axes):
    """Fold every non-neutral key back onto the neutral pose."""
    neutral = key_obj(axes, 0.0, 0.0)
    return [{"op": "copy", "target": target, "from": neutral,
             "key": key_obj(axes, x, y)} for x, y in keys_of(axes)]


def all_flatten():
    changes = []
    for t, ax in BRANCHES.items():
        changes += flatten(t, ax)
    changes += flatten(CONTAINER, "xy")
    send(changes, "flatten head branches + container")


def container_translate(deltas):
    """deltas: {(x,y): (dx,dy)} in normalized object units."""
    out = []
    for (x, y), (dx, dy) in deltas.items():
        out.append({"target": CONTAINER, "key": key_obj("xy", x, y),
                    "operations": [{"type": "translate", "delta": [dx, dy]}]})
    return out


if __name__ == "__main__":
    print("state before:", get_state())
    all_flatten()
    print("flattened; state:", get_state())
