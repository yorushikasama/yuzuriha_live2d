"""Write a second PSD whose face / nose / mouth layers carry Cyrene's artwork.

Two PSDs on purpose
-------------------
    variants/original/yuzuriha.psd   the original, untouched
    variants/cyrene/yuzuriha.psd     the same file with the head swapped

Someone reproducing the model can start from either, or diff the two to see
exactly what changed. Editing the original in place would destroy that baseline.

Scripted rather than hand-edited in Photoshop
---------------------------------------------
`psd-tools` is deterministic and re-runnable. A Photoshop session is not.

What the swap is
----------------
Measured on the original PSD (alpha >= 64, the project's own threshold):

    layer     ink px   ink bbox     verdict
    face       15897   131x160      the real face
    nose          35     6x7        vestigial -- a few leftover strokes
    mouth         88    19x9        vestigial -- a few leftover strokes

The old nose and mouth are effectively empty; the old face is what Cyrene's
replaces. Cyrene's parts, cut at the same threshold:

    cy_face_t        17124 ink  141x164  @ (694, 78)
    cy_nose_t         5751 ink   79x107  @ (764, 189)
    cy_mouth_open_t   9834 ink  118x114  @ (749, 201)
    cy_mouth_close_t  9311 ink  118x108  @ (749, 199)

Placement lands within a few pixels of the original face box (694,78 vs
702,80), so no manual nudging is needed.

Three psd-tools traps, each of which cost a round
-------------------------------------------------
1. `layer.numpy()` returns RAW channel data, which reads back EMPTY for a
   freshly created layer. `layer.composite()` returns the real pixels. Verify
   with `composite()` or every ink check silently reports zero.
2. `layer.visible = False` DISCARDS the layer's pixels on save (verified:
   face drops from 15897 ink px to 0). The originals are therefore *removed*,
   not hidden -- which also keeps yuzuriha.psd as the untouched baseline.
3. `PixelLayer.frompil(...)` appends at the BOTTOM of the stack. Use
   `move_up()` to place the head parts where the originals were.

Usage:
    python tools/make_cyrene_psd.py
    PSD2LIVE_ROOT=/path/to/repo python tools/make_cyrene_psd.py
"""
from __future__ import annotations

import json
import os

import numpy as np
from PIL import Image
from psd_tools import PSDImage
from psd_tools.api.layers import PixelLayer

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.environ.get("PSD2LIVE_ROOT", os.path.dirname(HERE))
SRC = os.path.join(ROOT, "variants", "original", "yuzuriha.psd")
DST = os.path.join(ROOT, "variants", "cyrene", "yuzuriha.psd")
ASSETS = os.path.join(ROOT, "assets", "trimmed")
MANIFEST = os.path.join(ASSETS, "manifest.json")

# The project's alpha threshold. Below 32 is PSD haze, not ink (REPRODUCE.md 4.1).
THRESH = 32
INK = 64

# manifest name -> new PSD layer name
NEW = [
    # (manifest name, layer name, original it replaces)
    ("cy_face_t", "cy_face", "face"),
    ("cy_nose_t", "cy_nose", "nose"),
    ("cy_mouth_open_t", "cy_mouth_open", "mouth"),
    ("cy_mouth_close_t", "cy_mouth_close", "mouth"),
]
# Bottom-to-top among the new head parts. The closed lips must end up ON TOP
# so the model rests with a closed mouth.
STACK = ["cy_face", "cy_nose", "cy_mouth_open", "cy_mouth_close"]
# Insert the block just under these, i.e. the ears sit above the face.
ANCHOR_ABOVE = "ears-l"
MIN_INK = 500


def load_parts():
    mf = {e["name"]: e for e in json.load(open(MANIFEST, encoding="utf-8"))}
    parts = {}
    for src, _name, _orig in NEW:
        e = mf[src]
        a = np.array(Image.open(os.path.join(ASSETS, e["file"])).convert("RGBA"))
        a[:, :, 3] = np.where(a[:, :, 3] < THRESH, 0, a[:, :, 3])
        parts[_name] = (Image.fromarray(a, "RGBA"), int(e["y"]), int(e["x"]))
    return parts


