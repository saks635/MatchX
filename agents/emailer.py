import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.mime.base import MIMEBase
from email import encoders
import os
from dotenv import load_dotenv

load_dotenv()

def generate_cold_email_template(resume_data, jobs_data, sender_name="Saksham"):
    return f"""
Subject: Application for Software Engineering Positions - {sender_name}

Dear Hiring Team,

I am {sender_name}, a Software Engineer from Pune, India. I came across your job openings and believe my skills align well:

MATCHING SKILLS:
{', '.join(resume_data.get('skills_detected', []))}

RELEVANT JOBS:
{chr(10).join([f"• {job['title'][:60]}" for job in jobs_data.get('jobs', [])[:3]])}

I have attached my resume for your review. I would love to discuss how I can contribute to your team.

Best regards,
{sender_name}
{sender_name}'s Email: {resume_data.get('emails', [''])[0] if resume_data.get('emails') else 'your-email@gmail.com'}
Pune, Maharashtra, India
    """

def send_email_with_resume(sender_email, app_password, receiver_email, resume_data, jobs_data, resume_path):
    msg = MIMEMultipart()
    msg['From'] = sender_email
    msg['To'] = receiver_email
    msg['Subject'] = f"Software Engineer Application - {resume_data.get('name', 'Candidate')}"
    
    # Email body
    body = generate_cold_email_template(resume_data, jobs_data)
    msg.attach(MIMEText(body, 'plain'))
    
    # Attach resume
    if os.path.exists(resume_path):
        with open(resume_path, "rb") as attachment:
            part = MIMEBase('application', 'octet-stream')
            part.set_payload(attachment.read())
        encoders.encode_base64(part)
        part.add_header(
            'Content-Disposition',
            f'attachment; filename= {os.path.basename(resume_path)}'
        )
        msg.attach(part)
    
    try:
        server = smtplib.SMTP_SSL('smtp.gmail.com', 465)
        server.login(sender_email, app_password)
        text = msg.as_string()
        server.sendmail(sender_email, receiver_email, text)
        server.quit()
        return True, "✅ Email sent successfully with resume!"
    except Exception as e:
        return False, f"❌ Failed to send: {str(e)}"
