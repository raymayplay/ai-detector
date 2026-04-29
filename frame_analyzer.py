"""
Frame-level video analysis for AI detection.

Extracts a handful of frames using ffmpeg and computes visual statistics
that often differ between AI-generated and real-world video:

  - Color saturation uniformity   (AI tends to be uniformly saturated)
  - Edge density variance         (AI often lacks fine natural detail)
  - Temporal smoothness           (AI motion is often unnaturally smooth or jittery)
  - High-frequency content        (Laplacian variance — AI often lacks grain)
  - Color palette concentration   (AI tends to use a narrower palette)

These are heuristics, not a trained model. They contribute to a combined score.
"""
import os
import subprocess
import tempfile
import shutil
from typing import Optional

try:
    import numpy as np
    from PIL import Image, ImageFilter
    _LIBS_OK = True
except ImportError:
    _LIBS_OK = False


def extract_frames(video_path: str, num_frames: int = 10, max_dim: int = 320) -> list:
    """Extract evenly spaced frames from a video. Returns list of PIL Images."""
    if not _LIBS_OK:
        return []

    tmpdir = tempfile.mkdtemp(prefix="frames_")
    try:
        # Get duration
        probe = subprocess.run(
            ['ffprobe', '-v', 'quiet', '-show_entries', 'format=duration',
             '-of', 'default=noprint_wrappers=1:nokey=1', video_path],
            capture_output=True, text=True, timeout=15
        )
        try:
            duration = float(probe.stdout.strip())
        except (ValueError, AttributeError):
            duration = 0.0

        if duration <= 0:
            return []

        # Cap total work: never analyze more than first 60 seconds
        analyze_until = min(duration, 60.0)
        # Pick 'num_frames' evenly spaced timestamps inside the first analyze_until seconds
        step = max(analyze_until / (num_frames + 1), 0.5)
        timestamps = [round(step * (i + 1), 2) for i in range(num_frames)]

        frames = []
        for i, ts in enumerate(timestamps):
            out_path = os.path.join(tmpdir, f"f{i:03d}.jpg")
            cmd = [
                'ffmpeg', '-loglevel', 'error', '-y',
                '-ss', str(ts), '-i', video_path,
                '-frames:v', '1',
                '-vf', f'scale={max_dim}:-1',
                out_path,
            ]
            try:
                subprocess.run(cmd, capture_output=True, timeout=10)
            except subprocess.TimeoutExpired:
                continue
            if os.path.isfile(out_path):
                try:
                    img = Image.open(out_path).convert('RGB')
                    img.load()
                    frames.append(img)
                except Exception:
                    pass

        return frames
    finally:
        shutil.rmtree(tmpdir, ignore_errors=True)


def _laplacian_variance(gray: 'np.ndarray') -> float:
    """Approximate Laplacian variance (a measure of high-frequency detail / grain)."""
    g = gray.astype(np.float32)
    lap = (
        -4 * g
        + np.roll(g, 1, axis=0) + np.roll(g, -1, axis=0)
        + np.roll(g, 1, axis=1) + np.roll(g, -1, axis=1)
    )
    return float(lap.var())


def _saturation(rgb: 'np.ndarray') -> float:
    """Mean saturation in [0, 1] using HSV-like calculation."""
    r = rgb[..., 0].astype(np.float32) / 255.0
    g = rgb[..., 1].astype(np.float32) / 255.0
    b = rgb[..., 2].astype(np.float32) / 255.0
    mx = np.max(rgb, axis=-1).astype(np.float32) / 255.0
    mn = np.min(rgb, axis=-1).astype(np.float32) / 255.0
    sat = np.where(mx > 0, (mx - mn) / np.maximum(mx, 1e-6), 0.0)
    return float(sat.mean())


def _edge_density(gray: 'np.ndarray') -> float:
    """Fraction of pixels considered 'edges' via simple gradient threshold."""
    g = gray.astype(np.float32)
    dx = np.abs(np.diff(g, axis=1))
    dy = np.abs(np.diff(g, axis=0))
    edges_x = (dx > 25).mean()
    edges_y = (dy > 25).mean()
    return float((edges_x + edges_y) / 2.0)


