"""Build six restrained Cubism motion3 clips; Python 3.10+, standard library only.

Usage (the target must already contain exactly one *.model3.json):
    python tools/build_motions.py --directory <model-directory>

The directory is REQUIRED so an unqualified invocation cannot modify deployment.
Only <model>.{idle,blink,nod,shake,smile,lookaround}.motion3.json and the
FileReferences.Motions subtree of that model3 file are managed. Other motion
entries, reference options, model fields and assets are preserved. Identical
bytes are not rewritten. Run this as a separate post-export step; it does not
call or patch the exporter or the editor.

Blink exclusively owns eye openness. Other clips leave eyes, gaze, lip-sync
and all physics outputs alone. LookAround uses head/body turns, allowing a
runtime gaze controller to remain independent. A separate runtime blink layer
(or automatic blink controller) is still needed for concurrent blinking.
Meta.Loop declares Idle's intent; some SDKs additionally require setIsLoop(true).
"""
from __future__ import annotations

import argparse
import codecs
import copy
import json
import math
import os
import re
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Sequence

FPS = 30.0
MODEL_SUFFIX = ".model3.json"
MOTION_NAMES = ("Idle", "Blink", "Nod", "Shake", "Smile", "LookAround")
EYES = frozenset(("ParamEyeLOpen", "ParamEyeROpen"))
# (minimum, neutral, maximum): an allow-list, not a physics-name deny-list.
PARAMETERS = {
    "ParamAngleX": (-15.0, 0.0, 15.0),
    "ParamAngleY": (-15.0, 0.0, 15.0),
    "ParamAngleZ": (-15.0, 0.0, 15.0),
    "ParamBodyAngleX": (-3.0, 0.0, 3.0),
    "ParamBodyAngleY": (-3.0, 0.0, 3.0),
    "ParamBodyAngleZ": (-3.0, 0.0, 3.0),
    "ParamBreath": (0.0, 0.0, 1.0),
    "ParamEyeLOpen": (0.0, 1.0, 1.0),
    "ParamEyeROpen": (0.0, 1.0, 1.0),
    "ParamMouthForm": (-1.0, 0.0, 1.0),
    "ParamBrowLY": (-1.0, 0.0, 1.0),
    "ParamBrowRY": (-1.0, 0.0, 1.0),
}
Keyframes = Sequence[tuple[float, float]]
JsonObject = dict[str, Any]


@dataclass(frozen=True)
class MotionSpec:
    duration: float
    fade_in: float
    fade_out: float
    tracks: dict[str, Keyframes]


