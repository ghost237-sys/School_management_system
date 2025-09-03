import os
import sys
import django

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.append(BASE_DIR)
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "Analitica.settings")

django.setup()

from core.models import FeePayment  # noqa: E402

refs = sys.argv[1:] or [
    "THS8A51C46",
    "NGROKTEST001",
    "TESTC2B001",
]

for r in refs:
    obj = FeePayment.objects.filter(reference=r).first()
    if obj:
        print(f"FOUND: reference={r} student={getattr(obj.student, 'admission_no', None)} amount={obj.amount_paid} status={obj.status}")
    else:
        print(f"MISSING: reference={r}")
