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

Auth header for protected APIs:

```text
Authorization: Bearer YOUR_ACCESS_TOKEN
```

Common response envelope (all endpoints):

```json
{
  "status": true,
  "message": "string",
  "data": {}
}
```

## 0] Health

### GET /

**Endpoint:** `GET /`

**Request:** none

**cURL:**
```bash
curl -X GET "http://127.0.0.1:8000/"
```

**Successful Response (200):**
```json
{
  "status": true,
  "message": "KampuLynk User Management API is running",
  "data": null
}
```

**Unsuccessful Response:** none

## 1] Authentication

### POST /auth/signup

**Endpoint:** `POST /auth/signup`

**Request:**
```json
{
  "fullName": "john",
  "email": "john@university.edu",
  "password": "StrongPass123",
  "university": "MIT",
  "major": "CS",
  "educationLevel": "bachelors",
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
    "password": "StrongPass123",
    "university": "MIT",
    "major": "CS",
    "educationLevel": "bachelors",
    "consentGiven": true
  }'
```

**Successful Response (201):**
```json
{
  "status": true,
  "message": "Signup successful",
  "data": {
    "accessToken": "...",
    "refreshToken": "...",
    "user": { "...": "..." }
  }
}
```

**Unsuccessful Response (409 - Email already registered):**
```json
{
  "status": false,
  "message": "Email already registered",
  "data": null
}
```

### POST /auth/verify-otp

**Endpoint:** `POST /auth/verify-otp`

**Request:**
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
    "otp": "123456"
  }'
```

**Successful Response (200):**
```json
{
  "status": true,
  "message": "Email verified",
  "data": { "email": "john@university.edu" }
}
```

**Unsuccessful Response (400 - Invalid/expired OTP):**
```json
{
  "status": false,
  "message": "Invalid OTP",
  "data": null
}
```

### POST /auth/resend-otp

**Endpoint:** `POST /auth/resend-otp`

**Request:**
```json
{ "email": "john@university.edu" }
```

**cURL:**
```bash
curl -X POST "http://127.0.0.1:8000/auth/resend-otp" \
  -H "Content-Type: application/json" \
  -d '{ "email": "john@university.edu" }'
```

**Successful Response (200):**
```json
{
  "status": true,
  "message": "OTP sent",
  "data": { "email": "john@university.edu" }
}
```

**Unsuccessful Response (404 - User not found):**
```json
{
  "status": false,
  "message": "User not found",
  "data": null
}
```

### POST /auth/login

**Endpoint:** `POST /auth/login`

**Request:**
```json
{
  "email": "john@university.edu",
  "password": "StrongPass123"
}
```

**cURL:**
```bash
curl -X POST "http://127.0.0.1:8000/auth/login" \
  -H "Content-Type: application/json" \
  -d '{
    "email": "john@university.edu",
    "password": "StrongPass123"
  }'
```

**Successful Response (200):**
```json
{
  "status": true,
  "message": "Login successful",
  "data": {
    "accessToken": "...",
    "refreshToken": "...",
    "user": { "...": "..." }
  }
}
```

**Unsuccessful Response (401 - Invalid email or password):**
```json
{
  "status": false,
  "message": "Invalid email or password",
  "data": null
}
```

### POST /auth/social

**Endpoint:** `POST /auth/social`

**Request:**
```json
{
  "provider": "google",
  "idToken": "social-id-token",
  "email": "john@university.edu",
  "fullName": "John University",
  "profilePhotoUrl": "https://example.com/photo.png"
}
```

**cURL:**
```bash
curl -X POST "http://127.0.0.1:8000/auth/social" \
  -H "Content-Type: application/json" \
  -d '{
    "provider": "google",
    "idToken": "social-id-token",
    "email": "john@university.edu",
    "fullName": "John University",
    "profilePhotoUrl": "https://example.com/photo.png"
  }'
