# KampuLynk User Management API

FastAPI backend for student platform user registration, authentication, profile management, and admin user management.

## Features

- Email/password signup and login
- Email OTP verification
- Google and Apple login endpoints
- Session refresh and logout
- Current user profile APIs
- Public user profile API
- Admin user list and admin user detail APIs
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
- `3] Admin — User Management`

## Testing

Run tests:

```powershell
..\myenv\Scripts\python.exe -m pytest tests -q
```

The Playwright API test starts a temporary local API server and uses a temporary SQLite database.

## Documentation

- Swagger testing guide: [README_TEST.md](README_TEST.md)
- cURL examples: [API_CURL_DOCUMENTATION.md](API_CURL_DOCUMENTATION.md)

## Notes

- Local OTP verification uses `123456`.
- Signup creates users with `role: "user"`.
- Admin APIs require `role: "admin"` in the database.

