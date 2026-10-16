"""Stabilize a box's time-lapse on its QR label: translation only, no zoom.

The robot's jitter is the carriage stopping a belt tooth or more off its usual position, so
every frame of a box is the same view shifted sideways by a whole number of ~2 mm steps.
The QR label glued to the vessel is static in the world, high contrast and identical in
every frame, so its position in a frame IS the camera offset. Matching it frame by frame
and shifting each frame back is exact for that kind of motion, where generic stabilization
(vid.stab) fits a whole-frame motion model to a mostly transparent, partly changing scene,
smooths the path, and zooms (changing the image scale by an unrecorded amount).

    stabilize_experiment(folder, "out.mp4")      # all of the below, plus stabilization.json
    offsets, scores, info = measure_offsets(paths)   # (dx, dy) per frame, sub-pixel
    write_video(paths, offsets, "out.mp4")       # shift, crop to the common area, encode once

stabilization.json, written into the experiment folder beside its frames, records each frame's
label offset keyed by filename, so root-tracking can stabilize the same frames exactly.

Frames are read from disk one at a time: a box of 3000x3000 frames is ~3 GB in memory.

Parallax: the label sits nearer the camera than the seeds, so a sideways camera move shifts
it further in the image. Aligning the label exactly leaves the seeds off by the difference
(~9 % of each jump on the College Station rig). write_video(parallax=...) scales the
correction to the seed plane instead. Measured on boxes 14-16 of 20260819162507_1_8: seed
shift / label shift = 0.906 / 0.915 / 0.901, so PARALLAX_COLLEGE_STATION = 0.907. With it,
the seed bodies held to 0.5-0.8 px sd (max 3 px) over 319 frames, against ~50 px sd and
~110 px of slow drift with vid.stab. It depends on the rig's working distance and vessel,
so another rig needs its own value.

Python 3.7-compatible (the processing container).
"""
import json
import os
import subprocess

import cv2
import numpy as np

PARALLAX_COLLEGE_STATION = 0.907   # seed-plane shift / label shift; see module docstring
OFFSETS_NAME = "stabilization.json"
OFFSETS_FORMAT = "qr-stabilization/1"
IMAGE_EXTENSIONS = (".png", ".jpg", ".jpeg", ".bmp", ".tif", ".tiff")


def locate_label(gray, margin=40):
    """(x0, y0, x1, y1) of the QR code plus a margin, or None if no QR is found."""
    pts = None
    if hasattr(cv2, "QRCodeDetector"):
        ok, found = cv2.QRCodeDetector().detect(gray)
        if ok and found is not None:
            pts = found.reshape(-1, 2)
    if pts is None:
        try:   # older OpenCV in the container: fall back to zbar, which the sorter uses
            from pyzbar.pyzbar import decode, ZBarSymbol
            hits = decode(gray, symbols=[ZBarSymbol.QRCODE])
            if hits:
                r = hits[0].rect
                pts = np.array([[r.left, r.top], [r.left + r.width, r.top + r.height]], float)
        except ImportError:
            pass
    if pts is None:
        return None
    h, w = gray.shape
    x0, y0 = np.floor(pts.min(0)).astype(int) - margin
    x1, y1 = np.ceil(pts.max(0)).astype(int) + margin
    return max(x0, 0), max(y0, 0), min(x1, w), min(y1, h)


