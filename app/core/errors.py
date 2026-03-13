"""Cognito error handling utilities."""

from botocore.exceptions import ClientError
from fastapi import HTTPException

_COGNITO_ERROR_MAP: dict[str, tuple[int, str]] = {
    "UserNotFoundException": (404, "User not found"),
    "NotAuthorizedException": (401, "Incorrect email or password"),
    "UserNotConfirmedException": (403, "Email not confirmed. Please verify your email first"),
    "UsernameExistsException": (409, "An account with this email already exists"),
    "AliasExistsException": (409, "An account with this email already exists"),
    "CodeMismatchException": (400, "Invalid verification code"),
    "ExpiredCodeException": (400, "Verification code has expired. Request a new one"),
    "InvalidPasswordException": (400, "Password does not meet requirements"),
    "LimitExceededException": (429, "Request limit exceeded. Please try again later"),
    "TooManyRequestsException": (429, "Too many requests. Please try again later"),
    "InvalidParameterException": (400, "Invalid parameter provided"),
    "PasswordResetRequiredException": (403, "Password reset required"),
}


def handle_cognito_error(e: ClientError) -> HTTPException:
    """Map a Cognito ClientError to an HTTPException with an appropriate status code.

    Falls back to HTTP 400 with the raw Cognito message for unmapped error codes.
    """
    code = e.response["Error"]["Code"]
    status_code, message = _COGNITO_ERROR_MAP.get(
        code, (400, e.response["Error"]["Message"])
    )
    return HTTPException(status_code=status_code, detail=message)
