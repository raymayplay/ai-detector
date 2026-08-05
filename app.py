from flask import Flask, render_template, request, jsonify
import os
import json
import re
import tempfile
import urllib.request
import urllib.parse
from datetime import datetime
import yt_dlp
from werkzeug.utils import secure_filename
from detect_ai_video import analyze_video_characteristics

try:
    from frame_analyzer import analyze_frames
    _FRAME_ANALYSIS_AVAILABLE = True
except ImportError:
    _FRAME_ANALYSIS_AVAILABLE = False

FEEDBACK_EMAIL = 'mokshoswal152@gmail.com'
FEEDBACK_LOG = os.path.join(os.path.dirname(__file__), 'feedback.log')

app = Flask(__name__, template_folder='templates')

# Configuration
UPLOAD_FOLDER = os.path.join(os.path.dirname(__file__), 'uploads')
ALLOWED_EXTENSIONS = {'mp4', 'mov', 'avi', 'mkv', 'webm', 'flv', 'm4v'}
MAX_FILE_SIZE = 500 * 1024 * 1024  # 500MB

# Create upload folder if it doesn't exist
os.makedirs(UPLOAD_FOLDER, exist_ok=True)
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER
app.config['MAX_CONTENT_LENGTH'] = MAX_FILE_SIZE


def allowed_file(filename):
    """Check if file extension is allowed"""
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS


@app.route('/')
def index():
    """Serve the main page"""
    return render_template('index.html')


@app.route('/api/analyze', methods=['POST'])
def analyze_video():
    """Handle video upload and analysis"""
    try:
        # Check if file is in request
        if 'video' not in request.files:
            print("[ERROR] No video file in request")
            return jsonify({
                'status': 'error',
                'message': 'No video file provided'
            }), 400
        
        file = request.files['video']
        print(f"[DEBUG] File received: {file.filename}")
        
        if file.filename == '':
            print("[ERROR] Empty filename")
            return jsonify({
                'status': 'error',
                'message': 'No video selected'
            }), 400
        
        if not allowed_file(file.filename):
            print(f"[ERROR] File type not allowed: {file.filename}")
            return jsonify({
                'status': 'error',
                'message': f'Invalid file type. Allowed: {", ".join(ALLOWED_EXTENSIONS)}'
            }), 400
        
        # Save file with secure name
        filename = secure_filename(file.filename)
        import time
        timestamp = str(int(time.time()))
        filename = f"{timestamp}_{filename}"
        filepath = os.path.join(app.config['UPLOAD_FOLDER'], filename)
        
        print(f"[DEBUG] Saving to: {filepath}")
        file.save(filepath)
        print(f"[DEBUG] File saved successfully")
        
        # Analyze video
        print(f"[DEBUG] Starting analysis...")
        result = analyze_video_characteristics(filepath, debug=False)
        print(f"[DEBUG] Analysis complete. Score: {result['ai_score']}, Is AI: {result['is_ai_generated']}")
        
        # Return results
        response_data = {
            'status': 'success',
            'data': {
                'filename': result['file'],
                'size_mb': result['size_mb'],
                'score': result['ai_score'],
                'is_ai': result['is_ai_generated'],
                'confidence': result.get('confidence', 'Low'),
                'factors': result['detection_factors'],
                'authenticity_factors': result.get('authenticity_factors', []),
            }
        }
        print(f"[DEBUG] Sending response: {response_data}")
        return jsonify(response_data), 200
        
    except Exception as e:
        print(f"[ERROR] Exception: {str(e)}")
        import traceback
        traceback.print_exc()
        return jsonify({
            'status': 'error',
            'message': str(e),
            'details': type(e).__name__
        }), 500


