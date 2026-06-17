"""
Quick SMTP test — run this locally to verify credentials before deploying.
Usage: python3 test_smtp.py
"""
import smtplib
import os
from email.message import EmailMessage
from dotenv import load_dotenv

load_dotenv()

smtp_email    = os.getenv('SMTP_EMAIL', '').strip()
smtp_password = os.getenv('SMTP_PASSWORD', '').replace(' ', '')

print(f"SMTP_EMAIL    : {smtp_email}")
print(f"SMTP_PASSWORD : {'*' * len(smtp_password)} ({len(smtp_password)} chars)")

if not smtp_email or not smtp_password:
    print("\n❌ SMTP_EMAIL or SMTP_PASSWORD is empty in .env")
    exit(1)

try:
    em = EmailMessage()
    em.set_content("This is a test email from V Royals Studio SMTP test script.")
    em['Subject'] = "V Royals Studio — SMTP Test"
    em['From']    = smtp_email
    em['To']      = smtp_email  # send to yourself

    print("\nConnecting to smtp.gmail.com:587 ...")
    with smtplib.SMTP("smtp.gmail.com", 587, timeout=10) as server:
        server.ehlo()
        server.starttls()
        server.ehlo()
        print("Logging in ...")
        server.login(smtp_email, smtp_password)
        print("Sending test email ...")
        server.send_message(em)

    print(f"\n✅ Success! Test email sent to {smtp_email}")
    print("Check your inbox.")

except smtplib.SMTPAuthenticationError as e:
    print(f"\n❌ Authentication failed: {e}")
    print("\nFix checklist:")
    print("  1. Is 2-Step Verification ON for this Google account?")
    print("     → https://myaccount.google.com/security")
    print("  2. Was the App Password generated for THIS exact account?")
    print("     → https://myaccount.google.com/apppasswords")
    print("  3. Did you copy the App Password correctly (16 chars, no spaces)?")

except Exception as e:
    print(f"\n❌ Error: {type(e).__name__}: {e}")