```

**Successful Response (200):**
```json
{
  "status": true,
  "message": "Google login successful",
  "data": { "accessToken": "...", "refreshToken": "...", "user": { "...": "..." } }
}
```

**Unsuccessful Response (422 - Validation error):**
```json
{
  "status": false,
  "message": "Validation error",
  "data": { "errors": [ { "...": "..." } ] }
}
```

### POST /auth/refresh

**Endpoint:** `POST /auth/refresh`

**Request:**
```json
{ "refreshToken": "YOUR_REFRESH_TOKEN" }
```

**cURL:**
```bash
curl -X POST "http://127.0.0.1:8000/auth/refresh" \
  -H "Content-Type: application/json" \
  -d '{ "refreshToken": "YOUR_REFRESH_TOKEN" }'
```

**Successful Response (200):**
```json
{
  "status": true,
  "message": "Token refreshed",
  "data": { "accessToken": "...", "refreshToken": "...", "user": { "...": "..." } }
}
```

**Unsuccessful Response (401 - Invalid refresh token):**
```json
{
  "status": false,
  "message": "Invalid refresh token",
  "data": null
}
```

### POST /auth/logout

**Endpoint:** `POST /auth/logout`

**Request:** none

**cURL:**
```bash
curl -X POST "http://127.0.0.1:8000/auth/logout" \
  -H "Authorization: Bearer YOUR_ACCESS_TOKEN"
```

**Successful Response (200):**
```json
{ "status": true, "message": "Logged out", "data": null }
```

**Unsuccessful Response (401 - Missing/invalid token):**
```json
{ "status": false, "message": "Missing bearer token", "data": null }
```

### POST /auth/admin/signup

**Endpoint:** `POST /auth/admin/signup`

**Request:** same schema as `/auth/signup`

**cURL:**
```bash
curl -X POST "http://127.0.0.1:8000/auth/admin/signup" \
  -H "Content-Type: application/json" \
  -d '{
    "fullName": "Admin",
    "email": "admin@university.edu",
    "password": "StrongPass123",
    "consentGiven": true,
    "university": "MIT",
    "major": "CS",
    "educationLevel": "bachelors"
  }'
```

**Successful Response (201):**
```json
{ "status": true, "message": "Admin signup successful", "data": { "accessToken": "...", "refreshToken": "...", "user": { "...": "..." } } }
```

**Unsuccessful Response (409 - Email already registered):**
```json
{ "status": false, "message": "Email already registered", "data": null }
```

### POST /auth/admin/signin

**Endpoint:** `POST /auth/admin/signin`

**Request:**
```json
{ "email": "admin@university.edu", "password": "StrongPass123" }
```

**cURL:**
```bash
curl -X POST "http://127.0.0.1:8000/auth/admin/signin" \
  -H "Content-Type: application/json" \
  -d '{ "email": "admin@university.edu", "password": "StrongPass123" }'
```

**Successful Response (200):**
```json
{ "status": true, "message": "Admin signin successful", "data": { "accessToken": "...", "refreshToken": "...", "user": { "...": "..." } } }
```

**Unsuccessful Response (403 - Admin access required):**
```json
{ "status": false, "message": "Admin access required", "data": null }
```

## 2] User Management

### GET /users/me

**Endpoint:** `GET /users/me`

**Request:** none

**cURL:**
```bash
curl -X GET "http://127.0.0.1:8000/users/me" \
  -H "Authorization: Bearer YOUR_ACCESS_TOKEN"
```

**Successful Response (200):**
```json
{ "status": true, "message": "Current user fetched", "data": { "...": "..." } }
```

**Unsuccessful Response (401 - Missing/invalid token):**
```json
{ "status": false, "message": "Missing bearer token", "data": null }
```

### PATCH /users/me

**Endpoint:** `PATCH /users/me`

**Request (partial update):**
```json
{ "bio": "New Bio" }
```

**cURL:**
```bash
curl -X PATCH "http://127.0.0.1:8000/users/me" \
  -H "Authorization: Bearer YOUR_ACCESS_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{ "bio": "New Bio" }'
