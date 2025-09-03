import os
import django
import requests

# Set up Django environment (project settings is Analitica.settings)
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'Analitica.settings')
django.setup()

from core.mpesa_utils import get_mpesa_access_token

def simulate_mpesa():
    access_token = get_mpesa_access_token()
    if not access_token:
        print("[ERROR] Could not retrieve M-Pesa access token. Check your credentials and network.")
        return
    print("Access Token:", access_token)
    url = 'https://sandbox.safaricom.co.ke/mpesa/c2b/v1/simulate'
    headers = {
        'Authorization': f'Bearer {access_token}',
        'Content-Type': 'application/json'
    }
    while True:
        print("\n--- M-Pesa Sandbox Payment Simulation ---")
        amount = input("Enter amount (e.g. 100): ").strip()
        msisdn = input("Enter MSISDN (e.g. 2547XXXXXXXX): ").strip()
        bill_ref = input("Enter Bill Reference Number (e.g. INV123): ").strip()
        if not (amount and msisdn and bill_ref):
            print("[ERROR] All fields are required. Try again.")
            continue
        shortcode = os.getenv('MPESA_SHORTCODE', '174379')  # default to sandbox PayBill 174379
        data = {
            "ShortCode": shortcode,
            "CommandID": "CustomerPayBillOnline",
            "Amount": amount,
            "Msisdn": msisdn,
            "BillRefNumber": bill_ref
        }
        try:
            resp = requests.post(url, headers=headers, json=data, timeout=15)
            resp.raise_for_status()
            print("[SUCCESS] Simulation Response:", resp.json())
        except requests.exceptions.HTTPError as errh:
            print("[HTTP Error]", errh)
            print("Response:", resp.text)
        except requests.exceptions.ConnectionError as errc:
            print("[Connection Error]", errc)
        except requests.exceptions.Timeout as errt:
            print("[Timeout Error]", errt)
        except requests.exceptions.RequestException as err:
            print("[Request Exception]", err)
        again = input("Simulate another payment? (y/n): ").strip().lower()
        if again != 'y':
            break

if __name__ == "__main__":
    simulate_mpesa()
