"""Check whether a PSD's layer alpha has invisible noise that would poison auto-rigging.

Auto-riggers derive each part's bounding box from its alpha.  A layer that carries
alpha 1..3/255 (0.4%-1.2%, invisible) spread over the whole canvas -- common in PSDs
saved from compositing tools -- gets measured as full-canvas, which inflates the
face-rig radii by roughly an order of magnitude.  Head-turn displacement is
proportional to those radii, so the head slides off the neck while the neck (parented
to the body) stays put: it looks exactly like a broken binding.

Gotcha: read the alpha from numpy("RGBA")[..., 3].  numpy("A") returns the merged
opaque channel and reports every such layer as full-canvas, hiding the real bounds.

    python tools/alpha_noise_check.py yuzuriha.psd
"""
import sys

import numpy as np
from psd_tools import PSDImage

# PSD2Live counts a pixel as opaque from its default alpha byte threshold of 1.
DEFAULT_THRESHOLD = 1
# A threshold that drops antialiasing fringe and stray composites but keeps real strokes.
SUGGESTED_THRESHOLD = 64


def canvas_bbox(alpha_bytes, layer, threshold):
    ys, xs = np.nonzero(alpha_bytes >= threshold)
    if not len(xs):
        return None
    return (int(xs.min()) + layer.left, int(ys.min()) + layer.top,
            int(xs.max()) + layer.left, int(ys.max()) + layer.top, len(xs))


def main():
    path = sys.argv[1] if len(sys.argv) > 1 else "yuzuriha.psd"
    psd = PSDImage.open(path)
    W, H = psd.width, psd.height
    canvas_area = W * H
    print("%s  canvas %dx%d" % (path, W, H))
    print()
    print("%-14s %-8s %-10s %-24s %s" % (
        "layer", "noise", "far px", "bbox @thr=1 (canvas px)", "bbox @thr=%d" % SUGGESTED_THRESHOLD))
    print("-" * 104)

    poisoned = []
    for layer in psd.descendants():
        if layer.is_group():
            continue
        rgb = np.asarray(layer.numpy("RGBA"), dtype=np.float32)
        if rgb.ndim != 3 or rgb.shape[2] < 4:
            continue
        a = (rgb[..., 3] * 255).round().astype(np.int32)

        noise = int(((a >= 1) & (a < DEFAULT_THRESHOLD + 32)).sum())
        far = int((a >= 1).sum()) - int((a >= SUGGESTED_THRESHOLD).sum())
        b1 = canvas_bbox(a, layer, DEFAULT_THRESHOLD)
        b64 = canvas_bbox(a, layer, SUGGESTED_THRESHOLD)

        def fmt(b):
            if b is None:
                return "EMPTY"
            return "x[%d,%d] y[%d,%d] w=%d h=%d" % (b[0], b[2], b[1], b[3], b[2] - b[0] + 1, b[3] - b[1] + 1)

        w1 = (b1[2] - b1[0] + 1) if b1 else 0
        h1 = (b1[3] - b1[1] + 1) if b1 else 0
        full = b1 is not None and w1 >= W and h1 >= H
        if full:
            poisoned.append(layer.name)
        print("%-14s %-8d %-10d %-24s %s%s" % (
            layer.name[:14], noise, far, fmt(b1), fmt(b64), "   <== full-canvas" if full else ""))

    print()
    if poisoned:
        print("PROBLEM: %d layer(s) measure as full-canvas at alphaThreshold=%d:" % (len(poisoned), DEFAULT_THRESHOLD))
        for n in poisoned:
            print("   -", n)
        print()
        print("These layers have invisible alpha noise (and no layer mask), so the auto-rig")
        print("computes full-canvas bounds for them and inflates the face-rig radii.")
        print("Fix: raise the project's alpha threshold (PSD2Live: settings.alphaThreshold)")
        print("to %d, which clears the noise and keeps every real stroke." % SUGGESTED_THRESHOLD)
    else:
        print("OK: no layer measures as full-canvas at alphaThreshold=%d." % DEFAULT_THRESHOLD)


if __name__ == "__main__":
    main()
