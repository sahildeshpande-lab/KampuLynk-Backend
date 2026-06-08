# KampuLynk User Management API

FastAPI backend for student platform user registration, authentication, profile management, and admin user management.

## Features

- Email/password signup and login
- Email OTP verification
- Google and Apple login endpoints
- Session refresh and logout
- Current user profile APIs
- Public user profile API
- Multi-user notification APIs for email, in-app, and queued push delivery
- Admin user list and admin user detail APIs
- Admin analytics dashboard APIs
- PostgreSQL database support
- Swagger UI documentation

## Project Structure

```text
backend/
  app/
    db/
      db.py
    models/
      model.py
      schemas.py
    main.py
  tests/
    test_users.py
  requirements.txt
```

## Setup

Install dependencies:

```powershell
cd backend
..\myenv\Scripts\pip.exe install -r requirements.txt
```

The default database URL is:

```text
postgresql://postgres:root@localhost:5432/test
```

You can override it with:

```powershell
$env:DATABASE_URL="postgresql://postgres:root@localhost:5432/test"
```

## Run The API

```powershell
cd backend
..\myenv\Scripts\python.exe -m uvicorn app.main:app --reload --host 127.0.0.1 --port 8000
```

Open:

```text
http://127.0.0.1:8000
```

Swagger UI:

```text
http://127.0.0.1:8000/docs
```

## API Sections

Swagger UI is grouped into:

- `1] Authentication`
- `2] User Management`
- `3] Notifications`
- `4] Admin — User Management`

## Testing

The project uses `pytest` for unit and integration testing.

### Prerequisites for Testing
Ensure you have installed the test dependencies and have the virtual environment activated.

```powershell
cd backend
..\myenv\Scripts\pip.exe install -r requirements.txt
```

### Running Tests

**Run all tests (quiet mode):**
```powershell
..\myenv\Scripts\python.exe -m pytest tests -q
```

**Run tests with verbose output:**
```powershell
..\myenv\Scripts\python.exe -m pytest tests -v
```

**Run a specific test file:**
```powershell
..\myenv\Scripts\python.exe -m pytest tests/test_users.py
```

**Run tests with coverage report:**
```powershell
..\myenv\Scripts\python.exe -m pytest --cov=app tests/
```

The Playwright API test starts a temporary local API server and uses a temporary SQLite database to ensure a clean testing environment.

## Documentation

- Swagger testing guide: [README_TEST.md](README_TEST.md)






## Notes

- OTP codes are randomly generated 6-digit numbers.
- OTP verification expires 10 minutes after generation.
- `/auth/resend-otp` currently returns the OTP in response data for local/testing use (temporary and security-sensitive).
- Notification email templates use the KampuLynk navy/crimson brand palette.
- Push notifications are currently queued in notification delivery status; provider delivery can be connected when device tokens/APNs/FCM are added.
- Signup creates users with `role: "user"`.
- Admin APIs require `role: "admin"` in the database.
- Admin APIs require a user with role in: `superadmin`, `moderator`, `viewer`.
