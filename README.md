# Cognito Auth API

A FastAPI application providing user authentication via AWS Cognito with JWT verification.

---

Source article: [Implementing AWS Cognito for User Management in FastAPI with Clean Architecture and Docker Deployment](https://medium.com/@3l4un1ck/implementing-aws-cognito-for-user-management-in-fastapi-with-clean-architecture-b686affb4cc6)

---

## Project Structure

```
app/
├── main.py                      # Entry point, middleware, rate limiting
├── api/
│   └── v1/
│       └── routes.py            # API endpoints
├── core/
│   ├── config.py                # Settings (loaded from configs/configs.yaml)
│   ├── errors.py                # Cognito error → HTTP response mapping
│   ├── limiter.py               # Rate limiter setup
│   └── security.py              # JWT verification, JWKS cache
├── domain/
│   └── models.py                # Pydantic request/response models
├── services/
│   └── auth_service.py          # Business logic
└── repository/
    └── cognito_repository.py    # AWS Cognito API calls
```

---

## Prerequisites

- Python 3.13+
- [uv](https://github.com/astral-sh/uv) package manager
- An AWS account with a Cognito User Pool configured

### Cognito User Pool Requirements

- **Username attributes**: email (users sign in with email)
- **Verification**: email verification enabled
- **App client**: `ALLOW_USER_PASSWORD_AUTH` authentication flow enabled
  - Console → User Pools → [pool] → App integration → App clients → [client] → Edit → Authentication flows

---

## Setup

### 1. Install dependencies

```bash
uv sync
```

### 2. Configure application settings

All configuration is in `configs/configs.yaml`:

```yaml
aws:
  region: us-east-1

cognito:
  user_pool_id: us-east-1_xxxxxxxxx
  client_id: xxxxxxxxxxxxxxxxxxxx

app:
  allowed_hosts:
    - "*"
  host: "0.0.0.0"
  port: 8000

security:
  jwks_ttl: 3600
  jwt_algorithm: RS256
  token_use: id

rate_limits:
  signup: "5/minute"
  login: "10/minute"
  forgot_password: "3/minute"
```

> The app will fail to start if `cognito.user_pool_id` or `cognito.client_id` are empty.

### 3. Configure AWS credentials

```bash
aws configure
```

Or set `AWS_ACCESS_KEY_ID`, `AWS_SECRET_ACCESS_KEY`, and `AWS_SESSION_TOKEN` environment variables.

### 4. Run the server

```bash
uv run uvicorn app.main:app --reload
```

API is available at `http://localhost:8000`
Swagger UI at `http://localhost:8000/docs`

---

## API Reference

### Authentication Flow

```
POST /signup  →  Cognito sends verification code to email
POST /confirm →  Verify email with the code
POST /login   →  Returns id_token, access_token, refresh_token
GET  /me      →  Returns authenticated user info (requires id_token)
```

### All Endpoints

| Method | Endpoint | Auth Required | Description |
|--------|----------|---------------|-------------|
| POST | `/api/v1/signup` | No | Register a new user |
| POST | `/api/v1/confirm` | No | Verify email with confirmation code |
| POST | `/api/v1/login` | No | Login and receive tokens |
| POST | `/api/v1/refresh` | No | Get new tokens using refresh_token |
| POST | `/api/v1/logout` | Yes (id_token) | Invalidate all sessions |
| POST | `/api/v1/forgot-password` | No | Send password reset code to email |
| POST | `/api/v1/reset-password` | No | Reset password using code |
| PUT | `/api/v1/change-password` | Yes (id_token) | Change password for logged-in user |
| GET | `/api/v1/me` | Yes (id_token) | Get current user info |
| GET | `/api/v1/hello` | Yes (id_token) | Protected dummy endpoint, returns greeting + email |
| POST | `/api/v1/users` | Yes (id_token) | Admin: create a user with a temporary password |
| DELETE | `/api/v1/users/{email}` | Yes (id_token) | Admin: delete a user |

---

### Request & Response Examples

#### Sign Up
```http
POST /api/v1/signup
Content-Type: application/json

{
  "email": "user@example.com",
  "password": "Password@123"
}
```
```json
{ "message": "User registered successfully. Check your email for a verification code" }
```

#### Confirm Email
```http
POST /api/v1/confirm
Content-Type: application/json

{
  "email": "user@example.com",
  "confirmation_code": "847291"
}
```
```json
{ "message": "Email verified successfully" }
```

#### Login
```http
POST /api/v1/login
Content-Type: application/json

{
  "email": "user@example.com",
  "password": "Password@123"
}
```
```json
{
  "id_token": "<jwt>",
  "access_token": "<jwt>",
  "refresh_token": "<token>",
  "token_type": "bearer"
}
```

> Use `id_token` in the `Authorization: Bearer` header for protected endpoints.
> Store `access_token` — required for logout and change-password.

#### Get Current User
```http
GET /api/v1/me
Authorization: Bearer <id_token>
```
```json
{
  "email": "user@example.com",
  "sub": "xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx"
}
```

#### Refresh Tokens
```http
POST /api/v1/refresh
Content-Type: application/json

{ "refresh_token": "<refresh_token>" }
```
```json
{
  "id_token": "<new_jwt>",
  "access_token": "<new_jwt>",
  "token_type": "bearer"
}
```

#### Logout
```http
POST /api/v1/logout
Authorization: Bearer <id_token>
Content-Type: application/json

{ "access_token": "<access_token>" }
```
```json
{ "message": "Logged out successfully" }
```

#### Forgot Password
```http
POST /api/v1/forgot-password
Content-Type: application/json

{ "email": "user@example.com" }
```
```json
{ "message": "Password reset code sent to your email" }
```

#### Reset Password
```http
POST /api/v1/reset-password
Content-Type: application/json

{
  "email": "user@example.com",
  "confirmation_code": "473829",
  "new_password": "NewPassword@456"
}
```
```json
{ "message": "Password reset successfully" }
```

#### Hello (Protected Dummy Endpoint)
```http
GET /api/v1/hello
Authorization: Bearer <id_token>
```
```json
{
  "message": "You are authenticated!",
  "email": "user@example.com"
}
```

#### Change Password
```http
PUT /api/v1/change-password
Authorization: Bearer <id_token>
Content-Type: application/json

{
  "access_token": "<access_token>",
  "old_password": "Password@123",
  "new_password": "NewPassword@456"
}
```
```json
{ "message": "Password changed successfully" }
```

---

## Testing via Swagger UI

1. Open `http://localhost:8000/docs`
2. Call `POST /api/v1/login` and copy the `id_token` from the response
3. Click the **Authorize** button (🔒) at the top right
4. Paste the `id_token` value (without `Bearer ` prefix) and click **Authorize**
5. Protected endpoints (🔒) will now include the token automatically

---

## Rate Limits

| Endpoint | Limit |
|----------|-------|
| `POST /signup` | 5 requests/minute |
| `POST /login` | 10 requests/minute |
| `POST /forgot-password` | 3 requests/minute |

---

## Password Policy

AWS Cognito enforces password requirements by default:
- Minimum 8 characters
- At least one uppercase letter
- At least one lowercase letter
- At least one number
- At least one special character

These can be customised in the Cognito User Pool settings.
