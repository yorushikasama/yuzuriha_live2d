"""Measure the head's on-canvas position quickly, using PSD2Live's own renderer.

The head sits in the top strip of the canvas and nothing else does, so a
viewport cropped to that strip makes the drawn bounding box a direct readout of
where the head is. mode="model" is the mode that actually applies `parameters`
(mode="poses" silently ignores the `parameters` field and renders neutral).
"""
import base64
import io
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
from psd2live_mcp import Mcp  # noqa: E402
from PIL import Image  # noqa: E402

# tall enough to hold the head at every angle, low enough to exclude the body
STRIP = {"mode": "canvas_rect", "left": 480.0, "top": 0.0, "width": 600.0, "height": 420.0}

BASE = {"ParamAngleX": 0, "ParamAngleY": 0, "ParamAngleZ": 0, "ParamBodyAngleX": 0,
        "ParamBodyAngleY": 0, "ParamBodyAngleZ": 0, "ParamBreath": 0, "ParamEyeBallX": 0,
        "ParamEyeBallY": 0, "ParamEyeBallForm": 0, "ParamEyeLOpen": 1, "ParamEyeROpen": 1,
        "ParamBrowLY": 0, "ParamBrowRY": 0, "ParamMouthForm": 0, "ParamMouthOpenY": 0,
        "ParamHairFront": 0, "ParamHairBack": 0}


def head_box(m, **overrides):
    vals = dict(BASE)
    vals.update(overrides)
    r = m.call("view", {"request": {"mode": "model", "viewport": STRIP,
                                    "target_long_edge": 700, "parameters": vals}})
    res = (r or {}).get("result", {})
    sc = res.get("structuredContent") or {}
    if "error" in sc:
        raise SystemExit("view: " + json.dumps(sc, ensure_ascii=False)[:250])
    if sc.get("appliedParameters", {}).get("ParamAngleX") != vals["ParamAngleX"]:
        raise SystemExit("pose not applied: " + json.dumps(
            sc.get("appliedParameters"), ensure_ascii=False)[:200])
    blob = next((c["data"] for c in res.get("content", []) or []
                 if c.get("type") == "image"), None)
    im = Image.open(io.BytesIO(base64.b64decode(blob))).convert("RGBA")
    W, H = im.size
    px = im.load()
    x0, y0, x1, y1 = 10**9, 10**9, -1, -1
    for y in range(H):
        for x in range(W):
            if px[x, y][3] > 8:
                if x < x0: x0 = x
                if x > x1: x1 = x
                if y < y0: y0 = y
                if y > y1: y1 = y
    if x1 < 0:
        return None
    cr = sc["canvasRect"]
    sx = (cr["right"] - cr["left"]) / W
    sy = (cr["bottom"] - cr["top"]) / H
    return {"cx": cr["left"] + (x0 + x1) / 2 * sx,
            "cy": cr["top"] + (y0 + y1) / 2 * sy,
            "top": cr["top"] + y0 * sy,
            "w": (x1 - x0) * sx, "h": (y1 - y0) * sy}


def deform(m, state, target, key, delta):
    r = m.call("deform", {"state": state, "changes": [
        {"target": target, "key": key,
         "operations": [{"type": "translate", "delta": delta}]}]})
    res = (r or {}).get("result", {})
    if res.get("isError"):
        raise SystemExit("deform: " + " ".join(
            (c.get("text") or "") for c in res.get("content", []))[:500])
    return res["structuredContent"]["state"]


if __name__ == "__main__":
    m = Mcp()
    m.initialize()
    st = m.call("inspect", {"scope": "project"})["result"]["structuredContent"]["state"]
    print("state:", st)

    ref = head_box(m)
    print(f"neutral            cx={ref['cx']:7.1f} cy={ref['cy']:7.1f} "
          f"top={ref['top']:7.1f} w={ref['w']:6.1f} h={ref['h']:6.1f}")

    for x in (45, -45):
        b = head_box(m, ParamAngleX=x)
        print(f"X={x:+4}             cx={b['cx']:7.1f} cy={b['cy']:7.1f} "
              f"top={b['top']:7.1f} w={b['w']:6.1f} h={b['h']:6.1f}   "
              f"d=({b['cx']-ref['cx']:+7.1f},{b['cy']-ref['cy']:+7.1f})")
    for y in (30, -30):
        b = head_box(m, ParamAngleY=y)
        print(f"Y={y:+4}             cx={b['cx']:7.1f} cy={b['cy']:7.1f} "
              f"top={b['top']:7.1f} w={b['w']:6.1f} h={b['h']:6.1f}   "
              f"d=({b['cx']-ref['cx']:+7.1f},{b['cy']-ref['cy']:+7.1f})")