def _run_frame_analysis_for_url(url, score, factors, authenticity_factors):
    """Download a small copy of the video and run frame-level AI analysis."""
    tmpdir = tempfile.mkdtemp(prefix="ytvid_")
    try:
        out_template = os.path.join(tmpdir, 'video.%(ext)s')
        download_opts = {
            'quiet': True,
            'no_warnings': True,
            'geo_bypass': True,
            'geo_bypass_country': 'US',
            # Prefer single-file formats at low resolution; we only need frames.
            'format': (
                'best[height<=360][ext=mp4][vcodec!=none]/'
                'best[height<=480][ext=mp4][vcodec!=none]/'
                'worstvideo[height<=480]/'
                'worst'
            ),
            'outtmpl': out_template,
            'max_filesize': 80 * 1024 * 1024,
            'socket_timeout': 30,
            'noplaylist': True,
            'merge_output_format': 'mp4',
            'extractor_args': {
                'youtube': {
                    'player_client': ['android', 'tv_embedded', 'mweb'],
                    'player_skip': ['webpage'],
                }
            },
        }
        with yt_dlp.YoutubeDL(download_opts) as dl:
            try:
                dl.download([url])
            except Exception as de:
                print(f"[WARN] Download for frame analysis failed: {de}")
                return score, factors, authenticity_factors

        # Locate downloaded file
        downloaded = None
        for fname in os.listdir(tmpdir):
            if fname.startswith('video.'):
                downloaded = os.path.join(tmpdir, fname)
                break
        if not downloaded or not os.path.isfile(downloaded):
            return score, factors, authenticity_factors

        frame_result = analyze_frames(downloaded)
        score += frame_result.get('score', 0.0)
        for f in frame_result.get('factors', []):
            factors.append(f"Visual: {f}")
        for f in frame_result.get('authenticity_factors', []):
            authenticity_factors.append(f"Visual: {f}")

        return score, factors, authenticity_factors
    finally:
        try:
            import shutil
            shutil.rmtree(tmpdir, ignore_errors=True)
        except Exception:
            pass


