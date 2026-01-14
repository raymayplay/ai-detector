# 🚀 Deploy to Replit - Step by Step

## Step 1: Create GitHub Repository

1. Go to **GitHub.com** (create account if needed)
2. Click **New Repository**
3. Name it: `ai-video-detector`
4. Choose **Public** (so Replit can access it)
5. Click **Create Repository**

## Step 2: Push Your Code to GitHub

On your PC, open PowerShell in the `Ai detector` folder:

```powershell
cd "c:\Users\moksh\OneDrive\Documents\Ai detector"
git init
git add .
git commit -m "Initial commit - AI video detector"
git branch -M main
git remote add origin https://github.com/YOUR_USERNAME/ai-video-detector.git
git push -u origin main
```

**Replace `YOUR_USERNAME` with your GitHub username**

## Step 3: Import to Replit

1. Go to **Replit.com** (create free account)
2. Click **Create** → **Import from GitHub**
3. Paste your repo URL: `https://github.com/YOUR_USERNAME/ai-video-detector`
4. Click **Import**
5. Replit will automatically detect it's a Python project

## Step 4: Configure Replit

Replit should auto-detect the `.replit` file. It will:
- Install dependencies from `requirements.txt`
- Run `python app.py`
- Expose port 5000

## Step 5: Deploy & Share

1. Click **Run** button
2. You'll see the URL at the top: `https://your-replit-name.replit.dev`
3. **Share this link** with anyone to use your detector!

## ✅ Features with Replit

- ✅ Always online (24/7)
- ✅ Free tier available
- ✅ Professional URL
- ✅ Easy to update code
- ✅ Automatic backups

## 📝 Privacy Disclaimer (On Your Replit)

Add to your HTML `<body>` at the top:

```html
<div style="background: #fff3cd; padding: 10px; margin-bottom: 20px; border-radius: 4px; font-size: 12px;">
    <strong>⚠️ Privacy Notice:</strong> Videos are analyzed but not permanently stored. 
    Do not upload copyrighted or private content. Results may vary in accuracy.
</div>
```

---

**Having trouble?** Let me know and I'll help step by step!
