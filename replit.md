# AI Video Detector

## Overview

A Flask-based web application that allows users to upload videos and detect if they are AI-generated. The application provides a drag-and-drop interface for video uploads, performs analysis on the uploaded files, and returns detection results with confidence scores and detailed factors.

## User Preferences

Preferred communication style: Simple, everyday language.

## System Architecture

### Frontend Architecture
- Single-page web interface using vanilla HTML, CSS, and JavaScript
- Templates served from `/templates` directory using Flask's Jinja2 templating
- Modern dark theme UI with Inter font from Google Fonts
- Drag-and-drop file upload functionality

### Backend Architecture
- **Framework**: Flask web server running on port 5000
- **Entry Point**: `app.py` - handles routing and file upload processing
- **Detection Logic**: `detect_ai_video.py` - contains the `analyze_video_characteristics()` function
- **File Handling**: Werkzeug's `secure_filename` for safe file uploads

### Detection Algorithm
The AI detection uses heuristic scoring based on:
1. File size patterns (smaller files score higher)
2. Filename keywords (AI-related terms like 'deepfake', 'synthetic', etc.)
3. File extension analysis (uncommon formats scored higher)
4. File creation time metadata

A score above 0.3 (30%) marks a video as potentially AI-generated.

### File Upload Configuration
- **Upload Directory**: `/uploads` (created automatically)
- **Allowed Extensions**: mp4, mov, avi, mkv, webm, flv, m4v
- **Max File Size**: 500MB

### API Endpoints
- `GET /` - Serves the main upload interface
- `POST /api/analyze` - Accepts video file uploads and returns JSON analysis results

## External Dependencies

### Python Packages
- **Flask 2.3.3**: Web framework for serving the application
- **Werkzeug 2.3.7**: WSGI utilities and secure file handling

### External Resources
- **Google Fonts CDN**: Inter font family for UI typography

### Database
- None - the application is stateless and does not persist data beyond temporary file uploads