def motion_specs() -> dict[str, MotionSpec]:
    """Times are seconds; all keyed values are deliberately below the limits."""
    blink = ((0.0, 1.0), (0.28, 1.0), (0.38, 0.0), (0.43, 0.0),
             (0.62, 1.0), (1.2, 1.0))
    brow = ((0.0, 0.0), (0.35, 0.0), (1.1, 0.12), (2.2, 0.12),
            (3.2, 0.0), (3.6, 0.0))
    return {
        "Idle": MotionSpec(12.0, 0.8, 0.6, {
            # Two unhurried breaths; slightly longer exhalation, exact loop seam.
            "ParamBreath": ((0.0, 0.0), (2.5, 0.85), (6.0, 0.0),
                            (8.5, 0.8), (12.0, 0.0)),
            "ParamAngleX": ((0.0, 0.0), (2.8, 3.5), (7.5, -3.0), (12.0, 0.0)),
            "ParamAngleY": ((0.0, 0.0), (2.1, -1.1), (6.4, 1.4),
                            (9.8, -0.65), (12.0, 0.0)),
            "ParamAngleZ": ((0.0, 0.0), (3.5, 1.8), (8.0, -1.6), (12.0, 0.0)),
            # Body follows the head, rather than driving the physics outputs.
            "ParamBodyAngleX": ((0.0, 0.0), (3.1, 0.6), (7.9, -0.5), (12.0, 0.0)),
            "ParamBodyAngleY": ((0.0, 0.0), (2.6, 0.35), (6.0, 0.0),
                                (8.6, 0.28), (12.0, 0.0)),
            "ParamBodyAngleZ": ((0.0, 0.0), (4.1, 0.4), (9.0, -0.35), (12.0, 0.0)),
        }),
        "Blink": MotionSpec(1.2, 0.1, 0.15, {
            "ParamEyeLOpen": blink,
            "ParamEyeROpen": blink,
        }),
        "Nod": MotionSpec(2.8, 0.25, 0.3, {
            "ParamAngleY": ((0.0, 0.0), (0.25, 0.0), (0.9, -9.0),
                            (1.65, 2.0), (2.35, 0.0), (2.8, 0.0)),
            "ParamBodyAngleY": ((0.0, 0.0), (0.3, 0.0), (1.05, -1.2),
                                (1.8, 0.3), (2.5, 0.0), (2.8, 0.0)),
        }),
        "Shake": MotionSpec(3.2, 0.25, 0.3, {
            "ParamAngleX": ((0.0, 0.0), (0.25, 0.0), (0.85, -10.0),
                            (1.65, 9.0), (2.35, -3.0), (2.85, 0.0), (3.2, 0.0)),
            "ParamAngleZ": ((0.0, 0.0), (0.25, 0.0), (0.9, 1.0),
                            (1.7, -0.9), (2.4, 0.3), (2.9, 0.0), (3.2, 0.0)),
            "ParamBodyAngleX": ((0.0, 0.0), (0.3, 0.0), (1.0, -1.35),
                                (1.8, 1.2), (2.5, -0.35), (2.9, 0.0), (3.2, 0.0)),
        }),
        "Smile": MotionSpec(3.6, 0.25, 0.35, {
            # Mouth form only: do not key lip-sync or force the eyes half closed.
            "ParamMouthForm": ((0.0, 0.0), (0.25, 0.0), (1.0, 0.5),
                               (2.3, 0.5), (3.2, 0.0), (3.6, 0.0)),
            "ParamBrowLY": brow,
            "ParamBrowRY": brow,
            "ParamAngleZ": ((0.0, 0.0), (0.3, 0.0), (1.2, 1.8),
                            (2.2, 1.8), (3.2, 0.0), (3.6, 0.0)),
        }),
        "LookAround": MotionSpec(6.0, 0.35, 0.4, {
            "ParamAngleX": ((0.0, 0.0), (0.35, 0.0), (1.55, -11.0),
                            (2.2, -11.0), (3.7, 12.0), (4.4, 12.0),
                            (5.55, 0.0), (6.0, 0.0)),
            "ParamAngleY": ((0.0, 0.0), (0.35, 0.0), (1.65, 1.4),
                            (2.2, 1.4), (3.8, -0.8), (4.4, -0.8),
                            (5.55, 0.0), (6.0, 0.0)),
            "ParamAngleZ": ((0.0, 0.0), (0.35, 0.0), (1.75, -1.0),
                            (2.2, -1.0), (3.9, 0.8), (4.4, 0.8),
                            (5.55, 0.0), (6.0, 0.0)),
            "ParamBodyAngleX": ((0.0, 0.0), (0.45, 0.0), (1.8, -1.4),
                                (2.3, -1.4), (4.0, 1.6), (4.5, 1.6),
                                (5.6, 0.0), (6.0, 0.0)),
        }),
    }


def _require(condition: bool, message: str) -> None:
    if not condition:
        raise ValueError(message)


def _number(value: Any) -> bool:
    return type(value) in (int, float) and math.isfinite(value)


def _near(a: float, b: float) -> bool:
    return math.isclose(a, b, rel_tol=0.0, abs_tol=1e-8)


