# Admin Guide

## Overview
Admins manage users, classes, fees, exams, messaging, analytics, and academic years.

## Navigation
- Admin Overview dashboard (`/admin_overview/`)
- Users (`/admin_users/`): list and manage users
- Fees (admin_fees): manage fees; expect Admin Fees page instead of Record Payment
- Payments (admin_payment): record fee payments
- Analytics (`/admin_analytics/`): table with filters and search (Django admin-like)
- Classes & Subjects: manage class-subject mapping (`manage_class_subjects`)
- Academic Years: run promotions (triggers `promote_students` command)

## Result Slips
- Teachers can use `teacher_class_result_slip` to view class slips with all students.

## Events Calendar
- Endpoint: `/dashboard/events/json/` returns events for admin/teacher roles.

## Messaging
- One-on-one basic messaging between roles (no groups/attachments in v1).

## Troubleshooting
- For common admin issues (analytics empty, URL reverses, M-Pesa callbacks, forms not saving), see the Admin Troubleshooting guide:
  - [Admin Troubleshooting](../troubleshooting/admin.md)