```

**Successful Response (200):**
```json
{ "status": true, "message": "Current user updated", "data": { "...": "..." } }
```

**Unsuccessful Response (401 - Missing/invalid token):**
```json
{ "status": false, "message": "Missing bearer token", "data": null }
```

### POST /users/me/change-password

**Endpoint:** `POST /users/me/change-password`

**Request:**
```json
{ "currentPassword": "StrongPass123", "newPassword": "NewStrongPass123" }
```

**cURL:**
```bash
curl -X POST "http://127.0.0.1:8000/users/me/change-password" \
  -H "Authorization: Bearer YOUR_ACCESS_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{ "currentPassword": "StrongPass123", "newPassword": "NewStrongPass123" }'
```

**Successful Response (200):**
```json
{ "status": true, "message": "Password changed", "data": null }
```

**Unsuccessful Response (401 - Invalid current password):**
```json
{ "status": false, "message": "Invalid current password", "data": null }
```

### DELETE /users/me

**Endpoint:** `DELETE /users/me`

**Request:** none

**cURL:**
```bash
curl -X DELETE "http://127.0.0.1:8000/users/me" \
  -H "Authorization: Bearer YOUR_ACCESS_TOKEN"
```

**Successful Response (200):**
```json
{ "status": true, "message": "Current user deleted", "data": null }
```

**Unsuccessful Response (401 - Missing/invalid token):**
```json
{ "status": false, "message": "Missing bearer token", "data": null }
```

### GET /users/me/export

**Endpoint:** `GET /users/me/export`

**Request:** none

**cURL:**
```bash
curl -X GET "http://127.0.0.1:8000/users/me/export" \
  -H "Authorization: Bearer YOUR_ACCESS_TOKEN"
```

**Successful Response (200):**
```json
{ "status": true, "message": "Current user exported", "data": { "...": "..." } }
```

**Unsuccessful Response (401 - Missing/invalid token):**
```json
{ "status": false, "message": "Missing bearer token", "data": null }
```

### GET /users/{userId}

**Endpoint:** `GET /users/{userId}`

**Request:** none

Notes:
- `profileVisibility = "public"`: anyone can view.
- `profileVisibility = "private"`: always forbidden.
- `profileVisibility = "connections_only"`: only visible to mutual connections (requires `Authorization` header).

**cURL:**
```bash
curl -X GET "http://127.0.0.1:8000/users/USER_ID"
```

**cURL (connections_only):**
```bash
curl -X GET "http://127.0.0.1:8000/users/USER_ID" \
  -H "Authorization: Bearer YOUR_ACCESS_TOKEN"
```

**Successful Response (200):**
```json
{ "status": true, "message": "Public user fetched", "data": { "...": "..." } }
```

**Unsuccessful Response (404 - User not found):**
```json
{ "status": false, "message": "User not found", "data": null }
```

**Unsuccessful Response (403 - Private / connections only):**
```json
{ "status": false, "message": "Profile is private", "data": null }
```

```json
{ "status": false, "message": "Profile is connections only", "data": null }
```

### POST /users/{userId}/follow

**Endpoint:** `POST /users/{userId}/follow`

**Request:** none

**cURL:**
```bash
curl -X POST "http://127.0.0.1:8000/users/USER_ID/follow" \
  -H "Authorization: Bearer YOUR_ACCESS_TOKEN"
```

**Successful Response (200):**
```json
{ "status": true, "message": "User followed", "data": { "userId": "USER_ID" } }
```

**Unsuccessful Response (400 - Cannot follow yourself / blocked):**
```json
{ "status": false, "message": "Cannot follow yourself", "data": null }
```

```json
{ "status": false, "message": "User is blocked", "data": null }
```

### DELETE /users/{userId}/follow

**Endpoint:** `DELETE /users/{userId}/follow`

**Request:** none

**cURL:**
```bash
curl -X DELETE "http://127.0.0.1:8000/users/USER_ID/follow" \
  -H "Authorization: Bearer YOUR_ACCESS_TOKEN"