def make_curve(parameter: str, keys: Keyframes) -> JsonObject:
    """Restricted cubic: t handles at 1/3, 2/3; flat endpoint tangents.

    Values follow v0 + (v1-v0)*(3*u*u-2*u*u*u). This is C1 at every
    key (including the Idle seam) and cannot overshoot either keyed value.
    """
    _require(len(keys) >= 2, f"{parameter}: at least two keys required")
    segments: list[float | int] = [float(keys[0][0]), float(keys[0][1])]
    for (t0, v0), (t1, v1) in zip(keys, keys[1:]):
        _require(t1 > t0, f"{parameter}: key times must increase")
        third = (t1 - t0) / 3.0
        segments.extend((1, round(t0 + third, 9), float(v0),
                         round(t1 - third, 9), float(v1), float(t1), float(v1)))
    return {"Target": "Parameter", "Id": parameter, "Segments": segments}


def _beziers(segments: Any) -> list[tuple[tuple[float, float], ...]]:
    """Decode the serialized stream, counting control points as real points."""
    _require(isinstance(segments, list) and len(segments) >= 9,
             "Segments must contain an initial point and at least one cubic")
    _require((len(segments) - 2) % 7 == 0, "Truncated Bezier segment")
    _require(all(_number(value) for value in segments), "Non-finite segment value")
    result = []
    start = (segments[0], segments[1])
    for pos in range(2, len(segments), 7):
        _require(type(segments[pos]) is int and segments[pos] == 1,
                 "Only cubic Bezier segment type 1 is generated")
        points = (start, (segments[pos + 1], segments[pos + 2]),
                  (segments[pos + 3], segments[pos + 4]),
                  (segments[pos + 5], segments[pos + 6]))
        result.append(points)
        start = points[-1]
    return result


def validate_motion(name: str, motion: JsonObject) -> None:
    """Validate serialized Cubism metadata, bounds and C1/neutral boundaries.

    Bounding ALL control values proves the entire cubic stays in range (the
    convex-hull property), rather than relying on samples that can miss peaks.
    """
    spec = motion_specs()[name]
    meta = motion["Meta"]
    curves = motion["Curves"]
    _require(motion.get("Version") == 3, f"{name}: expected Version 3")
    _require(meta["Duration"] == spec.duration and meta["Fps"] == FPS,
             f"{name}: incorrect duration or FPS")
    _require(meta["Loop"] is (name == "Idle"), f"{name}: incorrect Loop")
    _require(meta["AreBeziersRestricted"] is True, f"{name}: restricted cubics required")
    for field in ("FadeInTime", "FadeOutTime"):
        _require(_number(meta[field]) and 0 <= meta[field] <= spec.duration,
                 f"{name}: invalid {field}")
    ids = [curve["Id"] for curve in curves]
    _require(len(ids) == len(set(ids)) and set(ids) == set(spec.tracks),
             f"{name}: duplicate or unexpected parameter curves")
    _require((set(ids) == EYES) if name == "Blink" else not (set(ids) & EYES),
             f"{name}: eye openness belongs exclusively to Blink")
    segment_count = point_count = 0
    for curve in curves:
        parameter = curve["Id"]
        _require(curve["Target"] == "Parameter" and parameter in PARAMETERS,
                 f"{name}: forbidden target or physics parameter {parameter}")
        low, neutral, high = PARAMETERS[parameter]
        cubics = _beziers(curve["Segments"])
        segment_count += len(cubics)
        point_count += 1 + 3 * len(cubics)  # initial + two handles + endpoint
        _require(cubics[0][0] == (0.0, neutral), f"{name}/{parameter}: non-neutral start")
        _require(cubics[-1][-1] == (spec.duration, neutral),
                 f"{name}/{parameter}: non-neutral end or wrong duration")
        for p0, p1, p2, p3 in cubics:
            _require(p0[0] < p1[0] < p2[0] < p3[0],
                     f"{name}/{parameter}: non-monotone control times")
            third = (p3[0] - p0[0]) / 3.0
            _require(_near(p1[0], p0[0] + third) and _near(p2[0], p3[0] - third),
                     f"{name}/{parameter}: unrestricted Bezier handles")
            _require(p0[1] == p1[1] and p2[1] == p3[1],
                     f"{name}/{parameter}: non-flat key tangent")
            _require(all(low <= point[1] <= high for point in (p0, p1, p2, p3)),
                     f"{name}/{parameter}: parameter exceeds [{low}, {high}]")
    expected_counts = {"CurveCount": len(curves), "TotalSegmentCount": segment_count,
                       "TotalPointCount": point_count, "UserDataCount": 0,
                       "TotalUserDataSize": 0}
    _require(not motion.get("UserData"), f"{name}: unexpected events")
    for field, expected in expected_counts.items():
        _require(type(meta[field]) is int and meta[field] == expected,
                 f"{name}: {field} must be {expected}")


