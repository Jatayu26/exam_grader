# RVCE Exam Answer Sheet Grader

AI-powered exam grading system using Streamlit, Google Drive, and Gemini AI.

## ✨ Features

- **Student Portal**
  - Student registration with college details
  - Secure login using College Email and USN
  - Upload answer sheets (multiple photos/PDFs)
  - Automatic upload to Google Drive with organized folders
  
- **Admin Panel**
  - Password-protected admin access
  - View all submissions with status
  - AI-powered grading using Google Gemini
  - Automatic feedback generation
  - Email notifications on completion
  
- **Database Management**
  - SQLite database for local storage
  - Automatic import from Google Sheets
  - Track submissions and grading results

## 🚀 Setup Instructions

### Prerequisites

1. Python 3.8 or higher
2. Google Cloud Project with enabled APIs:
   - Google Drive API
   - Google Sheets API
3. Google Gemini API key (free tier)
4. Gmail account for email notifications (optional)

### Step 1: Install Dependencies

```bash
pip install -r requirements.txt
```

### Step 2: Configure Google Cloud Service Account

1. Go to [Google Cloud Console](https://console.cloud.google.com/)
2. Create a new project or select existing one
3. Enable Google Drive API and Google Sheets API
4. Create a Service Account:
   - Go to "IAM & Admin" > "Service Accounts"
   - Click "Create Service Account"
   - Give it a name and click "Create"
   - Grant it "Editor" role
   - Click "Done"
5. Create credentials:
   - Click on the service account you just created
   - Go to "Keys" tab
   - Click "Add Key" > "Create new key"
   - Select "JSON" and click "Create"
   - Download the JSON file and save it as `credentials.json` in the project root

### Step 3: Configure Google Drive

1. Create a folder in Google Drive for storing answer sheets
2. Share the folder with the service account email (found in credentials.json as `client_email`)
3. Give the service account "Editor" permissions
4. Copy the folder ID from the URL (the part after `/folders/`)

### Step 4: Configure Google Sheets

1. Create or use existing Google Sheet with student data
2. Sheet should have these columns:
   - `email` (Personal email)
   - `name` (Full name)
   - `usn` (University Serial Number)
   - `year` (1st, 2nd, 3rd, 4th)
   - `contact` (Phone number)
   - `college_email` (College email ID)
   - `branch` (BCS, CSE, ECE, etc.)
3. Share the sheet with the service account email
4. Give the service account "Viewer" permissions
5. Copy the sheet ID from the URL (between `/d/` and `/edit`)

### Step 5: Get Gemini API Key

1. Go to [Google AI Studio](https://makersuite.google.com/app/apikey)
2. Sign in with your Google account
3. Click "Create API Key"
4. Copy the API key

### Step 6: Configure Environment Variables

1. Copy `.env.example` to `.env`:
   ```bash
   cp .env.example .env
   ```

2. Edit `.env` and fill in your values:
   ```env
   GOOGLE_DRIVE_FOLDER_ID=your_folder_id_here
   GEMINI_API_KEY=your_gemini_api_key_here
   ADMIN_PASSWORD=your_admin_password_here
   GOOGLE_SHEETS_ID=your_sheet_id_here
   
   # Optional email configuration
   SMTP_EMAIL=your_email@gmail.com
   SMTP_PASSWORD=your_app_password_here
   ADMIN_EMAIL=admin@example.com
   ```

### Step 7: Configure Gmail (Optional - for email notifications)

If you want email notifications:

1. Enable 2-Factor Authentication on your Gmail account
2. Generate an App Password:
   - Go to [Google Account Security](https://myaccount.google.com/security)
   - Under "How you sign in to Google", select "App passwords"
   - Select "Mail" and your device
   - Copy the 16-character password
3. Use this App Password in the `.env` file for `SMTP_PASSWORD`

### Step 8: Run the Application

```bash
streamlit run app.py
```

The application will open in your default web browser at `http://localhost:8501`

## 📱 Usage

### For Students

1. **First Time Users**: Use the Registration tab
   - Fill in all required details
   - Your College Email becomes your username
   - Your USN becomes your password

2. **Login**: Use the Login tab
   - Username: College Email (e.g., john.doe@college.edu)
   - Password: USN (e.g., RVCE25BCS004)

3. **Upload Answer Sheets**:
   - Select multiple photos/PDFs
   - Click "Submit Answer Sheets"
   - Files are uploaded to Google Drive in a folder named with your USN

### For Admins

1. Go to the "Admin Panel" tab
2. Enter the admin password
3. View all submissions
4. Click "Grade All Ungraded Submissions" to start AI grading
5. Gemini AI will:
   - Analyze each answer sheet
   - Provide detailed feedback
   - Assign scores out of 10
   - Save comments as text files in Drive
6. Receive email notification when grading is complete

## 🗄️ Database Schema

### students table
```sql
CREATE TABLE students (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    email TEXT UNIQUE NOT NULL,
    name TEXT NOT NULL,
    usn TEXT UNIQUE NOT NULL,
    year TEXT NOT NULL,
    contact TEXT NOT NULL,
    college_email TEXT UNIQUE NOT NULL,
    branch TEXT NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
```

### submissions table
```sql
CREATE TABLE submissions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    usn TEXT NOT NULL,
    student_name TEXT NOT NULL,
    submission_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    drive_folder_id TEXT,
    num_files INTEGER,
    graded BOOLEAN DEFAULT 0,
    total_score DECIMAL(5,2),
    graded_at TIMESTAMP,
    FOREIGN KEY (usn) REFERENCES students(usn)
);
```

### grading_results table
```sql
CREATE TABLE grading_results (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    submission_id INTEGER NOT NULL,
    file_name TEXT NOT NULL,
    gemini_comments TEXT,
    score DECIMAL(5,2),
    graded_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (submission_id) REFERENCES submissions(id)
);
```

## 🔒 Security Notes

- Never commit `credentials.json` or `.env` files to version control
- Use strong passwords for admin access
- Keep your API keys secret
- Use Gmail App Passwords instead of regular passwords
- Regularly review service account permissions

## ⚠️ Important Notes

- **Gemini Rate Limit**: The free tier allows 15 requests per minute. The app automatically waits 4 seconds between requests.
- **File Storage**: All answer sheets are stored in Google Drive, not locally.
- **Database**: SQLite database (`students.db`) is created automatically on first run.
- **Initial Data**: Student data is imported from Google Sheets on first run only.

## 🐛 Troubleshooting

### "Could not import from Google Sheets"
- Check if `credentials.json` exists and is valid
- Verify the Google Sheet is shared with the service account
- Check if the sheet ID in `.env` is correct

### "Upload failed"
- Verify the Drive folder is shared with the service account
- Check if the folder ID in `.env` is correct
- Ensure the service account has "Editor" permissions

### "Grading failed"
- Verify your Gemini API key is valid
- Check if you've exceeded the rate limit
- Ensure the image files are in supported formats

### Email not sending
- Use Gmail App Password, not regular password
- Check SMTP settings in `.env`
- Verify 2FA is enabled on your Gmail account

## 📄 License

This project is provided as-is for educational purposes.

## 🤝 Contributing

Feel free to submit issues and enhancement requests!
