# Teacher Troubleshooting

- Issue: Calendar shows no events
  Cause: Missing permissions or endpoint not reachable.
  Fix: Verify `/dashboard/events/json/` returns events for role 'teacher'. Check `teacher_calendar.js` initialization.

- Issue: Cannot view class result slips for other classes
  Cause: Using admin-only view.
  Fix: Use `teacher_class_result_slip` endpoint to access any class results.

- Issue: Messaging recipients list empty
  Cause: UI not populating users by category.
  Fix: Ensure the recipient field queryset matches users by `role` and the category querystring is present.
