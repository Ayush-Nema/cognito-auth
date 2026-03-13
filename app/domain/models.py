"""Pydantic request and response models for the auth API."""

from pydantic import BaseModel, EmailStr


class User(BaseModel):
    """Registration request payload."""

    email: EmailStr
    password: str


class UserLogin(BaseModel):
    """Login request payload."""

    email: EmailStr
    password: str


class ConfirmSignUp(BaseModel):
    """Email confirmation request payload."""

    email: EmailStr
    confirmation_code: str


class ResendConfirmationRequest(BaseModel):
    """Request to resend the email confirmation code."""

    email: EmailStr


class RefreshTokenRequest(BaseModel):
    """Request to exchange a refresh token for new tokens."""

    refresh_token: str


class ForgotPasswordRequest(BaseModel):
    """Request to initiate the forgot-password flow."""

    email: EmailStr


class ResetPasswordRequest(BaseModel):
    """Request to complete a password reset using a confirmation code."""

    email: EmailStr
    confirmation_code: str
    new_password: str


class ChangePasswordRequest(BaseModel):
    """Request to change the password for an authenticated user."""

    access_token: str
    old_password: str
    new_password: str


class LogoutRequest(BaseModel):
    """Request to globally sign out a user."""

    access_token: str


class AdminCreateUserRequest(BaseModel):
    """Admin request to create a new user."""

    email: EmailStr


# Response models
class MessageResponse(BaseModel):
    """Generic message response."""

    message: str


class GreetingResponse(BaseModel):
    """Response returned by the protected /hello endpoint."""

    message: str
    email: str


class AdminCreateUserResponse(BaseModel):
    """Response after an admin creates a new user, including the temporary password."""

    message: str
    temporary_password: str


class AuthResponse(BaseModel):
    """Full token set returned after a successful login."""

    id_token: str
    access_token: str
    refresh_token: str
    token_type: str = "bearer"


class TokenRefreshResponse(BaseModel):
    """Tokens returned after a successful refresh (no new refresh token issued)."""

    id_token: str
    access_token: str
    token_type: str = "bearer"


class RoleAssignmentRequest(BaseModel):
    """Request to assign or remove a role from a user."""

    email: EmailStr
    role: str


class UserRolesResponse(BaseModel):
    """Response listing the roles assigned to a user."""

    email: str
    roles: list[str]


class TokenData(BaseModel):
    """Decoded claims extracted from a validated Cognito ID token."""

    email: str
    sub: str | None = None
    roles: list[str] = []
