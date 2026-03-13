"""API v1 route definitions for authentication endpoints."""

from fastapi import APIRouter, Depends, Request

from app.core.config import settings
from app.core.limiter import limiter
from app.core.security import get_current_user
from app.domain.models import (
    AdminCreateUserRequest,
    AdminCreateUserResponse,
    AuthResponse,
    ChangePasswordRequest,
    ConfirmSignUp,
    ForgotPasswordRequest,
    GreetingResponse,
    LogoutRequest,
    MessageResponse,
    RefreshTokenRequest,
    ResendConfirmationRequest,
    ResetPasswordRequest,
    TokenData,
    TokenRefreshResponse,
    User,
    UserLogin,
)
from app.services.auth_service import AuthService

router = APIRouter()
auth_service = AuthService()


@router.post("/signup", response_model=MessageResponse)
@limiter.limit(settings.rate_limit_signup)
async def signup(request: Request, user: User):
    """Register a new user and send an email verification code."""
    return auth_service.register_user(user)


@router.post("/confirm", response_model=MessageResponse)
async def confirm(confirm_data: ConfirmSignUp):
    """Confirm a user's email address using the verification code."""
    return auth_service.confirm_user(confirm_data)


@router.post("/login", response_model=AuthResponse)
@limiter.limit(settings.rate_limit_login)
async def login(request: Request, user_login: UserLogin):
    """Authenticate a user and return id, access, and refresh tokens."""
    return auth_service.login_user(user_login)


@router.post("/refresh", response_model=TokenRefreshResponse)
async def refresh(body: RefreshTokenRequest):
    """Exchange a refresh token for a new id token and access token."""
    return auth_service.refresh_token(body)


@router.post("/logout", response_model=MessageResponse)
async def logout(
    body: LogoutRequest,
    _: TokenData = Depends(get_current_user),
):
    """Globally sign out the authenticated user."""
    return auth_service.logout_user(body)


@router.post("/resend-confirmation", response_model=MessageResponse)
async def resend_confirmation(body: ResendConfirmationRequest):
    """Resend the email verification code to the given address."""
    return auth_service.resend_confirmation(body)


@router.post("/forgot-password", response_model=MessageResponse)
@limiter.limit(settings.rate_limit_forgot_password)
async def forgot_password(request: Request, body: ForgotPasswordRequest):
    """Initiate the forgot-password flow and send a reset code by email."""
    return auth_service.forgot_password(body)


@router.post("/reset-password", response_model=MessageResponse)
async def reset_password(body: ResetPasswordRequest):
    """Complete a password reset using the emailed confirmation code."""
    return auth_service.reset_password(body)


@router.put("/change-password", response_model=MessageResponse)
async def change_password(
    body: ChangePasswordRequest,
    _: TokenData = Depends(get_current_user),
):
    """Change the password for the currently authenticated user."""
    return auth_service.change_password(body)


@router.get("/me", response_model=TokenData)
async def get_me(current_user: TokenData = Depends(get_current_user)):
    """Return the decoded token claims for the currently authenticated user."""
    return current_user


@router.get("/hello", response_model=GreetingResponse)
async def hello(current_user: TokenData = Depends(get_current_user)):
    """Protected dummy endpoint that confirms authentication and returns the user's email."""
    return GreetingResponse(
        message="You are authenticated!",
        email=current_user.email,
    )


@router.post("/users", response_model=AdminCreateUserResponse, status_code=201)
async def create_user(
    body: AdminCreateUserRequest,
    _: TokenData = Depends(get_current_user),
):
    """Admin endpoint to create a new user with a generated temporary password."""
    return auth_service.admin_create_user(body)


@router.delete("/users/{email}", response_model=MessageResponse)
async def delete_user(
    email: str,
    _: TokenData = Depends(get_current_user),
):
    """Admin endpoint to delete a user from the User Pool."""
    return auth_service.admin_delete_user(email)
