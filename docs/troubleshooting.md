# Troubleshooting

## NoReverseMatch for URLs (e.g., `get_notifications_api`, `admin_messaging`)
- Ensure the URLconf that defines the path is included in the main `urls.py`.
- Restart the dev server if stale state is suspected.

## Admin Analytics table/charts empty
- Ensure `AdminAnalyticsView.get_context_data` provides metrics used by the template.

## Add Student stepper not working in modal
- Check JS load order and modal scoping for `.stepper-next/.stepper-prev` handlers.

## Exams Term dropdown empty
- Create `Term` instances first; ModelChoiceField requires data.

## M-Pesa callback 400: Missing payment details
- Phone not found in `Student` or no current term/fee assignment. Fix test data and retry.
