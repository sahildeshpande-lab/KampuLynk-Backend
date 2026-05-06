# Notification And Auth Email Testing

This guide explains how to test OTP, account-created, password-changed, and notification email flows.

## Template Structure

`backend/app/templates/` contains:

- `base_email.html`
- `otp_email.html`
- `account_created_email.html`
- `password_changed_email.html`
- `notification_email.html`

`backend/app/services/email_service.py` loads and renders these templates.

## Required Env

Set these in `backend/.env`:

```text
DATABASE_URL=postgresql://postgres:root@localhost:5432/ksolves
SENDGRID_API_KEY=your-real-sendgrid-api-key
SENDGRID_FROM_EMAIL=verified-sender@example.com
```

## OTP + Account Created

1. Call `/auth/signup`.
2. Call `/auth/verify-otp` with the valid OTP.
3. Expected emails:
   - OTP verification email.
   - Account created success email after successful OTP verification.

## Password Changed

1. Login and get `accessToken`.
2. Call `/users/me/change-password`.
3. Expected email:
   - Password changed confirmation email.

## Notification Email

1. Admin calls `/notifications` with `"channels": {"email": true, "inApp": true, "push": true}`.
2. Expected:
   - Notification email is sent.
   - In-app notification is created.
   - Push status is `queued`.

## Automated Tests

Run:

```powershell
cd "D:\POC\FASTAPI project\backend"
..\myenv\Scripts\python.exe -m pytest tests/test_notifications.py -q
```

Covered assertions include:

- OTP email template rendering.
- Account created email template rendering.
- Password changed email template rendering and endpoint trigger.
- Admin notification send + user read/mark-read flow.
