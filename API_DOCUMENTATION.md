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

**Endpoint:** `POST /auth/signup`

**Request Body:**
```json
{
  "fullName": "john",
  "email": "john@university.edu",
  "password": "john@123321",
  "university": "MIT",
  "major": "Data science",
  "minor": "AI",
  "educationLevel": "bachelors",
  "invitationCode": "ss",
  "consentGiven": true
}
```

**cURL:**
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

**Successful Response (201 Created):**
```json
{
  "status": true,
  "message": "Signup successful",
  "data": {
    "accessToken": "...",
    "refreshToken": "...",
    "user": { ... }
  }
}
```

**Unsuccessful Response (409 Conflict - Email Exists):**
```json
{
  "status": false,
  "message": "Email already registered",
  "data": null
}
```



### POST /auth/verify-otp

**Endpoint:** `POST /auth/verify-otp`

OTP is sent via email as a random 6-digit code and expires in 10 minutes.

**Request Body:**
```json
{
  "email": "john@university.edu",
  "otp": "123456"
}
```

**cURL:**
```bash
curl -X POST "http://127.0.0.1:8000/auth/verify-otp" \
  -H "Content-Type: application/json" \
  -d '{
    "email": "john@university.edu",
    "otp": "ENTER_OTP_FROM_EMAIL"
  }'
```

**Successful Response (200 OK):**
```json
{
  "status": true,
  "message": "Email verified",
  "data": {
    "email": "john@university.edu"
  }
}
```

**Unsuccessful Response (400 Bad Request - Invalid/Expired OTP):**
```json
{
  "status": false,
  "message": "Invalid OTP",
  "data": null
}
```

### POST /auth/resend-otp

**Endpoint:** `POST /auth/resend-otp`

Note: response currently includes OTP in `data.otp` for local/testing use only (temporary).

**Request Body:**
```json
{
  "email": "john@university.edu"
}
```

**cURL:**
```bash
curl -X POST "http://127.0.0.1:8000/auth/resend-otp" \
  -H "Content-Type: application/json" \
  -d '{
    "email": "john@university.edu"
  }'
```

**Successful Response (200 OK):**
```json
{
  "status": true,
  "message": "OTP sent",
  "data": {
    "email": "john@university.edu"
  }
}
```

**Unsuccessful Response (404 Not Found):**
```json
{
  "status": false,
  "message": "User not found",
  "data": null
}
```

### POST /auth/login

**Endpoint:** `POST /auth/login`

**Request Body:**
```json
{
  "email": "john@university.edu",
  "password": "john@123321"
}
```

**cURL:**
```bash
curl -X POST "http://127.0.0.1:8000/auth/login" \
  -H "Content-Type: application/json" \
  -d '{
    "email": "john@university.edu",
    "password": "john@123321"
  }'
```

**Successful Response (200 OK):**
```json
{
  "status": true,
  "message": "Login successful",
  "data": {
    "accessToken": "...",
    "refreshToken": "...",
    "user": { ... }
  }
}
```

**Unsuccessful Response (401 Unauthorized):**
```json
{
  "status": false,
  "message": "Invalid email or password",
  "data": null
}
```

### POST /auth/google | /auth/apple

**Endpoint:** `POST /auth/google` or `POST /auth/apple`

**Request Body:**
```json
{
  "idToken": "social-id-token",
  "email": "john@university.edu",
  "fullName": "John University",
  "profilePhotoUrl": "https://..."
}
```

**cURL (Google):**
```bash
curl -X POST "http://127.0.0.1:8000/auth/google" \
  -H "Content-Type: application/json" \
  -d '{
    "idToken": "google-id-token",
    "email": "john@university.edu",
    "fullName": "John University",
    "profilePhotoUrl": "https://kampulynk-user-media.s3.amazonaws.com/users/john/profile.png"
  }'
```

**Successful Response (200 OK):**
```json
{
  "status": true,
  "message": "Google login successful",
  "data": {
    "accessToken": "...",
    "refreshToken": "...",
    "user": { ... }
  }
}
```

### POST /auth/refresh

**Endpoint:** `POST /auth/refresh`

**Request Body:**
```json
{
  "refreshToken": "YOUR_REFRESH_TOKEN"
}
```

**cURL:**
```bash
curl -X POST "http://127.0.0.1:8000/auth/refresh" \
  -H "Content-Type: application/json" \
  -d '{
    "refreshToken": "YOUR_REFRESH_TOKEN"
  }'
```

**Successful Response (200 OK):**
```json
{
  "status": true,
  "message": "Token refreshed",
  "data": {
    "accessToken": "NEW_ACCESS_TOKEN",
    "refreshToken": "NEW_REFRESH_TOKEN",
    "user": { ... }
  }
}
```

**Unsuccessful Response (401 Unauthorized):**
```json
{
  "status": false,
  "message": "Invalid refresh token",
  "data": null
}
```

### POST /auth/logout

**Endpoint:** `POST /auth/logout`

**cURL:**
```bash
curl -X POST "http://127.0.0.1:8000/auth/logout" \
  -H "Authorization: Bearer YOUR_ACCESS_TOKEN"
```

