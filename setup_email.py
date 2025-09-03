#!/usr/bin/env python
"""
Email Setup and Test Script for School Management System
This script helps diagnose and fix email delivery issues
"""

import os
import sys
import django

# Add the project directory to Python path
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

# Set up Django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'Analitica.settings')
django.setup()

from django.core.mail import send_mail
from django.conf import settings
import smtplib
from email.mime.text import MIMEText

def test_smtp_connection():
    """Test direct SMTP connection to Gmail"""
    print("Testing SMTP connection to Gmail...")
    try:
        server = smtplib.SMTP(settings.EMAIL_HOST, settings.EMAIL_PORT)
        server.starttls()
        server.login(settings.EMAIL_HOST_USER, settings.EMAIL_HOST_PASSWORD)
        print("✅ SMTP connection successful!")
        server.quit()
        return True
    except Exception as e:
        print(f"❌ SMTP connection failed: {str(e)}")
        return False

def test_django_email():
    """Test Django email sending"""
    print("Testing Django email system...")
    try:
        subject = "[Seven Forks Primary School] Test Email"
        message = """
Dear User,

This is a test email from the School Management System Finance Department.

If you receive this email, the email system is working correctly.

Best regards,
Finance Department
Seven Forks Primary School
        """
        from_email = settings.DEFAULT_FROM_EMAIL
        recipient_list = ['emiliomuntin4@gmail.com']
        
        send_mail(
            subject=subject,
            message=message,
            from_email=from_email,
            recipient_list=recipient_list,
            fail_silently=False
        )
        
        print("✅ Django email sent successfully!")
        return True
    except Exception as e:
        print(f"❌ Django email failed: {str(e)}")
        return False

def print_email_config():
    """Print current email configuration"""
    print("=== Current Email Configuration ===")
    print(f"EMAIL_BACKEND: {settings.EMAIL_BACKEND}")
    print(f"EMAIL_HOST: {settings.EMAIL_HOST}")
    print(f"EMAIL_PORT: {settings.EMAIL_PORT}")
    print(f"EMAIL_USE_TLS: {settings.EMAIL_USE_TLS}")
    print(f"EMAIL_HOST_USER: {settings.EMAIL_HOST_USER}")
    print(f"DEFAULT_FROM_EMAIL: {settings.DEFAULT_FROM_EMAIL}")
    print(f"DEBUG: {settings.DEBUG}")
    print("=====================================")

def provide_troubleshooting_tips():
    """Provide troubleshooting tips for Gmail setup"""
    print("\n=== Gmail Setup Troubleshooting ===")
    print("If emails are not being sent, check these:")
    print("1. Gmail Account Settings:")
    print("   - Enable 2-Factor Authentication")
    print("   - Generate App Password (not regular password)")
    print("   - Use App Password in EMAIL_HOST_PASSWORD")
    print()
    print("2. Gmail Security:")
    print("   - Go to https://myaccount.google.com/security")
    print("   - Enable 2-Step Verification")
    print("   - Generate App Password for 'Mail'")
    print()
    print("3. Network/Firewall:")
    print("   - Ensure port 587 is not blocked")
    print("   - Check antivirus/firewall settings")
    print()
    print("4. Alternative SMTP Settings:")
    print("   - Try port 465 with SSL instead of 587 with TLS")
    print("   - Set EMAIL_USE_SSL=True and EMAIL_USE_TLS=False")
    print("=====================================")

if __name__ == "__main__":
    print("=== School Management System Email Setup ===")
    
    print_email_config()
    
    print("\nStep 1: Testing SMTP Connection...")
    smtp_ok = test_smtp_connection()
    
    print("\nStep 2: Testing Django Email...")
    django_ok = test_django_email()
    
    if smtp_ok and django_ok:
        print("\n🎉 Email system is fully functional!")
        print("📧 Check your inbox at emiliomuntin4@gmail.com")
    else:
        print("\n💥 Email system needs configuration.")
        provide_troubleshooting_tips()
