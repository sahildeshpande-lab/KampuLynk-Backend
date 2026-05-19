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

## 5] Invitations

### GET /invitations/code

Fetches the active invitation code for the logged-in user (creates one if missing).

**Endpoint:** `GET /invitations/code`

**cURL:**
```bash
curl -X GET "http://127.0.0.1:8000/invitations/code" \
  -H "Authorization: Bearer YOUR_ACCESS_TOKEN"
```

### POST /invitations/send

Creates an invitation (enforces daily limit + 7-day email cooldown) and returns the embedded-code URLs.

**Endpoint:** `POST /invitations/send`

**Request:**
```json
{ "email": "invitee@university.edu" }
```

## 4] Admin - Invitation Management

### GET /admin/invitation-codes

View invitation code list with pagination and optional `activeOnly=true`.

**Endpoint:** `GET /admin/invitation-codes?page=1&pageSize=10&activeOnly=false`

### GET /admin/invitation-codes/{codeId}

Access details of an invitation code including originator details.

**Endpoint:** `GET /admin/invitation-codes/{codeId}`

### PATCH /admin/invitation-codes/{codeId}/deactivate

Deactivate an invitation code.

**Endpoint:** `PATCH /admin/invitation-codes/{codeId}/deactivate`

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

## 7] Posts

### Media Field Note

- Canonical field for post files: `media`
- Legacy alias still accepted: `attachments`
- If both are sent, backend uses `media`
- Response includes both for backward compatibility; clients should read/write `media`

### POST /posts

**Endpoint:** `POST /posts`

**Request (recommended):**
```json
{
  "content": "Research update from today",
  "status": "published",
  "visibility": "public",
  "engagementEnabled": true,
  "contentFormat": "rich_text",
  "richTextHtml": "<p>Research update from today</p>",
  "media": [
    {
      "type": "image",
      "url": "https://cdn.example.com/posts/sample.jpg",
      "name": "sample.jpg",
      "contentType": "image/jpeg",
      "sizeBytes": 123456,
      "metadata": {}
    }
  ],
  "hashtags": ["#ai"],
  "topicTags": ["research"]
}
```

**Notes:**
- `status` controls draft/publish: `published` or `draft`
- content gate checks run for publish flow

### PATCH /posts/{postId}

**Endpoint:** `PATCH /posts/{postId}`

**Request (partial):**
```json
{
  "status": "published",
  "content": "Final revised post content",
  "media": []
}
```

### POST /posts/{postId}/rescan

Manual re-scan for edited content.

**Endpoint:** `POST /posts/{postId}/rescan`

### Engagement Endpoints

- `POST /posts/{postId}/reactions`
- `DELETE /posts/{postId}/reactions`
- `POST /posts/{postId}/comments`
- `POST /comments/{commentId}/replies`
- `POST /posts/{postId}/repost`

### POST /posts/{postId}/reactions

Create or update a user reaction for a post.

**Endpoint:** `POST /posts/{postId}/reactions`

**Request:**
```json
{ "reactionType": "like" }
```

**Supported `reactionType` values:**
- `like`
- `love`
- `celebrate`
- `insightful`
- `curious`
- `support`
- `remove like` (or `remove_like`) to remove an existing like using this same endpoint

**Business validations:**
- One active reaction per user per post.
- If already liked and request is `{"reactionType":"like"}`, API returns 400 with message: `Already liked this post`.
- If `reactionType = comment`, API returns 400 and client must use `POST /posts/{postId}/comments`.
- If `reactionType = repost`, API returns 400 and client must use `POST /posts/{postId}/repost`.

**Successful Response (200):**
```json
{
  "status": true,
  "message": "Reaction updated",
  "data": {
    "likeCount": 1,
    "reactions": { "like": 1 }
  }
}
```

**Unsuccessful Response (400 - duplicate like):**
```json
{
  "status": false,
  "message": "Already liked this post",
  "data": null
}
```

### DELETE /posts/{postId}/reactions

Remove current user's reaction from the post.

**Endpoint:** `DELETE /posts/{postId}/reactions`

**Successful Response (200):**
```json
{
  "status": true,
  "message": "Reaction deleted",
  "data": {
    "likeCount": 0,
    "reactions": {}
  }
}
```

### PATCH /posts/{postId}/report

Report a post for moderation review.

**Endpoint:** `PATCH /posts/{postId}/report`

**Request:**
```json
{
  "reason": "spam",
  "description": "optional details"
}
```

**Business validations:**
- Users cannot report their own post.
- Same user can report a given post only once.

**Successful Response (200):**
```json
{ "status": true, "message": "Post reported", "data": null }
```

**Unsuccessful Response (400 - duplicate report):**
```json
{ "status": false, "message": "You already reported this post", "data": null }
```

### PATCH /comments/{commentId}/report

Report a comment for moderation review.

**Endpoint:** `PATCH /comments/{commentId}/report`

**Request:**
```json
{
  "reason": "harassment",
  "description": "optional details"
}
```

**Business validations:**
- Users cannot report their own comment.
- Same user can report a given comment only once.

**Successful Response (200):**
```json
{ "status": true, "message": "Comment reported", "data": null }
```

**Unsuccessful Response (400 - duplicate report):**
```json
{ "status": false, "message": "You already reported this comment", "data": null }
```

### Admin Moderation Delete Behavior