**Successful Response (200 OK):**
```json
{
  "status": true,
  "message": "Logged out",
  "data": null
}
```

## 2] User Management

### GET /users/me

**Endpoint:** `GET /users/me`

**cURL:**
```bash
curl -X GET "http://127.0.0.1:8000/users/me" \
  -H "Authorization: Bearer YOUR_ACCESS_TOKEN"
```

**Successful Response (200 OK):**
```json
{
  "status": true,
  "message": "Current user fetched",
  "data": {
    "id": "...",
    "fullName": "John University",
    "email": "john@university.edu",
    "role": "user",
    "completenessScore": 85,
    ...
  }
}
```

### PUT /users/me

**Endpoint:** `PUT /users/me` (Use PATCH for partial updates)

**Request Body:**
```json
{
  "fullName": "John University",
  "university": "MIT",
  "major": "Data science",
  "bio": "Researching distributed systems.",
  "academicInterests": ["distributed systems", "blockchain"],
  ...
}
```

**cURL:**
```bash
curl -X PUT "http://127.0.0.1:8000/users/me" \
  -H "Authorization: Bearer YOUR_ACCESS_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "fullName": "John University",
    "profilePhotoUrl": "https://kampulynk-user-media.s3.amazonaws.com/users/john/profile.png",
    "bannerPhotoUrl": "https://kampulynk-user-media.s3.amazonaws.com/users/john/banner.png",
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

**Successful Response (200 OK):**
```json
{
  "status": true,
  "message": "Current user updated",
  "data": { ... }
}
```

### POST /users/me/change-password

**Endpoint:** `POST /users/me/change-password`

**Request Body:**
```json
{
  "currentPassword": "john@123321",
  "newPassword": "john@456654"
}
```

**cURL:**
```bash
curl -X POST "http://127.0.0.1:8000/users/me/change-password" \
  -H "Authorization: Bearer YOUR_ACCESS_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "currentPassword": "john@123321",
    "newPassword": "john@456654"
  }'
```

**Successful Response (200 OK):**
```json
{
  "status": true,
  "message": "Password changed",
  "data": null
}
```

**Unsuccessful Response (401 Unauthorized - Incorrect Current Password):**
```json
{
  "status": false,
  "message": "Invalid current password",
  "data": null
}
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

## 3] Notifications

### POST /notifications

**Endpoint:** `POST /notifications`

Admin-only endpoint for sending templated notifications to multiple users.

**Request Body:**
```json
{
  "userIds": ["USER_ID_1", "USER_ID_2"],
  "template": {
    "key": "campus-update",
    "subject": "KampuLynk campus update",
    "title": "New campus update",
    "body": "A new campus update is available..."
  },
  "channels": {
    "email": true,
    "inApp": true,
    "push": true
  }
}
```

**cURL:**
```bash
curl -X POST "http://127.0.0.1:8000/notifications" \
  -H "Authorization: Bearer ADMIN_ACCESS_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "userIds": ["USER_ID_1", "USER_ID_2"],
    "template": {
      "key": "campus-update",
      "subject": "KampuLynk campus update",
      "title": "New campus update",
      "body": "A new campus update is available in your KampuLynk account."
    },
    "channels": {
      "email": true,
      "inApp": true,
      "push": true
    }
  }'
```

**Successful Response (201 Created):**
```json
{
  "status": true,
  "message": "Notification processed",
  "data": {
    "items": [...],
    "summary": {
      "requested": 2,
      "processed": 2,
      "missingOrInactiveUserIds": []
    }
  }
}
```

### GET /notifications/me

```bash
curl -X GET "http://127.0.0.1:8000/notifications/me?unreadOnly=false&page=1&pageSize=20" \
  -H "Authorization: Bearer YOUR_ACCESS_TOKEN"
```

### PATCH /notifications/{notificationId}/read

```bash
curl -X PATCH "http://127.0.0.1:8000/notifications/NOTIFICATION_ID/read" \
  -H "Authorization: Bearer YOUR_ACCESS_TOKEN"
```

## 4] Admin — User Management

Admin APIs require a user with `role = 'admin'`.

For local testing, update an existing user in PostgreSQL:

```sql
UPDATE users
SET role = 'admin'
WHERE email = 'john@university.edu';
```

Then login again and use the new admin `accessToken`.

### GET /users/

**Endpoint:** `GET /users/`

**cURL:**
```bash
curl -X GET "http://127.0.0.1:8000/users/" \
  -H "Authorization: Bearer ADMIN_ACCESS_TOKEN"
```

**Successful Response (200 OK):**
```json
{
  "status": true,
  "message": "Users fetched",
  "data": {
    "items": [ ... ],
    "pagination": {
      "page": 1,
      "pageSize": 10,
      "totalRecords": 45,
      "totalPages": 5
    }
  }
}
```

Optional pagination:

```bash
curl -X GET "http://127.0.0.1:8000/users/?page=1&pageSize=50" \
  -H "Authorization: Bearer ADMIN_ACCESS_TOKEN"
```

### GET /users/admin/{userId}

```bash
curl -X GET "http://127.0.0.1:8000/users/admin/USER_ID" \
  -H "Authorization: Bearer ADMIN_ACCESS_TOKEN"
```
