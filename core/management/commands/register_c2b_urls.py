from django.core.management.base import BaseCommand
from core.mpesa_utils import register_c2b_urls

class Command(BaseCommand):
    help = "Register M-Pesa C2B Validation and Confirmation URLs with Safaricom Daraja."

    def handle(self, *args, **options):
        result = register_c2b_urls()
        if isinstance(result, dict):
            status = result.get('status', result.get('ResponseDescription') or result.get('error') or 'OK')
            self.stdout.write(self.style.SUCCESS(f"RegisterURL result: {status}"))
            # Pretty print key fields for visibility
            req = result.get('request') or {}
            sc = result.get('status_code')
            self.stdout.write(f"Status Code: {sc}")
            self.stdout.write(f"ShortCode: {req.get('ShortCode')}")
            self.stdout.write(f"ValidationURL: {req.get('ValidationURL')}")
            self.stdout.write(f"ConfirmationURL: {req.get('ConfirmationURL')}")
            if 'error' in result:
                self.stderr.write(self.style.ERROR(f"Error: {result['error']}"))
            if 'raw' in result:
                self.stdout.write(f"Raw: {result['raw'][:500]}")
        else:
            self.stdout.write(str(result))
