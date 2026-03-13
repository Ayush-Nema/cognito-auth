"""Data-access layer wrapping the AWS Cognito Identity Provider client."""

import boto3
from botocore.exceptions import ClientError

from app.core.config import settings


class CognitoRepository:
    """Thin wrapper around boto3 cognito-idp for all Cognito operations."""

    def __init__(self):
        """Initialise the boto3 Cognito client for the configured AWS region."""
        self.client = boto3.client("cognito-idp", region_name=settings.aws_region)

    def sign_up_user(self, email: str, password: str):
        """Register a new user in the Cognito User Pool."""
        try:
            return self.client.sign_up(
                ClientId=settings.cognito_client_id,
                Username=email,
                Password=password,
                UserAttributes=[{"Name": "email", "Value": email}],
            )
        except ClientError as e:
            raise e

    def confirm_sign_up(self, email: str, confirmation_code: str):
        """Confirm a user's email address using the code sent by Cognito."""
        try:
            return self.client.confirm_sign_up(
                ClientId=settings.cognito_client_id,
                Username=email,
                ConfirmationCode=confirmation_code,
            )
        except ClientError as e:
            raise e

    def login_user(self, email: str, password: str) -> dict:
        """Authenticate a user and return the id, access, and refresh tokens."""
        try:
            response = self.client.initiate_auth(
                ClientId=settings.cognito_client_id,
                AuthFlow="USER_PASSWORD_AUTH",
                AuthParameters={"USERNAME": email, "PASSWORD": password},
            )
            result = response["AuthenticationResult"]
            return {
                "id_token": result["IdToken"],
                "access_token": result["AccessToken"],
                "refresh_token": result["RefreshToken"],
            }
        except ClientError as e:
            raise e

    def refresh_token(self, refresh_token: str) -> dict:
        """Exchange a refresh token for a new id token and access token."""
        try:
            response = self.client.initiate_auth(
                ClientId=settings.cognito_client_id,
                AuthFlow="REFRESH_TOKEN_AUTH",
                AuthParameters={"REFRESH_TOKEN": refresh_token},
            )
            result = response["AuthenticationResult"]
            return {
                "id_token": result["IdToken"],
                "access_token": result["AccessToken"],
            }
        except ClientError as e:
            raise e

    def logout_user(self, access_token: str):
        """Globally sign out a user, invalidating all their active sessions."""
        try:
            return self.client.global_sign_out(AccessToken=access_token)
        except ClientError as e:
            raise e

    def resend_confirmation_code(self, email: str):
        """Resend the email verification code to the given address."""
        try:
            return self.client.resend_confirmation_code(
                ClientId=settings.cognito_client_id,
                Username=email,
            )
        except ClientError as e:
            raise e

    def forgot_password(self, email: str):
        """Trigger the forgot-password flow, sending a reset code to the user's email."""
        try:
            return self.client.forgot_password(
                ClientId=settings.cognito_client_id,
                Username=email,
            )
        except ClientError as e:
            raise e

    def confirm_forgot_password(
        self, email: str, confirmation_code: str, new_password: str
    ):
        """Complete a password reset using the code sent to the user's email."""
        try:
            return self.client.confirm_forgot_password(
                ClientId=settings.cognito_client_id,
                Username=email,
                ConfirmationCode=confirmation_code,
                Password=new_password,
            )
        except ClientError as e:
            raise e

    def change_password(
        self, access_token: str, old_password: str, new_password: str
    ):
        """Change the password for an authenticated user."""
        try:
            return self.client.change_password(
                AccessToken=access_token,
                PreviousPassword=old_password,
                ProposedPassword=new_password,
            )
        except ClientError as e:
            raise e

    def admin_create_user(self, email: str, temporary_password: str):
        """Create a user via admin API, suppressing the welcome email."""
        try:
            return self.client.admin_create_user(
                UserPoolId=settings.cognito_user_pool_id,
                Username=email,
                TemporaryPassword=temporary_password,
                UserAttributes=[
                    {"Name": "email", "Value": email},
                    {"Name": "email_verified", "Value": "true"},
                ],
                MessageAction="SUPPRESS",
            )
        except ClientError as e:
            raise e

    def admin_delete_user(self, email: str):
        """Delete a user from the User Pool via admin API."""
        try:
            return self.client.admin_delete_user(
                UserPoolId=settings.cognito_user_pool_id,
                Username=email,
            )
        except ClientError as e:
            raise e