def ink_of(layer):
    """`composite()`, never `numpy()` -- see trap 1 in the docstring."""
    arr = np.array(layer.composite())
    if arr.ndim != 3 or arr.shape[2] != 4:
        return -1
    return int((arr[:, :, 3] >= INK).sum())


def names(psd):
    return [l.name for l in psd]


def main():
    parts = load_parts()
    psd = PSDImage.open(SRC)
    before = names(psd)
    print("source: %dx%d, %d layers" % (psd.width, psd.height, len(psd)))

    # 1. Remove the originals (not hide -- trap 2).
    for orig in ("face", "nose", "mouth"):
        hit = [l for l in psd if l.name == orig]
        if not hit:
            raise SystemExit("source PSD lacks layer %r" % orig)
        print("  drop %-6s (ink %d)" % (orig, ink_of(hit[0])))
        psd.remove(hit[0])

    # 2. Add the Cyrene parts, then insert them at the slot the originals
    #    occupied. `frompil` appends at the bottom (trap 3); `insert(index, ...)`
    #    is the documented way to place them.
    #
    #    psd-tools lists TOP-FIRST, and the originals were face(11) nose(12)
    #    mouth(13) with ears-l at 10. So the new block goes at index 11, and
    #    STACK is bottom-to-top, i.e. reverse of the list order.
    anchor = [l for l in psd if l.name == ANCHOR_ABOVE][0]
    at = names(psd).index(ANCHOR_ABOVE) + 1
    for _src, name, _orig in NEW:
        img, top, left = parts[name]
        layer = PixelLayer.frompil(img, psd, name=name, top=top, left=left)
        psd.insert(at, layer)
        at += 1
        print("  add  %-16s %dx%d @ (%d,%d)  ink %d"
              % (name, img.width, img.height, left, top,
                 int((np.array(img)[:, :, 3] >= INK).sum())))
    assert anchor is not None

    print("\nresulting order:")
    for i, l in enumerate(psd):
        print("  %2d %s" % (i, l.name))

    psd.save(DST)
    print("\nwrote %s (%.1f MB)" % (DST, os.path.getsize(DST) / 1048576))

    chk = PSDImage.open(DST)
    got = names(chk)
    print("verify (%d layers):" % len(chk))
    ok = True
    for _src, name, _orig in NEW:
        if name not in got:
            print("  MISSING %s" % name)
            ok = False
            continue
        layer = [l for l in chk if l.name == name][0]
        n = ink_of(layer)
        good = n >= MIN_INK
        ok = ok and good
        print("  %-16s bbox=%-22s ink=%-7d %s"
              % (name, layer.bbox, n, "ok" if good else "SUSPECT"))
    for orig in ("face", "nose", "mouth"):
        if orig in got:
            print("  original %s still present" % orig)
            ok = False
    lost = [n for n in before if n not in got and n not in ("face", "nose", "mouth")]
    if lost:
        print("  unrelated layers lost: %s" % lost)
        ok = False
    # Layer order must match the original: the head block sat at index 11..14,
    # i.e. below ears-l (10) and above eyelash-l (15) in psd-tools' top-first
    # listing.
    got = names(chk)
    if not (got.index("ears-l") < got.index("cy_face") < got.index("eyelash-l")):
        print("  head block misplaced: ears-l=%d cy_face=%d eyelash-l=%d"
              % (got.index("ears-l"), got.index("cy_face"), got.index("eyelash-l")))
        ok = False
    if not (got.index("cy_mouth_open") < got.index("cy_mouth_close")):
        print("  closed lips must sit ON TOP of the open mouth")
        ok = False
    print("\n%s" % ("PASS" if ok else "FAIL"))
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