def build_motions() -> dict[str, JsonObject]:
    """Pure/deterministic: no filesystem, random seed, clock or exporter."""
    motions = {}
    for name, spec in motion_specs().items():
        curves = [make_curve(parameter, keys) for parameter, keys in spec.tracks.items()]
        counts = [len(_beziers(curve["Segments"])) for curve in curves]
        motion = {
            "Version": 3,
            "Meta": {
                "Duration": spec.duration, "Fps": FPS, "Loop": name == "Idle",
                "AreBeziersRestricted": True,
                "CurveCount": len(curves), "TotalSegmentCount": sum(counts),
                "TotalPointCount": len(curves) + 3 * sum(counts),
                "UserDataCount": 0, "TotalUserDataSize": 0,
                "FadeInTime": spec.fade_in, "FadeOutTime": spec.fade_out,
            },
            "Curves": curves,
            "UserData": [],
        }
        validate_motion(name, motion)
        motions[name] = motion
    return motions


def _unique_object(pairs: list[tuple[str, Any]]) -> JsonObject:
    result: JsonObject = {}
    for key, value in pairs:
        _require(key not in result, f"Duplicate JSON key: {key}")
        result[key] = value
    return result


def _invalid_constant(value: str) -> None:
    raise ValueError(f"Non-standard JSON constant: {value}")


def _load_json(data: bytes) -> JsonObject:
    result = json.loads(data.decode("utf-8-sig"), object_pairs_hook=_unique_object,
                        parse_constant=_invalid_constant)
    _require(isinstance(result, dict), "Expected a JSON object")
    return result


def _updated_motions(model: JsonObject, stem: str) -> JsonObject:
    refs = model.get("FileReferences")
    _require(model.get("Version") == 3 and isinstance(refs, dict),
             "Expected Version 3 with a FileReferences object")
    motions = copy.deepcopy(refs.get("Motions", {}))
    _require(isinstance(motions, dict), "FileReferences.Motions must be an object")
    for name, spec in motion_specs().items():
        filename = f"{stem}.{name.lower()}.motion3.json"
        entries = motions.get(name, [])
        _require(isinstance(entries, list), f"Motions.{name} must be an array")
        owned, others = [], []
        for entry in entries:
            _require(isinstance(entry, dict) and isinstance(entry.get("File"), str),
                     f"Motions.{name}: each entry needs a File string")
            # Do not overwrite/delete alternate takes, sound options, or other groups.
            if Path(entry["File"].replace("\\", "/")).as_posix().casefold() == filename.casefold():
                owned.append(entry)
            else:
                others.append(entry)
        if not owned:
            owned.append({})
        for entry in owned:
            entry.update(File=filename, FadeInTime=spec.fade_in, FadeOutTime=spec.fade_out)
        motions[name] = owned + others  # generated take is index 0, never duplicate on rerun
    return motions


