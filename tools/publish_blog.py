"""Publish the exported model to the Firefly blog's public assets.

One command replaces the manual copy step (which once left the blog on a stale,
TapBody-less model3.json): re-apply hand edits, compress textures for web, then
sync into the blog with pruning so removed files disappear there too.

    python tools/publish_blog.py                       # 默认目标 D:\\code\\Firefly
    BLOG_ROOT=/path/to/Firefly python tools/publish_blog.py
    python tools/publish_blog.py --size 1024 --colors 128

Requires Pillow (only for the texture step; everything else is stdlib).
The 4096 masters in yuzuriha/ are never modified -- compression lands only
in the blog copy.
"""
import argparse
import json
import os
import shutil

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.environ.get("PSD2LIVE_ROOT", r"D:\live2d")
BLOG_ROOT = os.environ.get("BLOG_ROOT", r"D:\code\Firefly")

SRC = os.path.join(ROOT, "yuzuriha")
DST = os.path.join(BLOG_ROOT, "public", "pio", "models", "live2d", "yuzuriha")

# The web runtime loads only the model family; index.html / README.md are the
# repo's demo page and deploy notes, not blog assets.
SKIP = ("index.html", "README.md")

# Hand edit kept outside the export: PSD2Live re-export drops the TapBody
# motion group (the tap-to-react wiring lives in the blog's widget). Re-apply
# it here, mirroring what patch_cloth_physics does for physics3.json.
TAP_BODY = {"File": "yuzuriha.nod.motion3.json"}, {"File": "yuzuriha.shake.motion3.json"}


def patch_tap_body(path):
    with open(path, encoding="utf-8") as f:
        model = json.load(f)
    motions = model.setdefault("FileReferences", {}).setdefault("Motions", {})
    if motions.get("TapBody") != list(TAP_BODY):
        motions["TapBody"] = list(TAP_BODY)
        with open(path, "w", encoding="utf-8", newline="\n") as f:
            json.dump(model, f, ensure_ascii=False, indent="\t")
        print("patched TapBody motion group ->", path)
    else:
        print("TapBody already present:", path)


def compress_textures(src_dir, dst_dir, size, colors):
    """Shrink atlas pages for the widget: the PSD canvas is ~98% transparent
    and the art is flat cel shading, so palette PNGs lose nothing at the
    widget's ~440x680 physical render size (2048 still oversamples ~3x).
    UVs are normalized, so file names stay and only pixels change."""
    from PIL import Image

    os.makedirs(dst_dir, exist_ok=True)
    for name in sorted(os.listdir(src_dir)):
        if not name.lower().endswith(".png"):
            continue
        im = Image.open(os.path.join(src_dir, name))
        if im.size != (size, size):
            im = im.resize((size, size), Image.LANCZOS)
        im = im.quantize(colors, method=Image.FASTOCTREE)
        out = os.path.join(dst_dir, name)
        im.save(out, "PNG", optimize=True)
        print(f"  {name}: {size}px, {colors} colors -> {os.path.getsize(out)/1024:,.0f} KB")


def sync(src, dst):
    """Copy SRC -> DST with pruning: stale files in DST are removed."""
    copied, pruned = [], []
    src_rel = set()
    for dirpath, _dirs, names in os.walk(src):
        for name in names:
            if name in SKIP:
                continue
            full = os.path.join(dirpath, name)
            rel = os.path.relpath(full, src)
            src_rel.add(rel)
            target = os.path.join(dst, rel)
            os.makedirs(os.path.dirname(target), exist_ok=True)
            if not os.path.exists(target) or not _same(full, target):
                shutil.copy2(full, target)
                copied.append(rel)
    for dirpath, _dirs, names in os.walk(dst):
        for name in names:
            rel = os.path.relpath(os.path.join(dirpath, name), dst)
            if rel not in src_rel:
                os.remove(os.path.join(dirpath, name))
                pruned.append(rel)
    for rel in copied:
        print("  copied:", rel)
    for rel in pruned:
        print("  pruned:", rel)
    print(f"sync: {len(src_rel)} files, {len(copied)} copied, {len(pruned)} pruned -> {dst}")


def _same(a, b):
    if os.path.getsize(a) != os.path.getsize(b):
        return False
    with open(a, "rb") as fa, open(b, "rb") as fb:
        while True:
            ca, cb = fa.read(1 << 20), fb.read(1 << 20)
            if ca != cb:
                return False
            if not ca:
                return True


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--size", type=int, default=2048, help="texture edge length (default 2048)")
    ap.add_argument("--colors", type=int, default=256, help="palette size, 2-256 (default 256)")
    args = ap.parse_args()

    if not os.path.isdir(SRC):
        raise SystemExit(f"model folder not found: {SRC}")
    if not os.path.isdir(BLOG_ROOT):
        raise SystemExit(f"blog root not found: {BLOG_ROOT} (set BLOG_ROOT)")

    # 1. hand edits first, so every downstream consumer gets the same model3.json
    patch_tap_body(os.path.join(SRC, "yuzuriha.model3.json"))

    # 2. compress into a staging dir next to the source, then sync the whole
    #    folder (compressed textures overwrite their 4096 counterparts there)
    staging = os.path.join(ROOT, "out", "blog_staging")
    if os.path.isdir(staging):
        shutil.rmtree(staging)
    sync(SRC, staging)  # JSON + moc3 as-is; textures get overwritten below
    print("compressing textures:")
    compress_textures(
        os.path.join(SRC, "yuzuriha.4096"),
        os.path.join(staging, "yuzuriha.4096"),
        args.size,
        args.colors,
    )

    # 3. deliver to the blog (with pruning)
    print("publishing:")
    sync(staging, DST)


if __name__ == "__main__":
    main()