```

**Successful Response (200):**
```json
{ "status": true, "message": "User unfollowed", "data": { "userId": "USER_ID" } }
```

**Unsuccessful Response (401 - Missing/invalid token):**
```json
{ "status": false, "message": "Missing bearer token", "data": null }
```

### POST /users/{userId}/block

**Endpoint:** `POST /users/{userId}/block`

**Request:** none

**cURL:**
```bash
curl -X POST "http://127.0.0.1:8000/users/USER_ID/block" \
  -H "Authorization: Bearer YOUR_ACCESS_TOKEN"
```

**Successful Response (200):**
```json
{ "status": true, "message": "User blocked", "data": { "userId": "USER_ID" } }
```

**Unsuccessful Response (400 - Cannot block yourself):**
```json
{ "status": false, "message": "Cannot block yourself", "data": null }
```

### DELETE /users/{userId}/block

**Endpoint:** `DELETE /users/{userId}/block`

**Request:** none

**cURL:**
```bash
curl -X DELETE "http://127.0.0.1:8000/users/USER_ID/block" \
  -H "Authorization: Bearer YOUR_ACCESS_TOKEN"
```

**Successful Response (200):**
```json
{ "status": true, "message": "User unblocked", "data": { "userId": "USER_ID" } }
```

**Unsuccessful Response (401 - Missing/invalid token):**
```json
{ "status": false, "message": "Missing bearer token", "data": null }
```

### POST /users/{userId}/report

**Endpoint:** `POST /users/{userId}/report`

**Request:** none

**cURL:**
```bash
curl -X POST "http://127.0.0.1:8000/users/USER_ID/report" \
  -H "Authorization: Bearer YOUR_ACCESS_TOKEN"
```

**Successful Response (200):**
```json
{ "status": true, "message": "User reported", "data": { "userId": "USER_ID" } }
```

**Unsuccessful Response (400 - Cannot report yourself):**
```json
{ "status": false, "message": "Cannot report yourself", "data": null }
```

### POST /users/{userId}/lynkup/request

**Endpoint:** `POST /users/{userId}/lynkup/request`

**Request:** none

**cURL:**
```bash
curl -X POST "http://127.0.0.1:8000/users/USER_ID/lynkup/request" \
  -H "Authorization: Bearer YOUR_ACCESS_TOKEN"
```

**Successful Response (200 - Requested):**
```json
{ "status": true, "message": "LynkUp request sent", "data": { "userId": "USER_ID", "status": "requested" } }
```

**Successful Response (200 - Connected via mutual request):**
```json
{ "status": true, "message": "LynkUp connected", "data": { "userId": "USER_ID", "status": "connected" } }
```

**Unsuccessful Response (403 - Blocked):**
```json
{ "status": false, "message": "User is blocked", "data": null }
```

### POST /users/{userId}/lynkup/accept

**Endpoint:** `POST /users/{userId}/lynkup/accept`

**Request:** none

**cURL:**
```bash
curl -X POST "http://127.0.0.1:8000/users/USER_ID/lynkup/accept" \
  -H "Authorization: Bearer YOUR_ACCESS_TOKEN"
```

**Successful Response (200):**
```json
{ "status": true, "message": "LynkUp connected", "data": { "userId": "USER_ID", "status": "connected" } }
```

**Unsuccessful Response (400 - No pending request):**
```json
{ "status": false, "message": "No pending request to accept", "data": null }
```

### DELETE /users/{userId}/lynkup

**Endpoint:** `DELETE /users/{userId}/lynkup`

**Request:** none

**cURL:**
```bash
curl -X DELETE "http://127.0.0.1:8000/users/USER_ID/lynkup" \
  -H "Authorization: Bearer YOUR_ACCESS_TOKEN"
