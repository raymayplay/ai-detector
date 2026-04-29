import argparse
import json
import os
import re
import subprocess
import sys
from typing import Optional

try:
    from frame_analyzer import analyze_frames
    _FRAME_ANALYSIS_AVAILABLE = True
except ImportError:
    _FRAME_ANALYSIS_AVAILABLE = False


KNOWN_AI_ENCODER_SIGNATURES = [
    'sora', 'runway', 'pika', 'kling', 'luma', 'dream machine',
    'midjourney', 'stable video', 'animatediff', 'modelscope',
    'gen-2', 'gen-3', 'gen2', 'gen3', 'wan2', 'cogvideo',
    'hunyuanvideo', 'mochi', 'ltx-video', 'veo', 'imagen video',
    'haiper', 'genmo',
]

_BL = r'(?<![a-z])'  # boundary: not preceded by a letter (digits/_/-/. all OK)
_BR = r'(?![a-z])'   # boundary: not followed by a letter

AI_FILENAME_PATTERNS = [
    rf'{_BL}ai[_\-\s]?generated{_BR}',
    rf'{_BL}deepfake{_BR}',
    rf'{_BL}synthetic{_BR}',
    rf'{_BL}sora{_BR}',
    rf'{_BL}runway{_BR}',
    rf'{_BL}pika{_BR}',
    rf'{_BL}kling{_BR}',
    rf'{_BL}midjourney{_BR}',
    rf'{_BL}stable[_\-\s]?diffusion{_BR}',
    rf'{_BL}veo{_BR}',
    rf'{_BL}imagen{_BR}',
    rf'{_BL}dall[_\-\s]?e{_BR}',
    rf'{_BL}generative{_BR}',
    rf'{_BL}llm[_\-\s]?video{_BR}',
]


def probe_video_metadata(video_path: str) -> dict:
    """Run ffprobe to extract encoder, codec, and stream metadata."""
    try:
        cmd = [
            'ffprobe', '-v', 'quiet', '-print_format', 'json',
            '-show_format', '-show_streams', video_path
        ]
        result = subprocess.run(
            cmd, capture_output=True, text=True, timeout=30
        )
        if result.returncode != 0:
            return {}
        return json.loads(result.stdout)
    except (subprocess.TimeoutExpired, json.JSONDecodeError, FileNotFoundError, OSError):
        return {}


