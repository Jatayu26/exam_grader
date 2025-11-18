import streamlit as st
import sqlite3
from google.oauth2.service_account import Credentials
from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload, MediaIoBaseDownload
import google.generativeai as genai
import io
from datetime import datetime
import time
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
import gspread
import os
from dotenv import load_dotenv
import pandas as pd

load_dotenv()

# Initialize SQLite and import data from Google Sheets
def init_db():
    conn = sqlite3.connect('students.db')
    c = conn.cursor()
    
    # Create tables
    c.execute('''CREATE TABLE IF NOT EXISTS students (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        email TEXT UNIQUE NOT NULL,
        name TEXT NOT NULL,
        usn TEXT UNIQUE NOT NULL,
        year TEXT NOT NULL,
        contact TEXT NOT NULL,
        college_email TEXT UNIQUE NOT NULL,
        branch TEXT NOT NULL,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )''')
    
    c.execute('''CREATE TABLE IF NOT EXISTS submissions (
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
    )''')
    
    c.execute('''CREATE TABLE IF NOT EXISTS grading_results (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        submission_id INTEGER NOT NULL,
        file_name TEXT NOT NULL,
        gemini_comments TEXT,
        score DECIMAL(5,2),
        graded_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (submission_id) REFERENCES submissions(id)
    )''')
    
    # Check if data already imported
    c.execute("SELECT COUNT(*) FROM students")
    if c.fetchone()[0] == 0:
        # Import from Google Sheets
        import_from_sheets()
    
    conn.commit()
    conn.close()

def import_from_sheets():
    try:
        # Connect to Google Sheets
        SCOPES = ['https://www.googleapis.com/auth/spreadsheets.readonly']
        creds = Credentials.from_service_account_file('credentials.json', scopes=SCOPES)
        client = gspread.authorize(creds)
        
        # Open the Google Sheet
        sheet_id = os.getenv('GOOGLE_SHEETS_ID')
        sheet = client.open_by_key(sheet_id).sheet1
        
        # Get all records
        records = sheet.get_all_records()
        
        # Insert into database
        conn = sqlite3.connect('students.db')
        c = conn.cursor()
        
        for record in records:
            try:
                c.execute("""INSERT INTO students (email, name, usn, year, contact, college_email, branch) 
                             VALUES (?, ?, ?, ?, ?, ?, ?)""", 
                          (record.get('email', ''), 
                           record.get('name', ''), 
                           record.get('usn', ''), 
                           record.get('year', ''),
                           record.get('contact', ''), 
                           record.get('college_email', ''), 
                           record.get('branch', '')))
            except sqlite3.IntegrityError:
                # Skip duplicates
                pass
        
        conn.commit()
        conn.close()
        st.success("Successfully imported student data from Google Sheets!")
    except Exception as e:
        st.warning(f"Could not import from Google Sheets: {str(e)}. Database will be empty initially.")

# Initialize Google Drive
def init_drive():
    SCOPES = ['https://www.googleapis.com/auth/drive']
    creds = Credentials.from_service_account_file('credentials.json', scopes=SCOPES)
    service = build('drive', 'v3', credentials=creds)
    return service

# Initialize Gemini
def init_gemini():
    genai.configure(api_key=os.getenv('GEMINI_API_KEY'))
    model = genai.GenerativeModel('gemini-1.5-flash')
    return model

# Login function
def login(college_email, usn):
    conn = sqlite3.connect('students.db')
    c = conn.cursor()
    c.execute("SELECT * FROM students WHERE college_email=? AND usn=?", (college_email, usn))
    user = c.fetchone()
    conn.close()
    return user

# Registration function
def register(email, name, usn, year, contact, college_email, branch):
    conn = sqlite3.connect('students.db')
    c = conn.cursor()
    try:
        c.execute("""INSERT INTO students (email, name, usn, year, contact, college_email, branch) 
                     VALUES (?, ?, ?, ?, ?, ?, ?)""", 
                  (email, name, usn, year, contact, college_email, branch))
        conn.commit()
        conn.close()
        return True
    except sqlite3.IntegrityError:
        conn.close()
        return False

