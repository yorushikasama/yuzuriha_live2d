"""Replay of the face swap + eyebrow draw-order fix after an app restart.

The PSD2Live app keeps everything in memory; a restart reverts to the last saved
project (the 9/30 baseline, 34 layers, no cy_*/精修 layers, alphaThreshold back
to 8). This script re-applies, on top of that baseline:

  1. visibility swap - hide the PSD face/nose/mouth, show the re-imported
     Cyrene layers (mesh ids are deterministic, they came out identical);
  2. the chapter-7 eyebrow draw_order fix, without which the PSD-stacked brows
     sit under the opaque face plate and never render.
"""
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "..", "tools"))
from psd2live_mcp import Mcp  # noqa: E402

HIDE = [
    "ArtMeshFace2",       # face-t  (原版 PSD 脸)
    "ArtMeshNose2",       # nose    (原版)
    "ArtMeshMouth",       # mouth   (原版)
    "ArtMeshMouth_lip_0", # mouth / 上唇描边
    "ArtMeshMouth_lip_1", # mouth / 下唇描边
]
SHOW = [
    "ArtMeshFace",             # cy_face
    "ArtMeshNose",             # cy_nose
    "ArtMeshMouthClose",       # cy_mouth_close
    "ArtMeshMouthOpen",        # cy_mouth_open
    "ArtMeshMouthOpen_lip_0",  # cy_mouth_open / 上唇描边
    "ArtMeshMouthOpen_lip_1",  # cy_mouth_open / 下唇描边
]
# 第七章配方:眉在脸之上、睫毛之下(导出端会整体重排,数值与最终档位不一一对应)
BROW_ORDER = [
    ("ArtMeshEyebrowL", 20),
    ("ArtMeshEyebrowR2", 18),
    ("ArtMeshEyebrowR", 19),
]


def main():
    m = Mcp()
    m.initialize()
    state = open(os.path.join(HERE, "state.txt"), encoding="utf-8").read().strip()

    def call(tool, args):
        nonlocal state
        args = dict(args)
        if tool not in ("inspect", "revision"):
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
        if res.get("isError"):
            print("  !!", json.dumps(sc, ensure_ascii=False)[:300])
        return sc

    edits = [{"action": "visibility", "kind": "mesh", "id": mid, "visible": False}
             for mid in HIDE]
    edits += [{"action": "visibility", "kind": "mesh", "id": mid, "visible": True}
              for mid in SHOW]
    sc = call("appearance", {"edits": edits})
    print("appearance ->", json.dumps(sc, ensure_ascii=False)[:300])

    edits = [{"action": "static", "kind": "mesh", "id": mid, "draw_order": order}
             for mid, order in BROW_ORDER]
    sc = call("structure", {"edits": edits})
    print("structure  ->", json.dumps(sc, ensure_ascii=False)[:300])

    with open(os.path.join(HERE, "state.txt"), "w", encoding="utf-8") as f:
        f.write(state or "")
    print("final state:", state)


if __name__ == "__main__":
    main()