def analyze_video_characteristics(video_path: str, debug: bool = False) -> dict:
    """
    Analyze a video file for AI-generation indicators using metadata inspection.

    Strategy:
      1. Inspect ffprobe encoder/comment/handler metadata for known AI tool signatures.
       2. Inspect filename for explicit AI markers (word-boundary matching).
       3. Combine signals and report a confidence level.

    We deliberately do NOT use file size, file extension, or upload time —
    those produce false positives on legitimate authentic media.
    """

    file_size_mb = round(os.path.getsize(video_path) / (1024 * 1024), 2)

    result = {
        "file": os.path.basename(video_path),
        "size_mb": file_size_mb,
        "ai_score": 0.0,
        "is_ai_generated": False,
        "confidence": "Low",
        "detection_factors": [],
        "authenticity_factors": [],
    }

    score = 0.0
    factors = result["detection_factors"]
    auth_factors = result["authenticity_factors"]

    # ---- Factor 1: Encoder / metadata signatures (strongest signal) ----
    metadata = probe_video_metadata(video_path)
    metadata_text_parts = []

    if metadata:
        fmt = metadata.get('format', {}) or {}
        tags = fmt.get('tags', {}) or {}
        for key in ('encoder', 'comment', 'description', 'title', 'creation_tool', 'software', 'handler_name'):
            value = tags.get(key)
            if value:
                metadata_text_parts.append(str(value).lower())

        for stream in metadata.get('streams', []) or []:
            stream_tags = stream.get('tags', {}) or {}
            for key in ('encoder', 'comment', 'handler_name', 'title'):
                value = stream_tags.get(key)
                if value:
                    metadata_text_parts.append(str(value).lower())

    metadata_blob = ' | '.join(metadata_text_parts)

    matched_signatures = [
        sig for sig in KNOWN_AI_ENCODER_SIGNATURES if sig in metadata_blob
    ]
    if matched_signatures:
        score += 0.85
        factors.append(
            f"AI tool signature found in video metadata: {', '.join(matched_signatures)}"
        )
    elif metadata_blob:
        # Found real encoder info that doesn't match AI tools
        # Common camera/phone/editor encoders push toward authentic
        camera_markers = ['lavf', 'x264', 'x265', 'h264', 'hevc', 'apple', 'gopro',
                          'sony', 'canon', 'nikon', 'samsung', 'iphone', 'android',
                          'adobe', 'davinci', 'premiere', 'finalcut', 'imovie', 'shotcut']
        if any(marker in metadata_blob for marker in camera_markers):
            auth_factors.append("Encoder matches a standard camera or editor")

    # ---- Factor 2: Filename markers (word-boundary, explicit only) ----
    filename = os.path.basename(video_path).lower()
    filename_matches = []
    for pattern in AI_FILENAME_PATTERNS:
        if re.search(pattern, filename):
            match = re.search(pattern, filename)
            if match:
                filename_matches.append(match.group(0))

    if filename_matches:
        score += 0.45
        factors.append(
            f"Filename contains explicit AI marker: {', '.join(set(filename_matches))}"
        )

    # ---- Factor 3: Lack of standard metadata can be a weak indicator ----
    if not metadata_blob and not matched_signatures:
        # Many AI tools strip metadata. But so do some converters.
        # Treat as a very weak indicator only.
        score += 0.05
        factors.append("Video metadata is missing or stripped (weak indicator)")

    # ---- Factor 4: Visual frame analysis ----
    if _FRAME_ANALYSIS_AVAILABLE:
        try:
            frame_result = analyze_frames(video_path)
            score += frame_result.get("score", 0.0)
            for f in frame_result.get("factors", []):
                factors.append(f"Visual: {f}")
            for f in frame_result.get("authenticity_factors", []):
                auth_factors.append(f"Visual: {f}")
            result["frame_details"] = frame_result.get("details", {})
        except Exception as e:
            if debug:
                print(f"[DEBUG] Frame analysis failed: {e}")

    # ---- Final scoring ----
    score = min(score, 1.0)
    result["ai_score"] = round(score, 4)

    # Threshold: be conservative. Require strong evidence.
    # 0.65+ = AI generated, 0.35-0.64 = uncertain (we say authentic), <0.35 = authentic
    if score >= 0.65:
        result["is_ai_generated"] = True
        result["confidence"] = "High" if score >= 0.85 else "Medium"
    else:
        result["is_ai_generated"] = False
        if score >= 0.35:
            result["confidence"] = "Low"
        elif auth_factors:
            result["confidence"] = "High"
        else:
            result["confidence"] = "Medium"

    if not factors:
        factors.append("No AI markers detected")

    if debug:
        print(f"[DEBUG] Metadata blob: {metadata_blob!r}")
        print(f"[DEBUG] Final score: {result['ai_score']}")
        print(f"[DEBUG] Threshold: 0.65")
        print(f"[DEBUG] Is AI: {result['is_ai_generated']}")
        print(f"[DEBUG] Confidence: {result['confidence']}")

    return result


def detect_video_local(video_path: str, save_json: Optional[str] = None, debug: bool = False) -> int:
    """Local video analysis without external APIs or services."""

    if not os.path.isfile(video_path):
        print(f"File not found: {video_path}")
        return 2

    print(f"\nAnalyzing video: {os.path.basename(video_path)}")
    print("=" * 60)

    result = analyze_video_characteristics(video_path, debug=debug)

    print(f"\nDETECTION RESULTS:")
    print(f"   File: {result['file']}")
    print(f"   Size: {result['size_mb']} MB")
    print(f"   AI Score: {result['ai_score']:.4f} (threshold: 0.65)")
    print(f"   Confidence: {result['confidence']}")
    print(f"   Status: {'AI GENERATED' if result['is_ai_generated'] else 'AUTHENTIC'}")

    if result["detection_factors"]:
        print(f"\nDetection Factors:")
        for factor in result["detection_factors"]:
            print(f"   - {factor}")

    if result["authenticity_factors"]:
        print(f"\nAuthenticity Indicators:")
        for factor in result["authenticity_factors"]:
            print(f"   - {factor}")

    print("=" * 60)

    if save_json:
        try:
            with open(save_json, "w", encoding="utf-8") as fh:
                json.dump(result, fh, indent=2)
            print(f"\nSaved result to {save_json}")
        except Exception as e:
            print(f"Failed to save JSON: {e}")

    return 0


def main(argv: Optional[list] = None) -> int:
    parser = argparse.ArgumentParser(
        description="Local video AI detection (no external APIs)."
    )
    parser.add_argument("video", nargs="?", default=None, help="Path to video file to analyze")
    parser.add_argument("--save-json", help="Path to save analysis result")
    parser.add_argument("--debug", action="store_true", help="Enable debug output")

    args = parser.parse_args(argv)

    video_path = args.video
    if not video_path:
        print("Please provide a video file path.")
        return 1

    return detect_video_local(video_path, save_json=args.save_json, debug=bool(args.debug))


if __name__ == "__main__":
    raise SystemExit(main())