```

**Successful Response (200):**
```json
{ "status": true, "message": "LynkUp removed", "data": { "userId": "USER_ID" } }
```

**Unsuccessful Response (404 - User not found):**
```json
{ "status": false, "message": "User not found", "data": null }
```

## 3] Notifications

### POST /notifications

**Endpoint:** `POST /notifications` (Admin only)

**Request (direct):**
```json
{
  "type": "send",
  "targetType": "direct",
  "topic": null,
  "userIds": ["USER_ID_1"],
  "template": {
    "id": "welcome",
    "subject": "Hello",
    "title": "Welcome",
    "body": "This is a test notification",
    "htmlBody": null
  },
  "channels": { "email": true, "inApp": true, "push": false }
}
```

**cURL:**
```bash
curl -X POST "http://127.0.0.1:8000/notifications" \
  -H "Authorization: Bearer ADMIN_ACCESS_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "type": "send",
    "targetType": "direct",
    "userIds": ["USER_ID_1"],
    "template": {
      "id": "welcome",
      "subject": "Hello",
      "title": "Welcome",
      "body": "This is a test notification",
      "htmlBody": null
    },
    "channels": { "email": true, "inApp": true, "push": false }
  }'
```

**Successful Response (201):**
```json
{
  "status": true,
  "message": "Notification processed",
  "data": {
    "items": [ { "id": "...", "userId": "...", "type": "send", "targetType": "direct", "topic": null, "...": "..." } ],
    "summary": { "requested": 1, "processed": 1, "type": "send", "targetType": "direct", "topic": null, "missingOrInactiveUserIds": [] }
  }
}
```

**Unsuccessful Response (403 - Admin access required):**
```json
{ "status": false, "message": "Admin access required", "data": null }
```

### GET /notifications

**Endpoint:** `GET /notifications` (Admin only; filter by type)

**Request:** none

**cURL:**
```bash
curl -X GET "http://127.0.0.1:8000/notifications?type=send&page=1&pageSize=20" \
  -H "Authorization: Bearer ADMIN_ACCESS_TOKEN"
```

**Successful Response (200):**
```json
{ "status": true, "message": "Notifications fetched", "data": { "items": [ { "...": "..." } ], "pagination": { "...": "..." } } }
```

**Unsuccessful Response (403 - Admin access required):**
```json
{ "status": false, "message": "Admin access required", "data": null }
```

### POST /notifications/types

**Endpoint:** `POST /notifications/types` (Admin only)

**Request:**
```json
{
  "type": "configuration",
  "name": "Configuration Notification",
  "description": "Setup and configuration updates",
  "isActive": true
}
```

**cURL:**
```bash
curl -X POST "http://127.0.0.1:8000/notifications/types" \
  -H "Authorization: Bearer ADMIN_ACCESS_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "type": "configuration",
    "name": "Configuration Notification",
    "description": "Setup and configuration updates",
    "isActive": true
  }'
```

**Successful Response (201):**
```json
{ "status": true, "message": "Notification type created", "data": { "id": "...", "type": "configuration", "name": "...", "description": "...", "isActive": true, "createdAt": "...", "updatedAt": "..." } }
```

**Unsuccessful Response (409 - Notification type already exists):**
```json
{ "status": false, "message": "Notification type already exists", "data": null }
```

### GET /notifications/me

**Endpoint:** `GET /notifications/me`

**Request:** none

**cURL:**
```bash
curl -X GET "http://127.0.0.1:8000/notifications/me?unreadOnly=false&page=1&pageSize=20" \
  -H "Authorization: Bearer YOUR_ACCESS_TOKEN"
```

**Successful Response (200):**
```json
{ "status": true, "message": "Notifications fetched", "data": { "items": [ { "...": "..." } ], "pagination": { "...": "..." } } }
```

**Unsuccessful Response (401 - Missing/invalid token):**
```json
{ "status": false, "message": "Missing bearer token", "data": null }
```

### PATCH /notifications/{notificationId}/read

**Endpoint:** `PATCH /notifications/{notificationId}/read`

**Request:** none

**cURL:**
```bash
curl -X PATCH "http://127.0.0.1:8000/notifications/NOTIFICATION_ID/read" \
  -H "Authorization: Bearer YOUR_ACCESS_TOKEN"