def _object_spans(text: str, start: int) -> tuple[dict[str, tuple[int, int]], int]:
    """Locate direct member values in already validated JSON without reformatting it."""
    decoder = json.JSONDecoder()
    skip = lambda pos: re.match(r"\s*", text[pos:]).end() + pos
    pos = skip(start + 1)
    spans = {}
    while text[pos] != "}":
        key, end = decoder.raw_decode(text, pos)
        value_start = skip(skip(end) + 1)  # colon, then whitespace
        _, value_end = decoder.raw_decode(text, value_start)
        spans[key] = (value_start, value_end)
        pos = skip(value_end)
        if text[pos] == ",":
            pos = skip(pos + 1)
    return spans, pos


def _patch_model(data: bytes, model: JsonObject, motions: JsonObject) -> bytes:
    """Replace only the Motions value; preserve all bytes outside it, including BOM."""
    if model["FileReferences"].get("Motions") == motions:
        return data
    text = data.decode("utf-8-sig")
    root_start = len(text) - len(text.lstrip())
    root, _ = _object_spans(text, root_start)
    refs_start, _ = root["FileReferences"]
    refs, closing = _object_spans(text, refs_start)
    newline = "\r\n" if "\r\n" in text else "\n"
    match = re.search(r'\n([ \t]+)"', text)
    step = match.group(1) if match else "  "

    def indentation(pos: int) -> str:
        line = text[text.rfind("\n", 0, pos) + 1:pos]
        return re.match(r"[ \t]*", line).group()

    def render(base: str) -> str:
        return json.dumps(motions, ensure_ascii=False, indent=step,
                          allow_nan=False).replace("\n", newline + base)

    if "Motions" in refs:
        start, end = refs["Motions"]
        patched = text[:start] + render(indentation(start)) + text[end:]
    else:
        # Insert the missing member without serializing the other FileReferences.
        start = closing
        while start > refs_start + 1 and text[start - 1].isspace():
            start -= 1
        parent_indent = indentation(refs_start)
        base = parent_indent + step
        addition = ("," if refs else "") + newline + base + '"Motions": ' + render(base)
        if "\n" not in text[start:closing]:
            addition += newline + parent_indent
        patched = text[:start] + addition + text[start:]
    output = (codecs.BOM_UTF8 if data.startswith(codecs.BOM_UTF8) else b"") + patched.encode("utf-8")
    expected = copy.deepcopy(model)
    expected["FileReferences"]["Motions"] = motions
    _require(_load_json(output) == expected, "Model patch changed an unrelated field")
    return output


def _read_target(path: Path) -> bytes | None:
    _require(not path.is_symlink(), f"Refusing to replace a symbolic link: {path}")
    if not path.exists():
        return None
    _require(path.is_file(), f"Expected a regular file: {path}")
    return path.read_bytes()


def _check_parameter_catalog(directory: Path, model: JsonObject,
                             motions: dict[str, JsonObject]) -> None:
    """Use an available display catalog, but allow a model3-only staging folder."""
    reference = model["FileReferences"].get("DisplayInfo")
    if reference is None:
        return
    _require(isinstance(reference, str) and bool(reference), "Invalid DisplayInfo reference")
    catalog_path = (directory / reference).resolve()
    _require(catalog_path.is_relative_to(directory), "DisplayInfo must stay inside --directory")
    if not catalog_path.is_file():
        print("NOTE: DisplayInfo not present; using the checked-in parameter allow-list.")
        return
    catalog = _load_json(catalog_path.read_bytes())
    parameters = catalog.get("Parameters")
    _require(isinstance(parameters, list), "DisplayInfo.Parameters must be an array")
    known = {item.get("Id") for item in parameters if isinstance(item, dict)}
    used = {curve["Id"] for motion in motions.values() for curve in motion["Curves"]}
    _require(used <= known, f"Model is missing parameters: {', '.join(sorted(used - known))}")


@dataclass(frozen=True)
class FileUpdate:
    path: Path
    before: bytes | None
    after: bytes

    @property
    def changed(self) -> bool:
        return self.before != self.after


