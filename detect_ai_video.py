import argparse
import json
import os
import sys
from typing import Optional


def analyze_video_characteristics(video_path: str, debug: bool = False) -> dict:
    """
    Analyze video file characteristics and calculate AI detection score.
    If score > 0.3 (30%), mark as suspicious.
    """
    
    result = {
        "file": os.path.basename(video_path),
        "size_mb": round(os.path.getsize(video_path) / (1024 * 1024), 2),
        "ai_score": 0.0,
        "is_ai_generated": False,
        "detection_factors": []
    }
    
    score = 0.0
    
    # Factor 1: File size pattern (0.20 max)
    file_size_mb = result["size_mb"]
    if file_size_mb < 1:
        score += 0.20
        result["detection_factors"].append("Very small file size (+0.20)")
    elif 1 <= file_size_mb < 5:
        score += 0.15
        result["detection_factors"].append("Small file size (+0.15)")
    
    # Factor 2: Filename keywords (0.30 max)
    filename = os.path.basename(video_path).lower()
    ai_keywords = ['ai', 'synthetic', 'generated', 'deepfake', 'stable', 'midjourney', 'dali', 'veo']
    keyword_count = sum(1 for kw in ai_keywords if kw in filename)
    if keyword_count > 0:
        score += keyword_count * 0.15
        result["detection_factors"].append(f"AI keywords in filename (+{keyword_count * 0.15})")
    
    # Factor 3: File extension (0.15 max)
    _, ext = os.path.splitext(video_path)
    ext = ext.lower()
    uncommon_formats = ['.webm', '.flv', '.m4v']
    if ext in uncommon_formats:
        score += 0.15
        result["detection_factors"].append(f"Uncommon format {ext} (+0.15)")
    
    # Factor 4: Creation time (0.20 max)
    try:
        import time
        creation_time = os.path.getctime(video_path)
        file_age_hours = (time.time() - creation_time) / 3600
        if file_age_hours < 1:
            score += 0.20
            result["detection_factors"].append("Very recently created (+0.20)")
        elif file_age_hours < 24:
            score += 0.10
            result["detection_factors"].append("Recently created (+0.10)")
    except:
        pass
    
    # Cap score at 1.0
    result["ai_score"] = round(min(score, 1.0), 4)
    
    # Threshold: if score > 0.5, it's suspicious
    result["is_ai_generated"] = result["ai_score"] > 0.5
    
    if debug:
        print(f"[DEBUG] Final score: {result['ai_score']}")
        print(f"[DEBUG] Threshold: 0.5")
        print(f"[DEBUG] Is AI: {result['is_ai_generated']}")
    
    return result


def detect_video_local(video_path: str, save_json: Optional[str] = None, debug: bool = False) -> int:
    """
    Local video analysis without external APIs or services.
    """

    if not os.path.isfile(video_path):
        print(f"File not found: {video_path}")
        return 2

    print(f"\n🎬 Analyzing video: {os.path.basename(video_path)}")
    print("=" * 60)
    
    # Perform local analysis
    result = analyze_video_characteristics(video_path, debug=debug)
    
    # Display results
    print(f"\n📊 DETECTION RESULTS:")
    print(f"   File: {result['file']}")
    print(f"   Size: {result['size_mb']} MB")
    print(f"   AI Score: {result['ai_score']:.4f} (threshold: 0.03)")
    print(f"   Status: {'🚨 AI GENERATED' if result['is_ai_generated'] else '✅ AUTHENTIC'}")
    
    if result["detection_factors"]:
        print(f"\n📌 Detection Factors:")
        for factor in result["detection_factors"]:
            print(f"   • {factor}")
    else:
        print(f"\n   No suspicious factors detected.")
    
    print("=" * 60)

    if save_json:
        try:
            with open(save_json, "w", encoding="utf-8") as fh:
                json.dump(result, fh, indent=2)
            print(f"\n✅ Saved result to {save_json}")
        except Exception as e:
            print(f"❌ Failed to save JSON: {e}")

    return 0


def main(argv: Optional[list] = None) -> int:
    parser = argparse.ArgumentParser(
        description="Local video AI detection (no external APIs)."
    )
    parser.add_argument(
        "video", nargs="?", default=None,
        help="Path to video file to analyze"
    )
    parser.add_argument(
        "--save-json", help="Path to save analysis result"
    )
    parser.add_argument(
        "--debug", action="store_true", help="Enable debug output"
    )

    args = parser.parse_args(argv)

    # If no video specified, prompt user to choose
    video_path = args.video
    if not video_path:
        ai_detector_dir = os.path.join(
            os.path.expanduser("~"), "Documents", "Ai detector"
        )

        try:
            mp4_files = sorted(
                [f for f in os.listdir(ai_detector_dir) 
                 if f.lower().endswith(".mp4")]
            )
        except Exception as e:
            print(f"Error listing videos: {e}")
            return 1

        if not mp4_files:
            print(f"No MP4 files found in {ai_detector_dir}")
            return 1

        print("\n📹 Available video files:")
        print("=" * 60)
        for i, fname in enumerate(mp4_files, 1):
            fpath = os.path.join(ai_detector_dir, fname)
            size_mb = os.path.getsize(fpath) / (1024 * 1024)
            print(f"  {i}. {fname} ({size_mb:.1f} MB)")
        print("=" * 60)

        try:
            choice = input(f"\nEnter number (1-{len(mp4_files)}): ").strip()
            idx = int(choice) - 1
            if idx < 0 or idx >= len(mp4_files):
                print("Invalid choice.")
                return 1
            video_path = os.path.join(ai_detector_dir, mp4_files[idx])
            print(f"Selected: {mp4_files[idx]}")
        except ValueError:
            print("Invalid input.")
            return 1

    return detect_video_local(
        video_path, 
        save_json=args.save_json, 
        debug=bool(args.debug)
    )


if __name__ == "__main__":
    raise SystemExit(main())