@app.route('/api/analyze-url', methods=['POST'])
def analyze_url():
    """Handle YouTube URL analysis"""
    try:
        data = request.json
        url = data.get('url')
        
        if not url:
            return jsonify({'status': 'error', 'message': 'No URL provided'}), 400
            
        print(f"[DEBUG] URL received: {url}")
        
        # Use yt-dlp to get info
        ydl_opts = {
            'quiet': True,
            'no_warnings': True,
            'geo_bypass': True,
            'geo_bypass_country': 'US',
            'skip_download': True,
            'extractor_args': {
                'youtube': {
                    'player_client': ['android', 'tv_embedded', 'mweb'],
                    'player_skip': ['webpage'],
                }
            },
        }
        
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            try:
                info = ydl.extract_info(url, download=False)
            except yt_dlp.utils.DownloadError as e:
                err = str(e)
                if 'unavailable' in err.lower() or 'not available' in err.lower():
                    return jsonify({'status': 'error', 'message': 'This video is unavailable or restricted in this region. Please try a different video.'}), 400
                elif 'private' in err.lower():
                    return jsonify({'status': 'error', 'message': 'This video is private and cannot be analyzed.'}), 400
                elif 'age' in err.lower():
                    return jsonify({'status': 'error', 'message': 'This video is age-restricted and cannot be analyzed.'}), 400
                else:
                    return jsonify({'status': 'error', 'message': 'Could not fetch this video. Make sure the URL is a valid YouTube link.'}), 400
            title = info.get('title', 'Unknown Title')
            description = (info.get('description') or '').lower()
            uploader = (info.get('uploader') or '').lower()
            channel = (info.get('channel') or '').lower()
            tags = [str(t).lower() for t in (info.get('tags') or [])]

            haystack = ' '.join([title.lower(), description, uploader, channel, ' '.join(tags)])

            score = 0.0
            factors = []
            authenticity_factors = []

            # Strong AI indicators: explicit tool names or unambiguous declarations
            strong_patterns = [
                r'\bai[\s\-]?generated\b',
                r'\bgenerated\s+by\s+ai\b',
                r'\bai[\s\-]?made\b',
                r'\bmade\s+by\s+ai\b',
                r'\bcreated\s+by\s+ai\b',
                r'\bcreated\s+with\s+ai\b',
                r'\bdeepfake\b',
                r'\bsynthetic\s+media\b',
                r'\bsynthetic\s+video\b',
                r'\bmade\s+with\s+(sora|runway|pika|kling|luma|midjourney|veo|imagen)\b',
                r'\b(sora|runway|pika|kling|luma\s+dream|midjourney|stable\s+diffusion|stable\s+video|veo|imagen|hunyuan|dall[\s\-]?e)\b',
                r'#ai(generated|video|art|made)?\b',
                r'#deepfake\b',
                r'#sora\b',
                r'#runway\b',
                r'#midjourney\b',
            ]
            strong_hits = []
            for pat in strong_patterns:
                m = re.search(pat, haystack)
                if m:
                    strong_hits.append(m.group(0))
            if strong_hits:
                score += 0.7
                factors.append(f"Explicit AI indicator: {', '.join(set(strong_hits))}")

            # Contextual AI patterns — natural language signals that the video itself is AI-generated.
            # These match phrases that creators commonly use in titles/descriptions for AI content,
            # while ignoring videos that merely discuss AI as a topic.
            contextual_patterns = [
                r'\bai\s+(interviews?|recreates?|imagines?|reimagines?|reconstructs?|reenacts?|brings?|brought|shows?|sings?|performs?|narrates?|voices?|generates?|creates?|made|makes?|did|does|drew|paints?|wrote|writes?|tells?|raps?|describes?)\b',
                r'\b(asked|using|with|by|via|through|prompted)\s+ai\b',
                r'\bai\s+version\s+of\b',
                r'\bai[\s\-]+(art|model|tool|image|video|animation|render|footage|clip|short|movie|film)\b',
                r'\b(midjourney|sora|runway|pika|kling|luma|dall[\s\-]?e|chatgpt|gpt[\s\-]?[0-9]?|stable\s+diffusion|leonardo|firefly)\b',
                r'\bgenerated\s+(with|using|by|via)\s+(ai|artificial)\b',
                r'\bprompt(ed|s|ing)?\b.{0,40}\b(ai|model|gpt|midjourney|sora)\b',
                r'\bthis\s+is\s+what\s+(ai|the\s+ai)\s+',
                r'\bwhat\s+(if\s+)?ai\s+(thinks|made|created|imagined|generated)\b',
                r'\bi\s+asked\s+ai\b',
            ]
            contextual_hits = []
            for pat in contextual_patterns:
                m = re.search(pat, haystack)
                if m:
                    contextual_hits.append(m.group(0).strip())
            if contextual_hits and not strong_hits:
                # Strong contextual evidence in description usually means AI-made content
                # Two or more matches → high confidence; one match → still strong enough
                if len(set(contextual_hits)) >= 2:
                    score += 0.7
                    factors.append(
                        f"Multiple AI generation phrases found: {', '.join(set(contextual_hits))}"
                    )
                else:
                    score += 0.55
                    factors.append(
                        f"AI generation phrase found: {', '.join(set(contextual_hits))}"
                    )
            elif contextual_hits:
                score += 0.15
                factors.append(
                    f"Additional AI context: {', '.join(set(contextual_hits))}"
                )

            # Standalone "AI" appearing prominently in the title
            # (with word boundaries so words like "Astley" don't match)
            title_lower = title.lower()
            ai_in_title = re.findall(r'\bai\b', title_lower)
            if ai_in_title and not strong_hits and not contextual_hits:
                score += 0.25
                factors.append("Title prominently mentions 'AI'")

            # AI-related tags (exact tag match, not substring)
            ai_tag_set = {
                'deepfake', 'ai video', 'ai-generated', 'ai generated', 'synthetic media',
                'sora', 'sora ai', 'generative ai', 'ai animation', 'runway ml', 'pika labs',
                'kling ai', 'midjourney video', 'stable video diffusion',
            }
            matching_tags = [t for t in tags if t in ai_tag_set]
            if matching_tags:
                score += 0.4
                factors.append(f"AI-specific tags: {', '.join(matching_tags)}")

            # Channel/uploader name strongly implies AI focus
            ai_channel_phrases = [
                'ai channel', 'ai videos', 'ai shorts', 'deepfake lab',
                'synthetic media', 'ai animations', 'generative ai',
            ]
            for phrase in ai_channel_phrases:
                if phrase in uploader or phrase in channel:
                    score += 0.3
                    factors.append(f"Channel name indicates AI focus: '{phrase}'")
                    break

            # Authenticity signals — categories typical of real-world recordings
            categories = [str(c).lower() for c in (info.get('categories') or [])]
            real_world_categories = {'news & politics', 'sports', 'travel & events', 'pets & animals'}
            if any(c in real_world_categories for c in categories):
                authenticity_factors.append(f"Real-world content category: {', '.join(categories)}")

            # Verified channel / live stream / very long video → likely authentic
            if info.get('was_live'):
                authenticity_factors.append("Originally a live broadcast")
                score = max(0.0, score - 0.2)

            duration = info.get('duration') or 0
            if duration > 600 and not strong_hits:
                authenticity_factors.append(f"Long-form content ({int(duration / 60)} min)")

            # ---- Visual frame analysis: download a small copy and inspect frames ----
            if _FRAME_ANALYSIS_AVAILABLE and (info.get('duration') or 0) <= 1800:
                try:
                    score, factors, authenticity_factors = _run_frame_analysis_for_url(
                        url, score, factors, authenticity_factors
                    )
                except Exception as fe:
                    print(f"[WARN] Frame analysis skipped: {fe}")

            score = min(score, 1.0)

            # Conservative threshold to avoid false positives
            is_ai = score >= 0.65
            if score >= 0.85:
                confidence = 'High'
            elif score >= 0.65:
                confidence = 'Medium'
            elif score >= 0.35:
                confidence = 'Low'
            else:
                confidence = 'High' if authenticity_factors else 'Medium'

            if not factors:
                factors.append("No AI markers detected in video metadata")

            return jsonify({
                'status': 'success',
                'data': {
                    'filename': title,
                    'is_ai': is_ai,
                    'score': round(score, 4),
                    'confidence': confidence,
                    'factors': factors,
                    'authenticity_factors': authenticity_factors,
                }
            })
            
    except Exception as e:
        print(f"[ERROR] URL Analysis Exception: {str(e)}")
        return jsonify({
            'status': 'error',
            'message': f"Could not analyze URL: {str(e)}"
        }), 500


