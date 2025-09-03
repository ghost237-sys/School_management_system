#!/usr/bin/env python
"""
Simple email test script for the School Management System
This script tests email functionality using Django's email system
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

def test_email():
    """Test email sending functionality"""
    print(f"Email Backend: {settings.EMAIL_BACKEND}")
    print(f"Debug Mode: {settings.DEBUG}")
    
    try:
        # Test email
        subject = "Test Email from School Management System"
        message = "This is a test email to verify email functionality is working."
        from_email = settings.DEFAULT_FROM_EMAIL
        recipient_list = ['emiliomuntin4@gmail.com']  # Use your actual email
        
        print(f"Sending test email...")
        print(f"From: {from_email}")
        print(f"To: {recipient_list}")
        print(f"Subject: {subject}")
        
        send_mail(
            subject=subject,
            message=message,
            from_email=from_email,
            recipient_list=recipient_list,
            fail_silently=False
        )
        
        print("✅ Email sent successfully!")
        if 'console' in settings.EMAIL_BACKEND:
            print("📧 Email was printed to console (development mode)")
        else:
            print("📧 Email was sent via SMTP")
            
    except Exception as e:
        print(f"❌ Email sending failed: {str(e)}")
        return False
    
    return True

if __name__ == "__main__":
    print("=== School Management System Email Test ===")
    success = test_email()
    if success:
        print("\n🎉 Email system is working correctly!")
    else:
        print("\n💥 Email system needs configuration.")
