"""Business logic layer for authentication operations."""

import secrets
import string
from botocore.exceptions import ClientError, NoCredentialsError
from fastapi import HTTPException

from app.core.errors import handle_cognito_error
from app.core.logging import get_logger
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

logger = get_logger("app.services.auth_service")


class AuthService:
    """Orchestrates auth flows by delegating to CognitoRepository."""

    def __init__(self):
        """Initialise the service with a CognitoRepository instance."""
        self.repo = CognitoRepository()

    def register_user(self, user: User):
        """Register a new user and prompt them to verify their email."""
        try:
            logger.info("Registering user | email={}", user.email)
            self.repo.sign_up_user(user.email, user.password)
            logger.success("User registered | email={}", user.email)
            return {
                "message": "User registered successfully. Check your email for a verification code"
            }
        except ClientError as e:
            logger.error("Registration failed | email={}: {}", user.email, e)
            raise handle_cognito_error(e) from e

    def confirm_user(self, confirm: ConfirmSignUp):
        """Confirm a user's email address with the provided verification code."""
        try:
            logger.info("Confirming email | email={}", confirm.email)
            self.repo.confirm_sign_up(confirm.email, confirm.confirmation_code)
            logger.success("Email confirmed | email={}", confirm.email)
            return {"message": "Email verified successfully"}
        except ClientError as e:
            logger.error("Confirmation failed | email={}: {}", confirm.email, e)
            raise handle_cognito_error(e) from e

    def login_user(self, user_login: UserLogin):
        """Authenticate a user and return the full token set."""
        try:
            logger.info("Login attempt | email={}", user_login.email)
            tokens = self.repo.login_user(user_login.email, user_login.password)
            logger.success("Login successful | email={}", user_login.email)
            return {**tokens, "token_type": "bearer"}
        except ClientError as e:
            logger.warning("Login failed | email={}: {}", user_login.email, e)
            raise handle_cognito_error(e) from e

    def refresh_token(self, body: RefreshTokenRequest):
        """Issue a new id token and access token from a valid refresh token."""
        try:
            logger.debug("Refreshing token")
            tokens = self.repo.refresh_token(body.refresh_token)
            return {**tokens, "token_type": "bearer"}
        except ClientError as e:
            logger.error("Token refresh failed: {}", e)
            raise handle_cognito_error(e) from e

    def logout_user(self, body: LogoutRequest):
        """Globally sign out the user, invalidating all active sessions."""
        try:
            logger.info("Logging out user")
            self.repo.logout_user(body.access_token)
            return {"message": "Logged out successfully"}
        except ClientError as e:
            logger.error("Logout failed: {}", e)
            raise handle_cognito_error(e) from e

    def resend_confirmation(self, body: ResendConfirmationRequest):
        """Resend the email verification code."""
        try:
            logger.info("Resending confirmation | email={}", body.email)
            self.repo.resend_confirmation_code(body.email)
            return {"message": "Verification code resent. Check your email"}
        except ClientError as e:
            logger.error("Resend confirmation failed | email={}: {}", body.email, e)
            raise handle_cognito_error(e) from e

    def forgot_password(self, body: ForgotPasswordRequest):
        """Trigger the forgot-password flow for the given email address."""
        try:
            logger.info("Forgot password | email={}", body.email)
            self.repo.forgot_password(body.email)
            return {"message": "Password reset code sent to your email"}
        except ClientError as e:
            logger.error("Forgot password failed | email={}: {}", body.email, e)
            raise handle_cognito_error(e) from e

    def reset_password(self, body: ResetPasswordRequest):
        """Complete a password reset using the confirmation code."""
        try:
            logger.info("Resetting password | email={}", body.email)
            self.repo.confirm_forgot_password(
                body.email, body.confirmation_code, body.new_password
            )
            logger.success("Password reset | email={}", body.email)
            return {"message": "Password reset successfully"}
        except ClientError as e:
            logger.error("Password reset failed | email={}: {}", body.email, e)
            raise handle_cognito_error(e) from e

    def change_password(self, body: ChangePasswordRequest):
        """Change the password for an already-authenticated user."""
        try:
            logger.info("Changing password")
            self.repo.change_password(
                body.access_token, body.old_password, body.new_password
            )
            logger.success("Password changed")
            return {"message": "Password changed successfully"}
        except ClientError as e:
            logger.error("Password change failed: {}", e)
            raise handle_cognito_error(e) from e

    def admin_create_user(self, body: AdminCreateUserRequest):
        """Create a user via the admin API with a generated temporary password."""
        try:
            logger.info("Admin creating user | email={}", body.email)
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
            logger.success("Admin user created | email={}", body.email)
            return {
                "message": f"User {body.email} created successfully",
                "temporary_password": temporary_password,
            }
        except NoCredentialsError as e:
            logger.error("AWS credentials not configured for admin_create_user")
            raise HTTPException(
                status_code=500, detail="AWS credentials not configured"
            ) from e
        except ClientError as e:
            logger.error("Admin create user failed | email={}: {}", body.email, e)
            raise handle_cognito_error(e) from e

    def admin_delete_user(self, email: str):
        """Delete a user from the User Pool via the admin API."""
        try:
            logger.info("Admin deleting user | email={}", email)
            self.repo.admin_delete_user(email)
            logger.success("Admin user deleted | email={}", email)
            return {"message": f"User {email} deleted successfully"}
        except NoCredentialsError as e:
            logger.error("AWS credentials not configured for admin_delete_user")
            raise HTTPException(
                status_code=500, detail="AWS credentials not configured"
            ) from e
        except ClientError as e:
            logger.error("Admin delete user failed | email={}: {}", email, e)
            raise handle_cognito_error(e) from e
