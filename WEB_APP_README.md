# 🎬 AI Video Detector - Web Interface

A Flask-based web application that allows people to upload and test videos to detect if they're AI-generated.

## 📋 Features

- 📹 Drag & drop video upload
- 🎯 Real-time AI detection analysis
- 📊 Detailed detection factors
- 🔒 Secure file handling
- 📱 Responsive design
- 🚀 Simple & fast

## 🚀 Quick Start

### 1. Install Dependencies

```bash
pip install -r requirements_web.txt
```

### 2. Run the Web Server

```bash
python app.py
```

You should see:
```
🎬 AI Video Detector Web Server Starting...
📱 Open your browser to: http://localhost:5000
Press Ctrl+C to stop the server
```

### 3. Open in Browser

Visit: **http://localhost:5000**

## 💻 How It Works

1. User uploads a video (MP4, MOV, AVI, MKV, WEBM, FLV, M4V)
2. File is saved to `/uploads/` folder
3. Analysis runs using the local detection algorithm
4. Results display with:
   - Status (AI DETECTED or REAL VIDEO)
   - Confidence score
   - Detection factors

## 📁 Project Structure

```
Ai detector/
├── app.py                    # Flask web server
├── detect_ai_video.py        # Local detection logic
├── requirements_web.txt      # Web dependencies
├── templates/
│   └── index.html           # Web interface
└── uploads/                  # Uploaded videos (created automatically)
```

## 🔧 Configuration

**Max file size**: 500MB (editable in `app.py`)
**Detection threshold**: 0.03 (editable in `detect_ai_video.py`)

## 📤 Sharing with Others

### Option 1: Local Network
Run the server and share: `http://YOUR_IP_ADDRESS:5000`

### Option 2: Cloud Deployment
Deploy to Heroku, Replit, or AWS:
- Push code to GitHub
- Connect to hosting service
- Set `debug=False` in production

### Option 3: Docker (Optional)
Create a `Dockerfile`:
```dockerfile
FROM python:3.10
WORKDIR /app
COPY . .
RUN pip install -r requirements_web.txt
EXPOSE 5000
CMD ["python", "app.py"]
```

Then:
```bash
docker build -t ai-detector .
docker run -p 5000:5000 ai-detector
```

## 🛡️ Security Notes

- ✅ Files saved with timestamps to avoid conflicts
- ✅ Only allowed video formats accepted
- ✅ File size limited to 500MB
- ✅ Automatic cleanup recommended (add to cron job)

## 📊 Detection Factors

The detector checks:
- 📏 File size patterns
- 📝 Filename keywords (AI, synthetic, generated, etc.)
- 📂 File extension/format
- 🕐 Creation timestamp

## ❓ FAQ

**Q: Why is my video showing as AI when it's real?**
A: Lower confidence videos (0.03-0.10) might trigger false positives. This is a basic detector.

**Q: Can I modify the threshold?**
A: Yes! Edit the `0.03` value in `detect_ai_video.py` line 57.

**Q: How do I delete uploaded files?**
A: They're stored in `/uploads/`. Delete manually or add a cleanup script.

---

**Made with ❤️ for AI detection**