When admin reviews reported post content and chooses `delete` from moderation review:
- Post is **soft deleted / archived** (not hard deleted).
- Post fields are updated as:
  - `moderationStatus = "Deleted by admin"`
  - `moderationReasons` populated from moderation queue reasons
  - `archivedAt` set to deletion timestamp
  - `deletedAt` set to deletion timestamp
  - `status = "archived"`

### POST /posts/{postId}/repost

Create a repost for the current user.

**Endpoint:** `POST /posts/{postId}/repost`

**Request:**
```json
{ "quote": "Loved the content" }
```

**Business validations:**
- A user can repost a given post only once.
- Second repost attempt by the same user for the same post returns 400.

**Successful Response (201):**
```json
{
  "status": true,
  "message": "Post reposted",
  "data": {
    "id": "REPOST_ID",
    "postId": "POST_ID",
    "quote": "Loved the content"
  }
}
```

**Unsuccessful Response (400 - duplicate repost):**
```json
{
  "status": false,
  "message": "Already reposted this post",
  "data": null
}
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

## 6] Search & Discovery

### GET /discovery/users/search

Search public user profiles (text/hashtag).

**Endpoint:** `GET /discovery/users/search`

**Query params (optional):**
- `q`: keyword search across name/email/university/major/minor/bio/interests
- `hashtag`: repeatable or CSV (e.g. `hashtag=%23AI` or `hashtag=#AI,#Robotics`)
- `limit` (default 20, max 50), `offset` (default 0)

**cURL (keyword search):**
```bash
curl -X GET "http://127.0.0.1:8000/discovery/users/search?q=MIT&limit=20&offset=0"
```

**cURL (hashtag search):**
```bash
curl -X GET "http://127.0.0.1:8000/discovery/users/search?hashtag=%23AI"
```

### GET /discovery/users/filter

Filter public user profiles (structured filters).

**Endpoint:** `GET /discovery/users/filter`

**Query params (optional):**
- `university`, `major`, `minor`, `educationLevel`
- `interest`: repeatable or CSV (matches academic interests)
- `country`: matched against `location` text
- `limit` (default 20, max 50), `offset` (default 0)

**cURL (filters):**
```bash
curl -X GET "http://127.0.0.1:8000/discovery/users/filter?university=Stanford&interest=Genetics&country=USA"
```

## Demo Data (Local)

Seed 10 users + 5 admins into your configured database:

```powershell
cd backend
..\myenv\Scripts\python.exe scripts\seed_demo_data.py
```

Note: This seeder also adds a couple of `private` profiles (they will not appear in `/discovery/users/search` or `/discovery/users/filter`).

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

## 4] Admin - User Management

Admin APIs require an authenticated admin user.

Allowed admin roles:
- `superadmin`
- `moderator`
- `viewer`

Non-admin users receive `403 Forbidden`. Missing/invalid tokens receive `401 Unauthorized`.

## 4] Admin - Analytics

### GET /admin/analytics/dau-trend

Admin-only DAU (Daily Active Users) trend data.

**Endpoint:** `GET /admin/analytics/dau-trend?days=7&start_date=YYYY-MM-DD&end_date=YYYY-MM-DD`

**Query Params (optional):**
- `days` (default `7`, min `1`, max `90`)
- `start_date` (`YYYY-MM-DD`)
- `end_date` (`YYYY-MM-DD`)

**cURL:**
```bash
curl -X GET "http://127.0.0.1:8000/admin/analytics/dau-trend?days=7" \
  -H "Authorization: Bearer ADMIN_ACCESS_TOKEN"
```

**Successful Response (200):**
```json
{
  "status": true,
  "message": "DAU trend fetched",
  "data": {
    "today_dau": 0,
    "yesterday_dau": 0,
    "growth_percentage": 0.0,
    "trend": [
      { "date": "2026-05-12", "dau": 0 }
    ],
    "range": { "start_date": "2026-05-12", "end_date": "2026-05-18" }
  }
}
```

### GET /admin/analytics/dashboard

Admin analytics dashboard payload (summary + DAU trend + new user trend + demographics).

**Endpoint:** `GET /admin/analytics/dashboard?days=7&start_date=YYYY-MM-DD&end_date=YYYY-MM-DD&top_limit=5`

**Query Params (optional):**
- `days` (default `7`, min `1`, max `90`)
- `start_date` (`YYYY-MM-DD`)
- `end_date` (`YYYY-MM-DD`)
- `top_limit` (default `5`, min `1`, max `20`)

**cURL:**
```bash
curl -X GET "http://127.0.0.1:8000/admin/analytics/dashboard?days=7&top_limit=5" \
  -H "Authorization: Bearer ADMIN_ACCESS_TOKEN"
```

**Successful Response (200):**
```json
{
  "status": true,
  "message": "Admin analytics dashboard fetched",
  "data": {
    "summary": {
      "total_users": 0,
      "today_dau": 0,
      "yesterday_dau": 0,
      "dau_growth_percentage": 0.0,
      "today_new_users": 0,
      "new_user_growth_percentage": 0.0
    },
    "dau_trend": [{ "date": "2026-05-12", "dau": 0 }],
    "new_user_trend": [{ "date": "2026-05-12", "new_users": 0 }],
    "top_universities": [{ "university": "MIT", "count": 0 }],
    "country_distribution": [{ "country": "USA", "count": 0 }],
    "top_majors": [{ "major": "CS", "count": 0 }],
    "range": { "start_date": "2026-05-12", "end_date": "2026-05-18" }
  }
}
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