```

**Successful Response (200):**
```json
{ "status": true, "message": "Notification marked as read", "data": { "...": "..." } }
```

**Unsuccessful Response (404 - Notification not found):**
```json
{ "status": false, "message": "Notification not found", "data": null }
```

## 4] Admin — User Management

Admin APIs require a user with `role = "admin"`.

### GET /users/

**Endpoint:** `GET /users/`

**Request:** none

**cURL:**
```bash
curl -X GET "http://127.0.0.1:8000/users/?page=1&pageSize=10" \
  -H "Authorization: Bearer ADMIN_ACCESS_TOKEN"
```

**Successful Response (200):**
```json
{ "status": true, "message": "Users fetched", "data": { "items": [ { "...": "..." } ], "pagination": { "...": "..." } } }
```

**Unsuccessful Response (403 - Admin access required):**
```json
{ "status": false, "message": "Admin access required", "data": null }
```

### POST /users/admin

**Endpoint:** `POST /users/admin`

**Request:**
```json
{
  "fullName": "Created By Admin",
  "email": "created@test.com",
  "password": "StrongPass123",
  "role": "user",
  "consentGiven": true,
  "university": "MIT",
  "major": "CS",
  "educationLevel": "bachelors"
}
```

**cURL:**
```bash
curl -X POST "http://127.0.0.1:8000/users/admin" \
  -H "Authorization: Bearer ADMIN_ACCESS_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "fullName": "Created By Admin",
    "email": "created@test.com",
    "password": "StrongPass123",
    "role": "user",
    "consentGiven": true,
    "university": "MIT",
    "major": "CS",
    "educationLevel": "bachelors"
  }'
```

**Successful Response (201):**
```json
{ "status": true, "message": "User created by admin", "data": { "...": "..." } }
```

**Unsuccessful Response (409 - Email already registered):**
```json
{ "status": false, "message": "Email already registered", "data": null }
```

### GET /users/admin/{userId}

**Endpoint:** `GET /users/admin/{userId}`

**Request:** none

**cURL:**
```bash
curl -X GET "http://127.0.0.1:8000/users/admin/USER_ID" \
  -H "Authorization: Bearer ADMIN_ACCESS_TOKEN"
```

**Successful Response (200):**
```json
{ "status": true, "message": "User fetched by admin", "data": { "...": "..." } }
```

**Unsuccessful Response (404 - User not found):**
```json
{ "status": false, "message": "User not found", "data": null }
```

### PATCH /users/admin/{userId}

**Endpoint:** `PATCH /users/admin/{userId}`

**Request (partial update):**
```json
{ "bio": "Admin Bio" }
```

**cURL:**
```bash
curl -X PATCH "http://127.0.0.1:8000/users/admin/USER_ID" \
  -H "Authorization: Bearer ADMIN_ACCESS_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{ "bio": "Admin Bio" }'
```

**Successful Response (200):**
```json
{ "status": true, "message": "User updated by admin", "data": { "...": "..." } }
```

**Unsuccessful Response (404 - User not found):**
```json
{ "status": false, "message": "User not found", "data": null }
```

### DELETE /users/admin/{userId}

**Endpoint:** `DELETE /users/admin/{userId}`

**Request:** none

**cURL:**
```bash
curl -X DELETE "http://127.0.0.1:8000/users/admin/USER_ID" \
  -H "Authorization: Bearer ADMIN_ACCESS_TOKEN"
```

**Successful Response (200):**
```json
{ "status": true, "message": "User deleted by admin", "data": null }
```

**Unsuccessful Response (404 - User not found):**
```json
{ "status": false, "message": "User not found", "data": null }
```
