from flask import Flask, render_template, request, jsonify
import os
import json
from werkzeug.utils import secure_filename
from detect_ai_video import analyze_video_characteristics

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


@app.route('/health')
def health():
    """Health check endpoint"""
    return jsonify({'status': 'ok', 'service': 'AI Video Detector'}), 200


if __name__ == '__main__':
    print("🎬 AI Video Detector Web Server Starting...")
    print("📱 Open your browser to: http://localhost:5000")
    print("Press Ctrl+C to stop the server")
    app.run(debug=True, host='0.0.0.0', port=5000)
