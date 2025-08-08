import requests
import sys

# Change this to your ngrok URL if testing via the internet
url = "http://127.0.0.1:8000/mpesa-callback/"

payload = {
    "Body": {
        "stkCallback": {
            "ResultCode": 0,
            "CallbackMetadata": {
                "Item": [
                    {"Name": "Amount", "Value": 1000},
                    {"Name": "PhoneNumber", "Value": "254700000000"},
                    {"Name": "MpesaReceiptNumber", "Value": "ABC123XYZ"}
                ]
            }
        }
    }
}

try:
    response = requests.post(url, json=payload, timeout=10)
    print("Status code:", response.status_code)
    print("Response:", response.text)
    if response.status_code == 200 and 'Received' in response.text:
        print("SUCCESS: Callback endpoint responded correctly.")
    else:
        print("WARNING: Callback endpoint did not respond as expected.")
except requests.ConnectionError:
    print("ERROR: Could not connect to the server. Make sure Django is running on {}".format(url))
    sys.exit(1)
except Exception as e:
    print("ERROR: An error occurred:", e)
    sys.exit(1)