@app.route('/api/feedback', methods=['POST'])
def submit_feedback():
    """Receive user feedback and email it to the owner."""
    try:
        data = request.json or {}
        name = str(data.get('name', 'Anonymous'))[:100]
        email = str(data.get('email', 'Not provided'))[:120]
        rating = str(data.get('rating', 'Not rated'))[:10]
        message = str(data.get('message', '')).strip()[:5000]

        if not message:
            return jsonify({'status': 'error', 'message': 'Message is required'}), 400

        timestamp = datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S UTC')

        # Always save a local log as a backup so feedback is never lost
        try:
            with open(FEEDBACK_LOG, 'a', encoding='utf-8') as f:
                f.write(f"\n--- {timestamp} ---\n")
                f.write(f"Name: {name}\nEmail: {email}\nRating: {rating}\n")
                f.write(f"Message: {message}\n")
        except Exception as log_err:
            print(f"[WARN] Could not write feedback log: {log_err}")

        # Send email via Resend API
        try:
            import resend

            resend.api_key = os.environ.get('RESEND_API_KEY', '')
            if not resend.api_key:
                raise RuntimeError("RESEND_API_KEY secret not set")

            stars = '★' * int(rating) if rating.isdigit() else rating
            html_body = f"""
            <html><body style="font-family:sans-serif;color:#222;">
            <h2 style="color:#4f46e5;">New Feedback Received</h2>
            <table style="border-collapse:collapse;width:100%;max-width:600px;">
              <tr style="background:#f5f5f5;"><td style="padding:10px;border:1px solid #ddd;font-weight:bold;width:120px;">Name</td><td style="padding:10px;border:1px solid #ddd;">{name}</td></tr>
              <tr><td style="padding:10px;border:1px solid #ddd;font-weight:bold;">Email</td><td style="padding:10px;border:1px solid #ddd;">{email}</td></tr>
              <tr style="background:#f5f5f5;"><td style="padding:10px;border:1px solid #ddd;font-weight:bold;">Rating</td><td style="padding:10px;border:1px solid #ddd;color:#f59e0b;font-size:1.2em;">{stars}</td></tr>
              <tr><td style="padding:10px;border:1px solid #ddd;font-weight:bold;">Message</td><td style="padding:10px;border:1px solid #ddd;">{message}</td></tr>
              <tr style="background:#f5f5f5;"><td style="padding:10px;border:1px solid #ddd;font-weight:bold;">Time</td><td style="padding:10px;border:1px solid #ddd;">{timestamp}</td></tr>
            </table>
            </body></html>
            """

            params = {
                "from": "AI Video Detector <onboarding@resend.dev>",
                "to": [FEEDBACK_EMAIL],
                "subject": f"New Feedback ({rating}★) from {name} — AI Video Detector",
                "html": html_body,
            }
            resend.Emails.send(params)
            print(f"[INFO] Feedback email sent via Resend from {name}")

            print(f"[INFO] Feedback email sent successfully from {name}")
        except Exception as mail_err:
            print(f"[WARN] Email sending failed: {mail_err}")
            # Feedback is still saved locally — report success so user knows we got it
            return jsonify({'status': 'success', 'message': 'Feedback received'}), 200

        return jsonify({'status': 'success', 'message': 'Feedback sent'}), 200

    except Exception as e:
        print(f"[ERROR] Feedback Exception: {str(e)}")
        return jsonify({'status': 'error', 'message': 'Could not process feedback'}), 500


@app.route('/health')
def health():
    """Health check endpoint"""
    return jsonify({'status': 'ok', 'service': 'AI Video Detector'}), 200


if __name__ == '__main__':
    print("🎬 AI Video Detector Web Server Starting...")
    print("📱 Open your browser to: http://localhost:5000")
    print("Press Ctrl+C to stop the server")
    app.run(debug=True, host='0.0.0.0', port=5000)