def prepare(gray, binarize):
    """Image to match on. binarize: Otsu threshold, then a light blur so the match peak
    stays smooth enough for sub-pixel refinement (a hard 0/255 edge quantizes it)."""
    if not binarize:
        return gray
    _, bw = cv2.threshold(gray, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
    return cv2.GaussianBlur(bw, (0, 0), 1.5)


def _subpixel(r, i, j):
    """Parabolic refinement of a correlation peak at (row i, col j)."""
    def one(a, b, c):
        d = a - 2 * b + c
        return 0.0 if d == 0 else 0.5 * (a - c) / d
    di = one(r[i - 1, j], r[i, j], r[i + 1, j]) if 0 < i < r.shape[0] - 1 else 0.0
    dj = one(r[i, j - 1], r[i, j], r[i, j + 1]) if 0 < j < r.shape[1] - 1 else 0.0
    return i + di, j + dj


def _gray(path):
    g = cv2.imread(str(path), cv2.IMREAD_GRAYSCALE)
    if g is None:
        raise ValueError("unreadable image: %s" % path)
    return g


def widen_to(search, shape):
    """Search reaches to try in turn: the normal one, double, then the whole frame."""
    return [search, 2 * search, max(shape)]


def _match(g, tmpl, box, around, reach, binarize):
    """((dx, dy), score) of the template within `reach` px of the box shifted by `around`,
    or None if the peak sits on a search limit (the label may lie beyond it). A window
    edge that is the frame's own edge doesn't count: widening can't help there."""
    x0, y0, x1, y1 = box
    h, w = g.shape
    cx, cy = int(round(around[0])), int(round(around[1]))
    sx0, sy0 = max(x0 + cx - reach, 0), max(y0 + cy - reach, 0)
    sx1, sy1 = min(x1 + cx + reach, w), min(y1 + cy + reach, h)
    if sx1 - sx0 < tmpl.shape[1] or sy1 - sy0 < tmpl.shape[0]:
        return None
    win = prepare(g[sy0:sy1, sx0:sx1], binarize).astype(np.float32)
    r = cv2.matchTemplate(win, tmpl, cv2.TM_CCOEFF_NORMED)
    _, score, _, (j, i) = cv2.minMaxLoc(r)
    limit = ((i == 0 and sy0 > 0) or (i == r.shape[0] - 1 and sy1 < h) or
             (j == 0 and sx0 > 0) or (j == r.shape[1] - 1 and sx1 < w))
    if limit:
        return None
    fi, fj = _subpixel(r, i, j)
    return (sx0 + fj - x0, sy0 + fi - y0), score


def measure_offsets(paths, ref_index=1, search=500, binarize=True, min_score=0.5,
                    jump_px=200, log=print):
    """Per-frame (dx, dy) of the QR label, re-referenced to the median position.

    paths: the box's frames, in time order. ref_index: frame the
    template is cut from -- not frame 0, the first cycle, whose light warm-up and cold
    calibration make it atypical. Each frame is searched within `search` px of the previous
    match; a miss (score below min_score, or the peak on a search limit) retries at double
    the reach, then the whole frame. A frame still unmatched holds the previous offset.
    Widened searches, unmatched frames and frame-to-frame jumps over jump_px are reported
    through `log`, since they usually mean the box itself was moved (camera jitter jumped at
    most ~120 px between frames on the College Station rig).
    Returns (offsets Nx2, scores N, info) with info = {"widened", "rejected", "jumps"}: frame
    indices that needed a wider search, weren't matched, or jumped over jump_px.
    """
    ref_index = min(ref_index, len(paths) - 1)
    ref = _gray(paths[ref_index])
    box = locate_label(ref)
    if box is None:
        raise ValueError("no QR label found in reference frame %d" % ref_index)
    x0, y0, x1, y1 = box
    tmpl = prepare(ref, binarize)[y0:y1, x0:x1].astype(np.float32)
    offsets, scores = np.full((len(paths), 2), np.nan), np.zeros(len(paths))
    last = (0.0, 0.0)          # search around the previous match, so after a box move only
    widened, rejected = [], [] # the first moved frame needs a wider search
    for k, path in enumerate(paths):
        g = _gray(path)
        for level, reach in enumerate(widen_to(search, g.shape)):
            hit = _match(g, tmpl, (x0, y0, x1, y1), last, reach, binarize)
            if hit is not None and hit[1] >= min_score:
                break
        else:
            hit = None
        if hit is None:
            rejected.append(k)
            continue
        offsets[k], scores[k] = hit
        last = tuple(offsets[k])
        if level:
            widened.append((k, int(round(offsets[k, 0])), int(round(offsets[k, 1]))))
    good = ~np.isnan(offsets[:, 0])
    if not good.any():
        raise ValueError("QR label not matched in any frame")
    if widened:
        log("qr_stabilize: %d frame(s) needed a wider search -- a moved box? "
            "(frame, dx, dy): %s" % (len(widened), widened[:20]))
    if rejected:
        log("qr_stabilize: WARNING label not found in %d frame(s), held the previous offset: "
            "%s" % (len(rejected), rejected[:50]))
    steps = np.abs(np.diff(offsets[good], axis=0)).max(axis=1)
    jumps = [int(np.where(good)[0][i + 1]) for i in np.where(steps > jump_px)[0]]
    if jumps:
        log("qr_stabilize: label jumped more than %d px at frame(s) %s -- more than camera "
            "jitter; check whether the box was moved" % (jump_px, jumps[:20]))
    for k in range(len(offsets)):   # hold the last good offset over rejected frames
        if not good[k]:
            prev = np.where(good[:k])[0]
            offsets[k] = offsets[prev[-1]] if len(prev) else offsets[np.where(good)[0][0]]
    offsets -= np.median(offsets[good], axis=0)   # no single frame becomes the baseline
    info = {"widened": [w[0] for w in widened], "rejected": rejected, "jumps": jumps}
    return offsets, scores, info


def common_crop(shape, offsets):
    """(x0, y0, x1, y1) valid in every shifted frame, so the output never shows a border."""
    h, w = shape[:2]
    dx, dy = offsets[:, 0], offsets[:, 1]
    x0, y0 = int(np.ceil(max(dx.max(), 0))), int(np.ceil(max(dy.max(), 0)))
    x1, y1 = int(np.floor(w + min(dx.min(), 0))), int(np.floor(h + min(dy.min(), 0)))
    x1, y1 = x0 + (x1 - x0) // 2 * 2, y0 + (y1 - y0) // 2 * 2   # even, for yuv420p
    return x0, y0, x1, y1


def shift(frame, dx, dy):
    """Move the content back by (dx, dy): translation only, sub-pixel, no scaling."""
    m = np.float32([[1, 0, -dx], [0, 1, -dy]])
    return cv2.warpAffine(frame, m, (frame.shape[1], frame.shape[0]), flags=cv2.INTER_LINEAR)


def write_video(paths, offsets, out_path, fps=15, crf=24, parallax=1.0):
    """Shift each full-colour frame, crop to the common area and encode once (same codec
    settings as the pipeline's unstabilized video). offsets are the label's, from
    measure_offsets(); parallax scales them to the plane that should hold still (1.0 = the
    label itself)."""
    offsets = np.asarray(offsets) * parallax
    proc, crop = None, None
    for k, path in enumerate(paths):
        f = cv2.imread(str(path))
        if crop is None:
            crop = common_crop(f.shape, offsets)
            x0, y0, x1, y1 = crop
            proc = subprocess.Popen(
                ["ffmpeg", "-v", "error", "-y", "-f", "rawvideo", "-pix_fmt", "bgr24",
                 "-s", "%dx%d" % (x1 - x0, y1 - y0), "-r", str(fps), "-i", "-",
                 "-c:v", "libx264", "-preset", "faster", "-threads", "4", "-crf", str(crf), "-pix_fmt", "yuv420p", out_path],
                stdin=subprocess.PIPE)
        s = shift(f, offsets[k, 0], offsets[k, 1])
        proc.stdin.write(np.ascontiguousarray(s[y0:y1, x0:x1]).tobytes())
    proc.stdin.close()
    if proc.wait() != 0:
        raise RuntimeError("ffmpeg failed writing " + out_path)
    return crop


def write_offsets(folder, names, offsets, scores, info, parallax):
    """Write stabilization.json into an experiment folder, keyed by frame filename.

    Stores the RAW label offsets plus the parallax factor separately, so a reader can apply its
    own factor without re-measuring. Keyed by name, not position, so a reader can tell when the
    frames on disk no longer match.
    """
    rec = {
        "format": OFFSETS_FORMAT,
        "method": "qr-label template match, translation only",
        "parallax": parallax,
        "offsets_are": "label offset (px) from the median position; to stabilize, shift each "
                       "frame back by offset * parallax",
        "reference_frame": names[min(1, len(names) - 1)],
        "frames": {n: [round(float(o[0]), 3), round(float(o[1]), 3), round(float(sc), 4)]
                   for n, o, sc in zip(names, offsets, scores)},
        "widened": [names[k] for k in info["widened"]],
        "rejected": [names[k] for k in info["rejected"]],
        "jumps": [names[k] for k in info["jumps"]],
    }
    path = os.path.join(folder, OFFSETS_NAME)
    with open(path, "w") as f:
        json.dump(rec, f, indent=1)
    return path


def stabilize_experiment(folder, out_path, parallax=PARALLAX_COLLEGE_STATION, fps=15, crf=24,
                         log=print):
    """Measure a finished experiment's frames, write stabilization.json beside them, and render
    the stabilized video to out_path. Raises ValueError when there's no usable label (the
    caller falls back to vid.stab)."""
    names = sorted(n for n in os.listdir(folder)
                   if n.lower().endswith(IMAGE_EXTENSIONS) and not n.startswith("."))
    if len(names) < 2:
        raise ValueError("fewer than 2 frames in %s" % folder)
    paths = [os.path.join(folder, n) for n in names]
    offsets, scores, info = measure_offsets(paths, log=log)
    write_offsets(folder, names, offsets, scores, info, parallax)
    write_video(paths, offsets, out_path, fps=fps, crf=crf, parallax=parallax)
    return info