# Upload to Google Drive
def upload_to_drive(files, usn, student_name):
    drive_service = init_drive()
    parent_folder_id = os.getenv('GOOGLE_DRIVE_FOLDER_ID')
    
    # Create or find folder with USN
    folder_name = f"{usn}_{student_name.replace(' ', '_')}"
    query = f"name='{folder_name}' and '{parent_folder_id}' in parents and mimeType='application/vnd.google-apps.folder'"
    results = drive_service.files().list(q=query, fields="files(id, name)").execute()
    folders = results.get('files', [])
    
    if folders:
        folder_id = folders[0]['id']
    else:
        folder_metadata = {
            'name': folder_name,
            'mimeType': 'application/vnd.google-apps.folder',
            'parents': [parent_folder_id]
        }
        folder = drive_service.files().create(body=folder_metadata, fields='id').execute()
        folder_id = folder['id']
    
    # Upload files
    uploaded_count = 0
    for uploaded_file in files:
        file_metadata = {'name': uploaded_file.name, 'parents': [folder_id]}
        
        # Save uploaded file to temp location
        temp_path = f"/tmp/{uploaded_file.name}"
        with open(temp_path, "wb") as f:
            f.write(uploaded_file.getbuffer())
        
        media = MediaFileUpload(temp_path, mimetype=uploaded_file.type)
        drive_service.files().create(body=file_metadata, media_body=media, fields='id').execute()
        uploaded_count += 1
        
        # Clean up temp file
        os.remove(temp_path)
    
    # Record submission
    conn = sqlite3.connect('students.db')
    c = conn.cursor()
    c.execute("""INSERT INTO submissions (usn, student_name, drive_folder_id, num_files) 
                 VALUES (?, ?, ?, ?)""", (usn, student_name, folder_id, uploaded_count))
    conn.commit()
    conn.close()
    
    return True

# Grade submissions with Gemini
def grade_submissions():
    conn = sqlite3.connect('students.db')
    c = conn.cursor()
    c.execute("SELECT * FROM submissions WHERE graded=0")
    ungraded = c.fetchall()
    conn.close()
    
    if not ungraded:
        return 0
    
    drive_service = init_drive()
    gemini_model = init_gemini()
    
    total_graded = 0
    total_score = 0
    
    progress_bar = st.progress(0)
    status_text = st.empty()
    
    for idx, submission in enumerate(ungraded):
        submission_id, usn, student_name, _, folder_id, num_files, _, _, _ = submission
        
        # Get all files in folder
        query = f"'{folder_id}' in parents and mimeType!='application/vnd.google-apps.folder'"
        results = drive_service.files().list(q=query, fields="files(id, name, mimeType)").execute()
        files = results.get('files', [])
        
        submission_score = 0
        files_graded = 0
        
        for file in files:
            if file['name'].startswith('COMMENTS_'):
                continue  # Skip already generated comment files
            
            status_text.text(f"Grading {student_name} - {file['name']}... ({idx + 1}/{len(ungraded)})")
            
            # Download file
            request = drive_service.files().get_media(fileId=file['id'])
            fh = io.BytesIO()
            downloader = MediaIoBaseDownload(fh, request)
            done = False
            while not done:
                status, done = downloader.next_chunk()
            
            # Send to Gemini
            fh.seek(0)
            image_data = fh.read()
            
            prompt = """Grade this exam answer sheet. Provide detailed feedback on:
            1. Correctness of answers
            2. Completeness of solutions
            3. Presentation and clarity
            4. Overall quality
            
            Give a score out of 10 and provide detailed comments. Start your response with "Score: X/10" where X is the score."""
            
            try:
                # Prepare content for Gemini
                image_parts = [{
                    "mime_type": file['mimeType'],
                    "data": image_data
                }]
                
                response = gemini_model.generate_content([prompt, image_parts[0]])
                comments = response.text
                
                # Extract score (simple parsing, look for "Score: X/10" or similar)
                score = 7.5  # Default if can't parse
                if "score:" in comments.lower():
                    try:
                        # Try to extract score from text
                        score_line = [line for line in comments.split('\n') if 'score:' in line.lower()][0]
                        score_part = score_line.split(':')[1].strip().split('/')[0].strip()
                        score = float(score_part)
                    except:
                        score = 7.5
                
                submission_score += score
                files_graded += 1
                
                # Save comments as text file in Drive
                comment_filename = f"COMMENTS_{file['name']}.txt"
                comment_metadata = {'name': comment_filename, 'parents': [folder_id], 'mimeType': 'text/plain'}
                
                # Save to temp file first
                temp_comment_path = f"/tmp/{comment_filename}"
                with open(temp_comment_path, 'w') as cf:
                    cf.write(comments)
                
                comment_media = MediaFileUpload(temp_comment_path, mimetype='text/plain')
                drive_service.files().create(body=comment_metadata, media_body=comment_media).execute()
                
                # Clean up temp file
                os.remove(temp_comment_path)
                
                # Save to database
                conn = sqlite3.connect('students.db')
                c = conn.cursor()
                c.execute("""INSERT INTO grading_results (submission_id, file_name, gemini_comments, score) 
                             VALUES (?, ?, ?, ?)""", (submission_id, file['name'], comments, score))
                conn.commit()
                conn.close()
                
                # RATE LIMIT: Wait 4 seconds between requests (15 req/min)
                time.sleep(4)
                
            except Exception as e:
                st.error(f"Error grading {file['name']}: {str(e)}")
        
        # Update submission
        avg_score = submission_score / files_graded if files_graded > 0 else 0
        conn = sqlite3.connect('students.db')
        c = conn.cursor()
        c.execute("""UPDATE submissions SET graded=1, total_score=?, graded_at=? 
                     WHERE id=?""", (avg_score, datetime.now(), submission_id))
        conn.commit()
        conn.close()
        
        total_graded += 1
        total_score += avg_score
        progress_bar.progress((idx + 1) / len(ungraded))
    
    # Send email notification
    avg_score = total_score / total_graded if total_graded > 0 else 0
    send_notification_email(total_graded, avg_score)
    
    return total_graded