def _palette_concentration(rgb: 'np.ndarray') -> float:
    """
    Concentration of the color histogram in the top buckets.
    Higher = narrower palette (typical of AI generation).
    Range roughly 0..1.
    """
    quant = (rgb // 32).astype(np.int32)  # 8 bins per channel → 512 buckets
    keys = quant[..., 0] * 64 + quant[..., 1] * 8 + quant[..., 2]
    flat = keys.flatten()
    counts = np.bincount(flat, minlength=512).astype(np.float32)
    counts.sort()
    total = counts.sum()
    if total <= 0:
        return 0.0
    top16 = counts[-16:].sum()
    return float(top16 / total)


def analyze_frames(video_path: str) -> dict:
    """
    Run frame-level analysis on a video and return:
      - factors:   list of human-readable AI-suggesting findings
      - score:     additional score contribution in [0, 1]
      - details:   raw measurements for debugging
    """
    result = {
        "factors": [],
        "authenticity_factors": [],
        "score": 0.0,
        "details": {},
    }

    if not _LIBS_OK:
        return result

    frames = extract_frames(video_path, num_frames=10, max_dim=320)
    if len(frames) < 4:
        return result

    arrays = [np.asarray(f) for f in frames]
    grays = [np.asarray(f.convert('L')) for f in frames]

    # Per-frame measurements
    sats = [_saturation(a) for a in arrays]
    edges = [_edge_density(g) for g in grays]
    laps = [_laplacian_variance(g) for g in grays]
    palette = [_palette_concentration(a) for a in arrays]

    # Temporal: mean absolute difference between consecutive frames (resized aligned)
    diffs = []
    for i in range(1, len(grays)):
        a, b = grays[i - 1].astype(np.int16), grays[i].astype(np.int16)
        diffs.append(float(np.abs(a - b).mean()))

    sat_mean = float(np.mean(sats))
    sat_std = float(np.std(sats))
    edge_mean = float(np.mean(edges))
    edge_std = float(np.std(edges))
    lap_mean = float(np.mean(laps))
    palette_mean = float(np.mean(palette))
    diff_mean = float(np.mean(diffs)) if diffs else 0.0
    diff_std = float(np.std(diffs)) if diffs else 0.0

    result["details"] = {
        "frames_analyzed": len(frames),
        "saturation_mean": round(sat_mean, 4),
        "saturation_std": round(sat_std, 4),
        "edge_mean": round(edge_mean, 4),
        "edge_std": round(edge_std, 4),
        "laplacian_mean": round(lap_mean, 2),
        "palette_top16_share": round(palette_mean, 4),
        "interframe_diff_mean": round(diff_mean, 3),
        "interframe_diff_std": round(diff_std, 3),
    }

    score = 0.0

    # AI tells:

    # 1. Very narrow palette + high uniform saturation = stylized look
    if palette_mean > 0.55 and sat_mean > 0.35:
        score += 0.20
        result["factors"].append(
            f"Narrow color palette with high saturation (palette={palette_mean:.2f}, sat={sat_mean:.2f})"
        )

    # 2. Very low high-frequency detail = lacks natural grain (AI tends to be smooth)
    if lap_mean < 80:
        score += 0.20
        result["factors"].append(
            f"Very low natural detail/grain (laplacian variance={lap_mean:.0f})"
        )
    elif lap_mean > 600:
        result["authenticity_factors"].append(
            f"Strong natural detail/grain (laplacian variance={lap_mean:.0f})"
        )

    # 3. Suspicious motion characteristics: too smooth or weirdly inconsistent
    if 0 < diff_mean < 4:
        score += 0.15
        result["factors"].append(
            f"Very smooth motion across frames (mean diff={diff_mean:.2f})"
        )
    if diff_std > diff_mean * 1.5 and diff_mean > 2:
        score += 0.10
        result["factors"].append(
            f"Inconsistent motion / temporal flicker (diff std={diff_std:.2f})"
        )

    # 4. Edge density unusually uniform across frames (AI tends to be consistent)
    if edge_std < 0.005 and edge_mean > 0:
        score += 0.10
        result["factors"].append(
            f"Unnaturally consistent edge density across frames"
        )

    # 5. Very high palette concentration alone (single tone scenes)
    if palette_mean > 0.7:
        score += 0.10
        result["factors"].append(
            f"Extremely concentrated color palette ({palette_mean:.0%} of pixels in 16 buckets)"
        )

    # Soft authenticity hints
    if 8 < diff_mean < 40 and 0.05 < edge_mean < 0.4 and lap_mean > 200:
        result["authenticity_factors"].append(
            "Natural motion, detail, and edge variation across frames"
        )

    result["score"] = round(min(score, 0.7), 4)
    return result
