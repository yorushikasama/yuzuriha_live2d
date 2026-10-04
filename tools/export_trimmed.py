"""Export every live layer's source pixels at 1:1 through `view mode=layer`.

Why not read the project's blobs: the .psd2live saved in the project directory
predates the current in-app state (its archived blob hashes do not match the
head snapshot's rgbaBlob values), and the running app is the only holder of the
live artwork. `view mode=layer` renders one source layer at scale 1.0 and
reports the canvas rectangle it was placed at -- exactly the pair `asset create`
wants: a trimmed PNG plus the x/y it goes back to.

Layers inherited from the PSD keep full-canvas storage (the whole reason the
atlas needs three pages), so the export crops each one to its ink. A full-body
render diff is the acceptance check that cropping lost nothing.
"""
from __future__ import annotations

import base64
import json
import os
import sys

import numpy as np
from PIL import Image

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "tools"))
from psd2live_mcp import Mcp  # noqa: E402

OUT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "trimmed")
CANVAS = 1536
# The PSD hides an alpha noise haze of 1..31 across every full-canvas layer
# (back hair: 52107 haze pixels vs 48101 ink pixels). Anything below 32 is
# haze, and it is what pins those layers' bounding boxes to the whole canvas.
# `settings.alphaThreshold` is 64, so the runtime already treats <64 as empty.
THRESH = 32
MARGIN = 2

# Deleted ids never render. A stale reference to one of these
# ("lyid:16::mouth-lip-0") is what makes `inspect scope=layers` blow up.
DEAD = {"lyid:10", "lyid:14", "lyid:17", "lyid:18", "lyid:6", "lyid:8", "lyid:9"}


def call(m, tool, args):
    """Call a tool and return (structuredContent, content)."""
    r = m.call(tool, args)
    res = (r or {}).get("result", {}) or {}
    if res.get("isError"):
        raise RuntimeError((tool, args, res))
    return res.get("structuredContent") or {}, res.get("content") or []


def all_meshes(m):
    """inspect scope=objects paginates; page until the cursor stops moving."""
    out, off = [], 0
    while True:
        sc, _ = call(m, "inspect", {"scope": "objects", "query": "ArtMesh",
                                    "offset": off, "limit": 64})
        items = sc.get("items") or []
        if not items:
            break
        out.extend(items)
        off = len(out)
    return out


def image_of(content):
    for c in content:
        if c.get("type") == "image":
            return base64.b64decode(c["data"])
    return None


def load(buf):
    import io
    return np.array(Image.open(io.BytesIO(buf)).convert("RGBA"))


def trim(rgba):
    """Bounding box of pixels with alpha >= THRESH, padded by MARGIN.

    The PSD carries a low-alpha noise haze across the whole canvas; at any
    scale that haze would pin the box to the full canvas, so it is clipped
    rather than merely ignored.
    """
    if THRESH > 0:
        rgba = rgba.copy()
        rgba[:, :, 3] = np.where(rgba[:, :, 3] < THRESH, 0, rgba[:, :, 3])
    a = rgba[:, :, 3]
    ys, xs = np.nonzero(a)
    if len(xs) == 0:
        return None
    x0 = max(0, int(xs.min()) - MARGIN)
    y0 = max(0, int(ys.min()) - MARGIN)
    x1 = min(rgba.shape[1] - 1, int(xs.max()) + MARGIN)
    y1 = min(rgba.shape[0] - 1, int(ys.max()) + MARGIN)
    return x0, y0, x1 - x0 + 1, y1 - y0 + 1


def main():
    m = Mcp()
    m.initialize()
    os.makedirs(OUT, exist_ok=True)
    for f in os.listdir(OUT):
        os.remove(os.path.join(OUT, f))

    meshes = all_meshes(m)
    print("meshes:", len(meshes))

    manifest = []
    for i, it in enumerate(meshes):
        lid = it.get("layerId")
        name = it.get("name")
        if lid in DEAD:
            print("  -- dead layer, skipped:", name, lid)
            continue
        # Lip outlines are sub-pieces of their parent layer's artwork; exporting the
        # parent already carries the pixels, and `asset create` cannot recreate
        # the ::piece split on its own.
        if "::" in lid:
            print("  -- sub-piece of an exported layer, skipped:", name, lid)
            continue

        # `view` scales the layer's content bounding box to `target_long_edge` --
        # it is a target, not a cap, so asking for 1536 magnifies a small layer
        # and the haze magnifies with it. canvasRect reports the box in ORIGINAL
        # canvas pixels, so requesting that long edge returns the artwork 1:1.
        probe, _ = call(m, "view", {"request": {"mode": "layer", "layer_id": lid,
                                                "target_long_edge": 128}})
        rect = probe["canvasRect"]
        long_edge = int(round(max(rect["right"] - rect["left"],
                                  rect["bottom"] - rect["top"])))
        if not 1 <= long_edge <= 4096:
            print("  !! implausible content size for", name, rect)
            continue
        sc, content = call(m, "view", {"request": {
            "mode": "layer", "layer_id": lid,
            "target_long_edge": max(128, long_edge), "background": "transparent",
        }})
        expect_w = round(rect["right"] - rect["left"])
        expect_h = round(rect["bottom"] - rect["top"])
        if long_edge >= 128 and (sc["renderedWidth"] != expect_w
                                 or sc["renderedHeight"] != expect_h):
            print("  !! %s rendered %dx%d, expected %dx%d -- resampled, skipping"
                  % (name, sc["renderedWidth"], sc["renderedHeight"],
                     expect_w, expect_h))
            continue
        rect = sc["canvasRect"]
        buf = image_of(content)
        if buf is None:
            print("  !! no image for", name, lid)
            continue
        full = load(buf)
        box = trim(full)
        if box is None:
            print("  -- fully transparent, skipped:", name, lid)
            continue
        bx, by, bw, bh = box
        sub = full[by:by + bh, bx:bx + bw]
        safe = name.replace("/", "_").replace(" ", "_")
        fn = "%02d_%s.png" % (i, safe)
        Image.fromarray(sub, "RGBA").save(os.path.join(OUT, fn))
        manifest.append({
            "name": name,
            "source_layer_id": lid,
            "file": fn,
            "x": rect["left"] + bx,
            "y": rect["top"] + by,
            "w": int(bw),
            "h": int(bh),
            "rendered": [int(full.shape[1]), int(full.shape[0])],
        })
        print("  %-26s %-46s %5dx%-5d -> %5dx%-5d @ %7.1f,%-7.1f  (%.0f%% of full canvas)"
              % (name, lid[:46], full.shape[1], full.shape[0], bw, bh,
                 rect["left"] + bx, rect["top"] + by,
                 100.0 * bw * bh / (CANVAS * CANVAS)))

    with open(os.path.join(OUT, "manifest.json"), "w", encoding="utf-8") as f:
        json.dump(manifest, f, ensure_ascii=False, indent=1)

    before = sum(m2["rendered"][0] * m2["rendered"][1] for m2 in manifest)
    after = sum(m2["w"] * m2["h"] for m2 in manifest)
    print("\nexported %d layers" % len(manifest))
    print("  content bbox total: %6.2f Mpx" % (before / 1e6))
    print("  after alpha trim:   %6.2f Mpx  (%.1f%% of bbox)" % (after / 1e6, 100 * after / before))
    print("  a 2048 atlas holds 4.2 Mpx, 4096 holds 16.8 Mpx")


if __name__ == "__main__":
    main()