# Send email
def send_notification_email(count, avg_score):
    try:
        sender_email = os.getenv('SMTP_EMAIL')
        sender_password = os.getenv('SMTP_PASSWORD')
        receiver_email = os.getenv('ADMIN_EMAIL')
        
        if not all([sender_email, sender_password, receiver_email]):
            st.warning("Email configuration not set. Skipping email notification.")
            return
        
        message = MIMEMultipart()
        message["From"] = sender_email
        message["To"] = receiver_email
        message["Subject"] = f"Exam Grading Complete - {datetime.now().strftime('%Y-%m-%d %H:%M')}"
        
        body = f"""
Grading completed successfully!

Total Submissions Graded: {count}
Average Score: {avg_score:.2f}/10
Date: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}

Login to the admin panel to view detailed results.
"""
        
        message.attach(MIMEText(body, "plain"))
        
        with smtplib.SMTP(os.getenv('SMTP_HOST', 'smtp.gmail.com'), int(os.getenv('SMTP_PORT', 587))) as server:
            server.starttls()
            server.login(sender_email, sender_password)
            server.send_message(message)
        
        st.success("Email notification sent successfully!")
    except Exception as e:
        st.warning(f"Failed to send email: {str(e)}")

# Main app
def main():
    st.set_page_config(page_title="RVCE Exam Grader", page_icon="📝", layout="wide")
    st.title("📝 RVCE Exam Answer Sheet Upload & Grading")
    
    # Tabs
    tab1, tab2 = st.tabs(["Student Portal", "Admin Panel"])
    
    # STUDENT TAB
    with tab1:
        if 'logged_in' not in st.session_state:
            st.session_state.logged_in = False
        
        if not st.session_state.logged_in:
            login_tab, register_tab = st.tabs(["Login", "Register"])
            
            with login_tab:
                st.subheader("🔐 Student Login")
                college_email = st.text_input("College Email ID", key="login_email")
                usn = st.text_input("USN (Password)", type="password", key="login_usn")
                if st.button("Login", key="login_btn"):
                    user = login(college_email, usn)
                    if user:
                        st.session_state.logged_in = True
                        st.session_state.user = user
                        st.session_state.name = user[2]
                        st.session_state.usn = user[3]
                        st.rerun()
                    else:
                        st.error("Invalid credentials!")
            
            with register_tab:
                st.subheader("📝 New Student Registration")
                with st.form("register_form"):
                    email = st.text_input("Personal Email Address")
                    name = st.text_input("Full Name")
                    usn = st.text_input("USN")
                    year = st.selectbox("Year", ["1st", "2nd", "3rd", "4th"])
                    contact = st.text_input("Contact Number")
                    college_email = st.text_input("College Email ID")
                    branch = st.selectbox("Branch", ["BCS", "CSE", "ECE", "EEE", "MECH", "CIVIL", "ISE", "AIML"])
                    
                    if st.form_submit_button("Register"):
                        if register(email, name, usn, year, contact, college_email, branch):
                            st.success("Registration successful! Please login.")
                        else:
                            st.error("USN or Email already exists!")
        
        else:
            st.success(f"Welcome, {st.session_state.name}! ({st.session_state.usn})")
            
            if st.button("Logout"):
                st.session_state.logged_in = False
                st.rerun()
            
            st.subheader("📤 Upload Answer Sheets")
            uploaded_files = st.file_uploader(
                "Select answer sheet photos/PDFs", 
                accept_multiple_files=True,
                type=['jpg', 'jpeg', 'png', 'pdf']
            )
            
            if uploaded_files:
                st.info(f"{len(uploaded_files)} file(s) selected")
                if st.button("Submit Answer Sheets"):
                    with st.spinner("Uploading to Google Drive..."):
                        try:
                            if upload_to_drive(uploaded_files, st.session_state.usn, st.session_state.name):
                                st.success("✅ Answer sheets uploaded successfully!")
                        except Exception as e:
                            st.error(f"Upload failed: {str(e)}")
    
    # ADMIN TAB
    with tab2:
        st.subheader("🔑 Admin Panel")
        
        if 'admin_logged_in' not in st.session_state:
            st.session_state.admin_logged_in = False
        
        if not st.session_state.admin_logged_in:
            admin_password = st.text_input("Enter Admin Password", type="password", key="admin_pass")
            if st.button("Access Admin Panel"):
                if admin_password == os.getenv('ADMIN_PASSWORD'):
                    st.session_state.admin_logged_in = True
                    st.rerun()
                else:
                    st.error("Invalid admin password!")
        else:
            st.success("✅ Admin Access Granted")
            
            if st.button("Logout", key="admin_logout"):
                st.session_state.admin_logged_in = False
                st.rerun()
            
            # Show submissions
            conn = sqlite3.connect('students.db')
            c = conn.cursor()
            c.execute("SELECT usn, student_name, submission_date, num_files, graded, total_score FROM submissions ORDER BY submission_date DESC")
            submissions = c.fetchall()
            conn.close()
            
            if submissions:
                st.subheader("📊 All Submissions")
                df = pd.DataFrame(submissions, columns=['USN', 'Student Name', 'Submission Date', 'Files', 'Graded', 'Score'])
                df['Graded'] = df['Graded'].map({0: '❌ Pending', 1: '✅ Graded'})
                st.dataframe(df, use_container_width=True)
                
                # Count ungraded
                ungraded_count = sum(1 for s in submissions if s[4] == 0)
                st.metric("Ungraded Submissions", ungraded_count)
                
                if ungraded_count > 0:
                    if st.button("🤖 Grade All Ungraded Submissions", type="primary"):
                        with st.spinner("Grading in progress... This may take a while."):
                            try:
                                graded_count = grade_submissions()
                                st.success(f"✅ Graded {graded_count} submissions successfully!")
                                st.balloons()
                                st.rerun()
                            except Exception as e:
                                st.error(f"Grading failed: {str(e)}")
                else:
                    st.info("All submissions are graded!")
            else:
                st.info("No submissions yet.")

if __name__ == "__main__":
    init_db()
    main()
