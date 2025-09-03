import os
import sys
import django
from datetime import datetime

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.append(BASE_DIR)
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "Analitica.settings")

django.setup()

from core.models import MpesaC2BLedger  # noqa: E402


def main(limit=20):
    qs = MpesaC2BLedger.objects.all().order_by("-created_at")[:limit]
    if not qs:
        print("No MpesaC2BLedger rows found.")
        return
    print(f"Found {qs.count()} ledger rows (showing most recent {len(qs)}):")
    for i, led in enumerate(qs, 1):
        created = getattr(led, "created_at", None)
        created_s = created.strftime("%Y-%m-%d %H:%M:%S") if isinstance(created, datetime) else str(created)
        print(
            f"{i:02d}. TransID={led.trans_id} Amount={led.amount} BillRef={led.bill_ref} "
            f"MSISDN={led.msisdn} ShortCode={led.business_short_code} Created={created_s}"
        )


if __name__ == "__main__":
    lim = 20
    if len(sys.argv) > 1:
        try:
            lim = int(sys.argv[1])
        except Exception:
            pass
    main(lim)
