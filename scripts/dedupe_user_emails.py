from django.db.models import Count
from core.models import User

print("Scanning for duplicate emails...")

dups = list(
    User.objects.values('email')
    .annotate(c=Count('id'))
    .filter(c__gt=1)
)
print(f"Found {len(dups)} duplicate email groups: {dups}")

for group in dups:
    email = group['email']
    users = list(User.objects.filter(email=email).order_by('id'))
    # keep the first as-is; update others
    local, sep, domain = (email or '').partition('@')
    if not sep:
        # no domain; just use the raw string
        local = email or 'user'
        domain = ''
    for i, u in enumerate(users[1:], start=1):
        if domain:
            new_email = f"{local}+dup{i}@{domain}"
        else:
            new_email = f"{local}+dup{i}"
        print(f"Fixing user {u.id}: {email} -> {new_email}")
        u.email = new_email
        u.save(update_fields=['email'])

print("Deduplication complete.")
