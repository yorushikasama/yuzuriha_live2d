"""Post-export patch: rebuild the ribbon physics as ONE multi-node pendulum with
several outputs tapped at increasing depth -- the native Cubism mechanism for a
traveling wave.

The PSD2Live physics tool can only emit independent 2-node pendulums, and
chaining pendulums by parameter does not propagate gain in the pixi runtime
(downstream stages read ~0), so the settings are hand-written here.

Node feel follows Cyrene20251105's skirt/mail chain (the reference the user
pointed at): Delay pinned at 1.0 (maximum lag, silky rather than springy) with
Mobility rising along the chain and Acceleration easing off.  The phase lag
between successive nodes is what makes the wave travel down the ribbon when
ParamClothSway / 2 / 3 drive the three nested warp segments.

Inputs follow the project's own hair chains (and Cyrene's): head yaw/roll plus
body yaw/roll, so the ribbons answer both mouse-follow and the idle body sway.
Both X-type sources take Type "X"; the angle sources take Type "Angle".
Run after tools/export.py, or standalone for fast tuning.
"""
import json
import sys

DEPLOY = r"D:\live2d\deploy\yuzuriha\yuzuriha.physics3.json"

# Pendulum nodes below the anchored root (node 0).
# (radius, mobility, delay, acceleration) -- Cyrene-style: delay maxed, mobility rising.
NODES = [
    (9.0,  0.90, 1.0, 1.00),
    (11.0, 0.94, 1.0, 0.95),
    (13.0, 0.96, 1.0, 0.90),
]
# Outputs: (vertex_index, out_param, scale) -- scale ramps toward the hem so the
# tip swings widest.
#
# Gain chosen by rendering three tiers and comparing at the idle peak
# (_work/gain_tiers.png): the idle motion only reaches +-2..3 deg, so a low gain
# leaves the ribbons inert (peak 0.29 of range) and a high gain snaps them to the
# limit on any real head turn (saturates 60%+ of the cycle, which clips the wave
# into a square wave). 3.0/4.5/6.0 peaks at 0.51 during idle -- clearly visible
# and still smooth -- and only approaches the limit on a deliberate big swing.
OUTPUTS = [
    (1, "ParamClothSway",  3.0),
    (2, "ParamClothSway2", 4.5),
    (3, "ParamClothSway3", 6.0),
]
INPUTS = [  # (param, type, weight) -- weights set so only an extreme pose saturates
    # ParamAngleX/Y span +-45/+-30 here; with weight w the engine normalises
    # v*w/100 against Normalization, so w must stay small or a routine head turn
    # pins the pendulum at its limit (measured: 60/40 clipped at ParamAngleX=20).
    ("ParamAngleX", "X", 35.0),
    ("ParamAngleZ", "Angle", 35.0),
    ("ParamBodyAngleX", "X", 65.0),
    ("ParamBodyAngleZ", "Angle", 65.0),
]
IN_POS_NORM = 10.0
IN_ANG_NORM = 10.0


def build_cloth_setting():
    verts = [{"Position": {"X": 0, "Y": 0.0}, "Mobility": 1.0, "Delay": 1.0,
              "Acceleration": 1.0, "Radius": 0.0}]
    y = 0.0
    for (r, mob, delay, acc) in NODES:
        y += r
        verts.append({"Position": {"X": 0, "Y": y}, "Mobility": mob,
                      "Delay": delay, "Acceleration": acc, "Radius": r})
    outputs = [{"Destination": {"Target": "Parameter", "Id": op},
                "VertexIndex": vi, "Scale": sc, "Weight": 100,
                "Type": "Angle", "Reflect": False} for (vi, op, sc) in OUTPUTS]
    inputs = [{"Source": {"Target": "Parameter", "Id": pid},
               "Weight": w, "Type": tp, "Reflect": False}
              for (pid, tp, w) in INPUTS]
    return {
        "Id": "PhysicsCloth",
        "Input": inputs,
        "Output": outputs,
        "Vertices": verts,
        "Normalization": {
            "Position": {"Minimum": -IN_POS_NORM, "Default": 0.0, "Maximum": IN_POS_NORM},
            "Angle": {"Minimum": -IN_ANG_NORM, "Default": 0.0, "Maximum": IN_ANG_NORM},
        },
    }


def main(path=DEPLOY):
    d = json.load(open(path, encoding="utf-8"))
    settings = d["PhysicsSettings"]
    new = [s for s in settings if not s["Id"].startswith("PhysicsCloth")]
    new.append(build_cloth_setting())
    d["PhysicsSettings"] = new
    d["Meta"]["PhysicsSettingCount"] = len(new)
    d["Meta"]["TotalInputCount"] = sum(len(s["Input"]) for s in new)
    d["Meta"]["TotalOutputCount"] = sum(len(s["Output"]) for s in new)
    d["Meta"]["VertexCount"] = sum(len(s["Vertices"]) for s in new)
    # Same startswith rule as the settings filter above, so preview-only groups
    # (e.g. PhysicsClothPreview*) leave no stale display names behind either.
    dic = [x for x in d["Meta"].get("PhysicsDictionary", [])
           if not x["Id"].startswith("PhysicsCloth")]
    if not any(x["Id"] == "PhysicsCloth" for x in dic):
        dic.append({"Id": "PhysicsCloth", "Name": "飘带摆动"})
    d["Meta"]["PhysicsDictionary"] = dic
    json.dump(d, open(path, "w", encoding="utf-8"), ensure_ascii=False, indent=4)
    print("patched", path, "-> single multi-node cloth pendulum, outputs:",
          [o[1] for o in OUTPUTS])


if __name__ == "__main__":
    main(sys.argv[1] if len(sys.argv) > 1 else DEPLOY)
