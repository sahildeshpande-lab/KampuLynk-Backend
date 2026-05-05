# KampuLynk User Management API - cURL Documentation

Base URL:

```text
http://127.0.0.1:8000
```

Start the API:

```powershell
cd backend
..\myenv\Scripts\python.exe -m uvicorn app.main:app --reload --host 127.0.0.1 --port 8000
```

Use the `accessToken` returned by signup or login for protected APIs:

```text
Authorization: Bearer YOUR_ACCESS_TOKEN
```

## 1] Authentication

### POST /auth/signup

```bash
curl -X POST "http://127.0.0.1:8000/auth/signup" \
  -H "Content-Type: application/json" \
  -d '{
    "fullName": "john",
    "email": "john@university.edu",
    "password": "john@123321",
    "university": "MIT",
    "major": "Data science",
    "minor": "AI",
    "educationLevel": "bachelors",
    "invitationCode": "ss",
    "consentGiven": true
  }'
```

### POST /auth/verify-otp

Local testing OTP is `123456`.

```bash
curl -X POST "http://127.0.0.1:8000/auth/verify-otp" \
  -H "Content-Type: application/json" \
  -d '{
    "email": "john@university.edu",
    "otp": "123456"
  }'
```

### POST /auth/resend-otp

```bash
curl -X POST "http://127.0.0.1:8000/auth/resend-otp" \
  -H "Content-Type: application/json" \
  -d '{
    "email": "john@university.edu"
  }'
```

### POST /auth/login

```bash
curl -X POST "http://127.0.0.1:8000/auth/login" \
  -H "Content-Type: application/json" \
  -d '{
    "email": "john@university.edu",
    "password": "john@123321"
  }'
```

### POST /auth/google

```bash
curl -X POST "http://127.0.0.1:8000/auth/google" \
  -H "Content-Type: application/json" \
  -d '{
    "idToken": "google-id-token",
    "email": "john@university.edu",
    "fullName": "John University",
    "profilePhotoUrl": "https://storage.example.com/profile.png"
  }'
```

### POST /auth/apple

```bash
curl -X POST "http://127.0.0.1:8000/auth/apple" \
  -H "Content-Type: application/json" \
  -d '{
    "idToken": "apple-id-token",
    "email": "john@university.edu",
    "fullName": "John University",
    "profilePhotoUrl": "https://storage.example.com/profile.png"
  }'
```

### POST /auth/refresh

```bash
curl -X POST "http://127.0.0.1:8000/auth/refresh" \
  -H "Content-Type: application/json" \
  -d '{
    "refreshToken": "YOUR_REFRESH_TOKEN"
  }'
```

### POST /auth/logout

```bash
curl -X POST "http://127.0.0.1:8000/auth/logout" \
  -H "Authorization: Bearer YOUR_ACCESS_TOKEN"
```

## 2] User Management

### GET /users/me

```bash
curl -X GET "http://127.0.0.1:8000/users/me" \
  -H "Authorization: Bearer YOUR_ACCESS_TOKEN"
```

### PUT /users/me

```bash
curl -X PUT "http://127.0.0.1:8000/users/me" \
  -H "Authorization: Bearer YOUR_ACCESS_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "fullName": "John University",
    "profilePhotoUrl": "https://storage.googleapis.com/profile.png",
    "bannerPhotoUrl": "https://storage.googleapis.com/banner.png",
    "university": "MIT",
    "major": "Data science",
    "minor": "AI",
    "educationLevel": "bachelors",
    "bio": "Researching distributed systems and consensus algorithms.",
    "academicInterests": ["distributed systems", "blockchain", "algorithms"],
    "graduationDate": "2027-05",
    "location": "Cambridge, MA",
    "profileVisibility": "public",
    "notificationPreferences": {
      "email": true,
      "push": true,
      "inApp": true
    },
    "consentGiven": true,
    "invitationCode": "ss",
    "onlinePresence": true,
    "welcomeMessage": "Welcome to KampuLynk."
  }'
```

### POST /users/me/change-password

```bash
curl -X POST "http://127.0.0.1:8000/users/me/change-password" \
  -H "Authorization: Bearer YOUR_ACCESS_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "currentPassword": "john@123321",
    "newPassword": "john@456654"
  }'
```

### DELETE /users/me

```bash
curl -X DELETE "http://127.0.0.1:8000/users/me" \
  -H "Authorization: Bearer YOUR_ACCESS_TOKEN"
```

### GET /users/me/export

```bash
curl -X GET "http://127.0.0.1:8000/users/me/export" \
  -H "Authorization: Bearer YOUR_ACCESS_TOKEN"
```

### GET /users/{userId}

```bash
curl -X GET "http://127.0.0.1:8000/users/USER_ID"
```

## 3] Admin — User Management

Admin APIs require a user with `role = 'admin'`.

For local testing, update an existing user in PostgreSQL:

```sql
UPDATE users
SET role = 'admin'
WHERE email = 'john@university.edu';
```

Then login again and use the new admin `accessToken`.

### GET /users/

```bash
curl -X GET "http://127.0.0.1:8000/users/" \
  -H "Authorization: Bearer ADMIN_ACCESS_TOKEN"
```

Optional pagination:

```bash
curl -X GET "http://127.0.0.1:8000/users/?skip=0&limit=50" \
  -H "Authorization: Bearer ADMIN_ACCESS_TOKEN"
```

### GET /users/admin/{userId}

```bash
curl -X GET "http://127.0.0.1:8000/users/admin/USER_ID" \
  -H "Authorization: Bearer ADMIN_ACCESS_TOKEN"
```

