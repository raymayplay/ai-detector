from flask import Flask, render_template, request, jsonify
import os
import json
import urllib.request
import urllib.parse
from datetime import datetime
import yt_dlp
from werkzeug.utils import secure_filename
from detect_ai_video import analyze_video_characteristics

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
                'confidence': result['ai_score'],
                'is_ai': result['is_ai_generated'],
                'factors': result['detection_factors']
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
            description = info.get('description', '').lower()
            uploader = info.get('uploader', '').lower()
            
            # Simple heuristic detection for YouTube metadata
            score = 0.0
            factors = []
            
            # Factor 1: Keywords in title/description
            # Using more specific keywords to reduce false positives
            ai_keywords_strong = ['synthetic', 'deepfake', 'generated by ai', 'ai generated', 'midjourney', 'sora', 'veo', 'stable diffusion', 'runway gen', 'pika labs', 'luma dream machine', 'kling ai']
            ai_keywords_weak = ['ai', 'generated', 'artificial', 'intelligence', 'robot', 'automation']
            
            # Strong matches give more weight
            found_strong = [kw for kw in ai_keywords_strong if kw in title.lower() or kw in description]
            if found_strong:
                score += 0.5
                factors.append(f"Strong AI indicator: {', '.join(found_strong)} (+0.50)")
            
            # Weak matches only if combined or repeated
            found_weak = [kw for kw in ai_keywords_weak if kw in title.lower() or kw in description]
            
            # Check for #ai hashtag specifically in title or description
            if '#ai' in title.lower() or '#ai' in description:
                score += 0.5
                factors.append("Found #ai hashtag in metadata (+0.50)")

            if len(found_weak) >= 1:
                weight = 0.2 * len(set(found_weak))
                score += weight
                factors.append(f"AI-related terms found: {', '.join(set(found_weak))} (+{weight:.2f})")
            
            # Factor 2: Uploader name (be very specific here)
            ai_channel_keywords = ['ai channel', 'deepfake lab', 'synthetic media', 'ai tools', 'ai art']
            if any(kw in uploader for kw in ai_channel_keywords):
                score += 0.3
                factors.append(f"AI-specialized channel detected (+0.30)")
                
            # Factor 3: Tags (only high confidence tags)
            tags = [tag.lower() for tag in info.get('tags', [])]
            ai_tags = ['deepfake', 'ai video', 'synthetic media', 'sora ai', 'generative ai', 'ai animation', 'ai']
            found_ai_tags = [tag for tag in tags if tag in ai_tags]
            if found_ai_tags:
                score += 0.4
                factors.append(f"AI-specific tags detected: {', '.join(found_ai_tags)} (+0.40)")

            # Threshold: Increased to 0.5 for a balance of sensitivity and accuracy
            is_ai = score >= 0.5
            
            return jsonify({
                'status': 'success',
                'data': {
                    'filename': title,
                    'is_ai': is_ai,
                    'factors': factors
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

        # Forward to owner's email via formsubmit.co (free, no API key required)
        try:
            payload = json.dumps({
                'name': name,
                'email': email if '@' in email else 'noreply@aivideodetector.app',
                'rating': rating,
                'message': message,
                '_subject': f'New AI Video Detector Feedback ({rating} stars) from {name}',
                '_template': 'table',
                '_captcha': 'false',
            }).encode('utf-8')
            req = urllib.request.Request(
                f'https://formsubmit.co/ajax/{FEEDBACK_EMAIL}',
                data=payload,
                headers={
                    'Content-Type': 'application/json',
                    'Accept': 'application/json',
                    'User-Agent': 'Mozilla/5.0 (compatible; AI-Video-Detector/1.0)'
                },
                method='POST'
            )
            with urllib.request.urlopen(req, timeout=10) as resp:
                resp.read()
        except Exception as mail_err:
            print(f"[WARN] Email forwarding failed: {mail_err}")
            # Feedback is still saved locally, so report success to user
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
