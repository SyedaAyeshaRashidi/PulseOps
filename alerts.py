import smtplib
import os
from email.mime.text import MIMEText

SENDER_EMAIL = os.environ.get("GMAIL_ADDRESS")
APP_PASSWORD = os.environ.get("GMAIL_APP_PASSWORD")
RECEIVER_EMAIL = SENDER_EMAIL

def send_alert(subject, message):
    if not SENDER_EMAIL or not APP_PASSWORD:
        print(f"ERROR: Email env vars not set")
        return False
    try:
        msg = MIMEText(message)
        msg["Subject"] = f"PulseOps Alert — {subject}"
        msg["From"] = SENDER_EMAIL
        msg["To"] = RECEIVER_EMAIL
        with smtplib.SMTP_SSL("smtp.gmail.com", 465) as server:
            server.login(SENDER_EMAIL, APP_PASSWORD)
            server.sendmail(SENDER_EMAIL, RECEIVER_EMAIL, msg.as_string())
        print(f"Alert sent: {subject}")
        return True
    except Exception as e:
        print(f"Email error: {e}")
        return False

if __name__ == "__main__":
    send_alert("Test", "PulseOps email alert working correctly.")
