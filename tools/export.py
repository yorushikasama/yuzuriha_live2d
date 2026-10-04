"""Export the PSD2Live project and publish it to the web deploy folder.

The browser runtime measures the rig far more precisely than the editor's own
view tool (its layer filter silently renders nothing), so the fix loop is:
    apply deform -> export -> copy -> measure in the browser -> adjust
"""
import json
import os
import shutil
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
from psd2live_mcp import Mcp  # noqa: E402

# Overridable so the project can live outside D:\live2d (and so a contributor on
# another machine does not have to edit the script).
ROOT = os.environ.get("PSD2LIVE_ROOT", r"D:\live2d")
OUT = os.environ.get("PSD2LIVE_OUT", os.path.join(ROOT, "out"))
# Published to ROOT/<family>/, where <family> is whatever the source PSD is
# called -- PSD2Live names the exported family after the source file. Resolved
# at run time from the actual export rather than assumed.


def main():
    m = Mcp()
    m.initialize()
    st = m.call("inspect", {"scope": "project"})["result"]["structuredContent"]["state"]

    # PSD2Live names the exported family after the SOURCE FILE, so the prefix
    # varies by variant (yuzuriha.psd -> yuzuriha.*, source.psd -> source.*).
    # Start from an empty OUT so a previous variant's files can never be
    # published as this one's -- that bug shipped the Cyrene model into the
    # original path once already.
    if os.path.isdir(OUT):
        shutil.rmtree(OUT)
    os.makedirs(OUT, exist_ok=True)

    r = m.call("export", {"state": st, "output_directory": OUT})
    res = (r or {}).get("result", {})
    if res.get("isError"):
        raise SystemExit("export: " + " ".join(
            (c.get("text") or "") for c in res.get("content") or [])[:600])
    sc = res.get("structuredContent") or {}
    files = sc.get("files") or []
    print(f"exported {len(files) if isinstance(files, list) else '?'} files -> {OUT}")
    for w in sc.get("warnings") or []:
        print("  warning:", str(w)[:200])

    # Derive the family prefix from what the app actually wrote, rather than
    # assuming a name. The file is "<stem>.model3.json", so strip both suffixes.
    models = [f for f in files if f.get("path", "").endswith(".model3.json")]
    if len(models) != 1:
        raise SystemExit(f"expected exactly one model3.json in the export, got {len(models)}")
    base = os.path.basename(models[0]["path"])
    stem = base[: -len(".model3.json")]
    print(f"model family: {stem}.*")

    # Regression guard: the alpha-noise bug (settings.alphaThreshold = 1) used to push
    # faceRig.radiusX to 1335 (>2670px face width) and fling the head off the neck.
    # If the project state ever reverts (e.g. the app restarts with an unsaved project),
    # fail loudly here instead of publishing a broken model.
    report = json.load(open(os.path.join(OUT, stem + ".psd2live.json"), encoding="utf-8"))
    rig = report.get("faceRig") or {}
    rx, ry, az = rig.get("radiusX", 0), rig.get("radiusY", 0), rig.get("initialAngleZ", 0)
    if not (0 < rx < 200 and 0 < ry < 300 and abs(az) < 5):
        raise SystemExit(
            f"FACE RIG LOOKS WRONG: radiusX={rx} radiusY={ry} initialAngleZ={az}. "
            "Expected ~71/~100/~0. The project has probably lost the alphaThreshold=64 "
            "fix (settings.alphaThreshold). Do NOT publish this export.")

    # publish the runtime-relevant files (textures are unchanged but copying all
    # of them keeps the deploy folder self-consistent). The .cmo3 editor project
    # and the .psd2live.json diagnostic report are not runtime files and must not
    # bloat / leak into the web-served folder, so they stay in OUT only.
    SKIP_PUBLISH = (".cmo3", ".psd2live.json")
    DEPLOY = os.path.join(ROOT, stem)
    if os.path.isdir(DEPLOY):
        shutil.rmtree(DEPLOY)
    os.makedirs(DEPLOY, exist_ok=True)
    n = 0
    for root, _dirs, names in os.walk(OUT):
        for name in names:
            if name.endswith(SKIP_PUBLISH):
                continue
            src = os.path.join(root, name)
            rel = os.path.relpath(src, OUT)
            dst = os.path.join(DEPLOY, rel)
            os.makedirs(os.path.dirname(dst), exist_ok=True)
            shutil.copy2(src, dst)
            n += 1
    print(f"published {n} files -> {DEPLOY}")

    # The PSD2Live physics tool can only emit independent 2-node pendulums, so the
    # silky multi-node cloth wave (one pendulum chain, three depth-tapped outputs)
    # lives in a post-export patch. Re-apply it to the freshly published physics
    # file, otherwise every export reverts the ribbons to the stiff single swing.
    import patch_cloth_physics  # noqa: E402
    patch_cloth_physics.main(os.path.join(DEPLOY, stem + ".physics3.json"))

    print("state:", st)


if __name__ == "__main__":
    main()
