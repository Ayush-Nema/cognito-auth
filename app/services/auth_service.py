"""Business logic layer for authentication operations."""

import secrets
import string
from botocore.exceptions import ClientError, NoCredentialsError
from fastapi import HTTPException

from app.core.errors import handle_cognito_error
from app.domain.models import (
    AdminCreateUserRequest,
    ChangePasswordRequest,
    ConfirmSignUp,
    ForgotPasswordRequest,
    LogoutRequest,
    RefreshTokenRequest,
    ResendConfirmationRequest,
    ResetPasswordRequest,
    User,
    UserLogin,
)
from app.repository.cognito_repository import CognitoRepository


class AuthService:
    """Orchestrates auth flows by delegating to CognitoRepository."""

    def __init__(self):
        """Initialise the service with a CognitoRepository instance."""
        self.repo = CognitoRepository()

    def register_user(self, user: User):
        """Register a new user and prompt them to verify their email."""
        try:
            self.repo.sign_up_user(user.email, user.password)
            return {"message": "User registered successfully. Check your email for a verification code"}
        except ClientError as e:
            raise handle_cognito_error(e) from e

    def confirm_user(self, confirm: ConfirmSignUp):
        """Confirm a user's email address with the provided verification code."""
        try:
            self.repo.confirm_sign_up(confirm.email, confirm.confirmation_code)
            return {"message": "Email verified successfully"}
        except ClientError as e:
            raise handle_cognito_error(e) from e

    def login_user(self, user_login: UserLogin):
        """Authenticate a user and return the full token set."""
        try:
            tokens = self.repo.login_user(user_login.email, user_login.password)
            return {**tokens, "token_type": "bearer"}
        except ClientError as e:
            raise handle_cognito_error(e) from e

    def refresh_token(self, body: RefreshTokenRequest):
        """Issue a new id token and access token from a valid refresh token."""
        try:
            tokens = self.repo.refresh_token(body.refresh_token)
            return {**tokens, "token_type": "bearer"}
        except ClientError as e:
            raise handle_cognito_error(e) from e

    def logout_user(self, body: LogoutRequest):
        """Globally sign out the user, invalidating all active sessions."""
        try:
            self.repo.logout_user(body.access_token)
            return {"message": "Logged out successfully"}
        except ClientError as e:
            raise handle_cognito_error(e) from e

    def resend_confirmation(self, body: ResendConfirmationRequest):
        """Resend the email verification code."""
        try:
            self.repo.resend_confirmation_code(body.email)
            return {"message": "Verification code resent. Check your email"}
        except ClientError as e:
            raise handle_cognito_error(e) from e

    def forgot_password(self, body: ForgotPasswordRequest):
        """Trigger the forgot-password flow for the given email address."""
        try:
            self.repo.forgot_password(body.email)
            return {"message": "Password reset code sent to your email"}
        except ClientError as e:
            raise handle_cognito_error(e) from e

    def reset_password(self, body: ResetPasswordRequest):
        """Complete a password reset using the confirmation code."""
        try:
            self.repo.confirm_forgot_password(
                body.email, body.confirmation_code, body.new_password
            )
            return {"message": "Password reset successfully"}
        except ClientError as e:
            raise handle_cognito_error(e) from e

    def change_password(self, body: ChangePasswordRequest):
        """Change the password for an already-authenticated user."""
        try:
            self.repo.change_password(
                body.access_token, body.old_password, body.new_password
            )
            return {"message": "Password changed successfully"}
        except ClientError as e:
            raise handle_cognito_error(e) from e

    def admin_create_user(self, body: AdminCreateUserRequest):
        """Create a user via the admin API with a generated temporary password."""
        try:
            alphabet = string.ascii_letters + string.digits + "!@#$%^&*"
            # Guarantee at least one character from each required character class
            temporary_password = (
                secrets.choice(string.ascii_uppercase)
                + secrets.choice(string.ascii_lowercase)
                + secrets.choice(string.digits)
                + secrets.choice("!@#$%^&*")
                + "".join(secrets.choice(alphabet) for _ in range(8))
            )
            self.repo.admin_create_user(body.email, temporary_password)
            return {"message": f"User {body.email} created successfully", "temporary_password": temporary_password}
        except NoCredentialsError as e:
            raise HTTPException(status_code=500, detail="AWS credentials not configured") from e
        except ClientError as e:
            raise handle_cognito_error(e) from e

    def admin_delete_user(self, email: str):
        """Delete a user from the User Pool via the admin API."""
        try:
            self.repo.admin_delete_user(email)
            return {"message": f"User {email} deleted successfully"}
        except NoCredentialsError as e:
            raise HTTPException(status_code=500, detail="AWS credentials not configured") from e
        except ClientError as e:
            raise handle_cognito_error(e) from e
