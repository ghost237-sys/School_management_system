# Admin Troubleshooting

- Issue: Admin Analytics table/charts empty at `/admin_analytics/`
  Cause: `AdminAnalyticsView.get_context_data()` not computing analytics.
  Fix: Ensure analytics context is calculated and passed to template (`core/views.py`).

- Issue: Navigating to Fee Management opens Record Fee Payment instead of Admin Fees
  Cause: Route/template mapping points to `admin_payment.html`.
  Fix: Update navigation to use `admin_fees.html` as default page.

- Issue: NoReverseMatch for `get_notifications_api` or `admin_messaging`
  Cause: URL pattern file not included or stale server.
  Fix: Include missing URLconf in project `urls.py`; restart server.

- Issue: M-Pesa callback returns 400 'Missing payment details'
  Cause: Test phone not linked to a Student with active term/fee assignment.
  Fix: Use a real student phone and ensure current term and fee assignment exist.

- Issue: Admin Users page not visible
  Cause: Missing nav link to `/admin_users/`.
  Fix: Add link in `dashboards/admin_overview.html`.

- Issue: Exams page Term dropdown empty
  Cause: No `Term` objects exist.
  Fix: Create terms in admin; optionally display a friendly message.

- Issue: Add Teacher form submits but nothing happens
  Cause: No backend POST handler at `/dashboard/teachers/add/`.
  Fix: Implement view + URL to create Teacher and wire form action.

- Issue: Stepper in Add Student modal not advancing
  Cause: JS load/order or modal event issue.
  Fix: Ensure stepper JS loads after modal content and event bindings target modal DOM.
