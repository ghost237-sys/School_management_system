# M-Pesa Integration (Daraja)

## Configuration
Set env vars:
- MPESA_ENVIRONMENT=sandbox|production
- MPESA_CONSUMER_KEY, MPESA_CONSUMER_SECRET
- MPESA_SHORTCODE, MPESA_PASSKEY
- MPESA_CALLBACK_URL (public HTTPS in production)
- Optional: MPESA_C2B_VALIDATION_URL, MPESA_C2B_CONFIRMATION_URL, MPESA_CALLBACK_SECRET

## Callback Behavior
- Matches incoming payment to a student by phone number.
- Requires current term and fee assignment; otherwise returns 400 ("Missing payment details").

## Testing
Use the helper scripts:
- `simulate_mpesa.py`
- `test_mpesa_callback.py`
Ensure the test phone exists in `Student` and term/fee assignment is active.