def plan_updates(directory: Path) -> tuple[list[FileUpdate], dict[str, JsonObject]]:
    """Read/validate everything before making any changes. No fallback to deploy."""
    directory = directory.expanduser().resolve()
    _require(directory.is_dir(), f"Directory does not exist: {directory}")
    models = sorted(directory.glob(f"*{MODEL_SUFFIX}"))
    _require(len(models) == 1, "--directory must contain exactly one *.model3.json")
    model_path = models[0]
    model_data = _read_target(model_path)
    _require(model_data is not None, f"Missing model: {model_path}")
    model = _load_json(model_data)
    stem = model_path.name[:-len(MODEL_SUFFIX)]
    _require(bool(stem), "Model filename must have a non-empty prefix")
    references = _updated_motions(model, stem)
    model_output = _patch_model(model_data, model, references)
    motions = build_motions()
    _check_parameter_catalog(directory, model, motions)
    updates = []
    for name, motion in motions.items():
        path = directory / f"{stem}.{name.lower()}.motion3.json"
        data = (json.dumps(motion, ensure_ascii=False, indent=2, allow_nan=False) + "\n").encode("utf-8")
        # Check the serialized form, not only the in-memory keyframe definition.
        validate_motion(name, _load_json(data))
        updates.append(FileUpdate(path, _read_target(path), data))
    # Publish references last so new filenames are never referenced before creation.
    updates.append(FileUpdate(model_path, model_data, model_output))
    return updates, motions


def write_updates(updates: list[FileUpdate]) -> int:
    """Stage all changed bytes, then atomically replace each file (model last).

    This is per-file atomicity, not a cross-file transaction. An OS-level failure
    during replacement can leave a partial set; rerunning the command repairs it.
    """
    staged: list[tuple[FileUpdate, Path]] = []
    try:
        for update in updates:
            _require(_read_target(update.path) == update.before,
                     f"File changed during generation; retry: {update.path}")
        for update in updates:
            if not update.changed:
                continue
            with tempfile.NamedTemporaryFile(prefix=f".{update.path.name}.", suffix=".tmp",
                                             dir=update.path.parent, delete=False) as stream:
                temp_path = Path(stream.name)
                staged.append((update, temp_path))
                stream.write(update.after)
                stream.flush()
                os.fsync(stream.fileno())
            if update.before is not None:
                os.chmod(temp_path, update.path.stat().st_mode)
        for update in updates:
            _require(_read_target(update.path) == update.before,
                     f"File changed during staging; retry: {update.path}")
        for update, temp_path in staged:
            os.replace(temp_path, update.path)
        return len(staged)
    finally:
        for _, temp_path in staged:
            temp_path.unlink(missing_ok=True)


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--directory", type=Path, required=True,
                        help="existing model directory; required, never inferred from cwd")
    parser.add_argument("--check", action="store_true",
                        help="read-only verification; exit 1 if any managed output is missing/outdated")
    args = parser.parse_args(argv)
    try:
        updates, motions = plan_updates(args.directory)
        changed = sum(update.changed for update in updates)
        if not args.check:
            write_updates(updates)
        for name, motion in motions.items():
            meta = motion["Meta"]
            print(f"{name:10} {meta['Duration']:4.1f}s  loop={str(meta['Loop']):5}  "
                  f"curves={meta['CurveCount']:2} segments={meta['TotalSegmentCount']:3} "
                  f"points={meta['TotalPointCount']:3}")
        for update in updates:
            state = ("OUTDATED" if args.check else "UPDATED") if update.changed else "UNCHANGED"
            print(f"{state:9} {update.path.name}")
        if args.check:
            print(f"CHECK {'FAIL' if changed else 'PASS'}: {changed} of 7 managed files differ; no writes.")
            return 1 if changed else 0
        print(f"OK: {changed} of 7 managed files updated in {args.directory.expanduser().resolve()}")
        return 0
    except (OSError, ValueError) as exc:
        parser.exit(2, f"build_motions: {exc}\n")


if __name__ == "__main__":
    raise SystemExit(main())
