import os
import sys
import django
from datetime import datetime

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.append(BASE_DIR)
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "Analitica.settings")

django.setup()

from core.models import MpesaTransaction  # noqa: E402

def main(limit=20):
    qs = MpesaTransaction.objects.all().order_by("-created_at")[:limit]
    if not qs:
        print("No MpesaTransaction rows found.")
        return
    print(f"Found {qs.count()} transactions (showing most recent {len(qs)}):")
    for i, tx in enumerate(qs, 1):
        created = getattr(tx, "created_at", None)
        created_s = created.strftime("%Y-%m-%d %H:%M:%S") if isinstance(created, datetime) else str(created)
        print(
            f"{i:02d}. Phone={tx.phone_number} Amount={tx.amount} Ref={tx.account_reference} "
            f"Status={tx.status} Receipt={tx.mpesa_receipt} Checkout={tx.checkout_request_id} Created={created_s}"
        )

if __name__ == "__main__":
    lim = 20
    if len(sys.argv) > 1:
        try:
            lim = int(sys.argv[1])
        except Exception:
            pass
    main(lim)
