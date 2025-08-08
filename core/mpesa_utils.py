import requests
import base64
from django.conf import settings
from datetime import datetime

def get_mpesa_access_token():
    consumer_key = settings.MPESA_CONSUMER_KEY
    consumer_secret = settings.MPESA_CONSUMER_SECRET
    api_URL = "https://sandbox.safaricom.co.ke/oauth/v1/generate?grant_type=client_credentials" if settings.MPESA_ENVIRONMENT == 'sandbox' else "https://api.safaricom.co.ke/oauth/v1/generate?grant_type=client_credentials"
    r = requests.get(api_URL, auth=(consumer_key, consumer_secret))
    return r.json().get('access_token')

def initiate_stk_push(phone_number, amount, account_ref, transaction_desc):
    print("[M-PESA] Initiating STK Push...")
    access_token = get_mpesa_access_token()
    print("[M-PESA] Access token:", access_token)
    shortcode = settings.MPESA_SHORTCODE
    passkey = settings.MPESA_PASSKEY
    timestamp = datetime.now().strftime('%Y%m%d%H%M%S')
    data_to_encode = shortcode + passkey + timestamp
    password = base64.b64encode(data_to_encode.encode()).decode('utf-8')
    api_url = "https://sandbox.safaricom.co.ke/mpesa/stkpush/v1/processrequest" if settings.MPESA_ENVIRONMENT == 'sandbox' else "https://api.safaricom.co.ke/mpesa/stkpush/v1/processrequest"
    headers = {"Authorization": f"Bearer {access_token}", "Content-Type": "application/json"}
    payload = {
        "BusinessShortCode": shortcode,
        "Password": password,
        "Timestamp": timestamp,
        "TransactionType": "CustomerPayBillOnline",
        "Amount": int(amount),
        "PartyA": phone_number,
        "PartyB": shortcode,
        "PhoneNumber": phone_number,
        "CallBackURL": "https://d6c3698eeef9.ngrok-free.app/mpesa/callback/",  # Updated to current ngrok URL
        "AccountReference": account_ref,
        "TransactionDesc": transaction_desc
    }
    print("[M-PESA] STK Push Request Payload:", payload)
    print("[M-PESA] STK Push Request Headers:", headers)
    try:
        response = requests.post(api_url, json=payload, headers=headers, timeout=20)
        print("[M-PESA] STK Push Raw Response:", response.text)
        try:
            resp_json = response.json()
        except Exception as e:
            print("[M-PESA][ERROR] Could not parse JSON response:", e)
            resp_json = {'error': 'Invalid JSON response', 'raw': response.text}
        return resp_json
    except requests.RequestException as e:
        print("[M-PESA][ERROR] Request to Daraja failed:", e)
        return {'error': str(e)}
