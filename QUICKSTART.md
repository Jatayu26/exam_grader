# 🚀 Quick Start Guide

## Prerequisites Checklist
- [ ] Python 3.8+ installed
- [ ] Google Cloud account
- [ ] Google Gemini API key
- [ ] Gmail account (for notifications)

## 5-Minute Setup

### 1. Install Dependencies
```bash
pip install -r requirements.txt
```

### 2. Get Google Service Account Credentials
1. Visit: https://console.cloud.google.com/
2. Create new project
3. Enable APIs: Google Drive API, Google Sheets API
4. Create Service Account → Download JSON → Save as `credentials.json`

### 3. Get Gemini API Key
1. Visit: https://makersuite.google.com/app/apikey
2. Create API Key → Copy it

### 4. Configure Environment
```bash
cp .env.example .env
# Edit .env and fill in:
# - GEMINI_API_KEY
# - ADMIN_PASSWORD (change from default)
# - SMTP settings (optional, for email)
```

### 5. Share Google Resources
- Share Drive folder with service account email (from credentials.json)
- Share Google Sheet with service account email
- Give "Editor" permission for Drive, "Viewer" for Sheets

### 6. Run Application
```bash
streamlit run app.py
```

## Default Credentials
- **Admin Password**: `admin123` (change this in .env!)
- **Student Login**: College Email + USN

## Pre-configured URLs
- **Google Drive**: https://drive.google.com/drive/folders/1kq_E2q7Pfyr5dsNiXFPQVKQ4LdtKLzSv
- **Google Sheets**: https://docs.google.com/spreadsheets/d/1twEnmpMzCd6yltJ--QmBIqzfywmz2wbryYAKgXNR_lk

## Testing Flow
1. Open http://localhost:8501
2. Register a test student
3. Login with college email + USN
4. Upload test images
5. Switch to Admin Panel
6. Enter admin password
7. Click "Grade All Ungraded Submissions"

## Troubleshooting
- **Import Error**: Install dependencies
- **Auth Error**: Check credentials.json and .env
- **Upload Error**: Verify Drive folder permissions
- **Grading Error**: Check Gemini API key and rate limits

For detailed help, see README.md
