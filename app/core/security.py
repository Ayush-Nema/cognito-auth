"""JWT verification and role-based access control utilities for Cognito-issued tokens."""

import time
from collections.abc import Callable

import httpx
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from jose import JWTError, jwt

from app.core.config import settings
from app.domain.models import TokenData

JWKS_URL = (
    f"https://cognito-idp.{settings.aws_region}.amazonaws.com"
    f"/{settings.cognito_user_pool_id}/.well-known/jwks.json"
)
ISSUER = (
    f"https://cognito-idp.{settings.aws_region}.amazonaws.com"
    f"/{settings.cognito_user_pool_id}"
)

_JWKS_TTL = settings.jwks_ttl

_jwks_cache: dict | None = None
_jwks_cache_time: float = 0.0

http_bearer = HTTPBearer()


def _get_jwks() -> dict:
    """Fetch and cache the Cognito JSON Web Key Set, refreshing after TTL expires."""
    global _jwks_cache, _jwks_cache_time
    if _jwks_cache is None or time.monotonic() - _jwks_cache_time > _JWKS_TTL:
        response = httpx.get(JWKS_URL)
        response.raise_for_status()
        _jwks_cache = response.json()
        _jwks_cache_time = time.monotonic()
    return _jwks_cache


def verify_token(token: str) -> TokenData:
    """Decode and validate a Cognito ID token, returning the extracted claims.

    Raises HTTP 401 if the token is malformed, has an unknown key ID,
    fails signature verification, or does not satisfy issuer / token_use checks.
    """

    def _fail(reason: str) -> HTTPException:
        return HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=f"Token validation failed: {reason}",
            headers={"WWW-Authenticate": "Bearer"},
        )

    try:
        jwks = _get_jwks()
        header = jwt.get_unverified_header(token)
        key = next((k for k in jwks["keys"] if k["kid"] == header.get("kid")), None)
        if key is None:
            raise _fail(f"no matching key for kid={header.get('kid')}")

        payload = jwt.decode(
            token,
            key,
            algorithms=[settings.jwt_algorithm],
            options={"verify_aud": False},
        )

        if payload.get("iss") != ISSUER:
            raise _fail(
                f"iss mismatch: got {payload.get('iss')!r}, expected {ISSUER!r}"
            )
        if payload.get("token_use") != settings.token_use:
            raise _fail(
                f"token_use is {payload.get('token_use')!r}, expected {settings.token_use!r}"
            )

        email: str | None = payload.get("email")
        if email is None:
            raise _fail("email claim not present in token")

        roles: list[str] = payload.get("cognito:groups", [])

        return TokenData(email=email, sub=payload.get("sub"), roles=roles)
    except JWTError as exc:
        raise _fail(str(exc)) from exc


def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(http_bearer),
) -> TokenData:
    """FastAPI dependency that extracts and validates the Bearer token from the request."""
    return verify_token(credentials.credentials)


def require_role(*allowed_roles: str) -> Callable:
    """Return a FastAPI dependency that enforces role-based access control.

    Usage:
        @router.post("/admin-only")
        async def admin_endpoint(user: TokenData = Depends(require_role("admin"))):
            ...
    """

    def role_checker(
        current_user: TokenData = Depends(get_current_user),
    ) -> TokenData:
        if not any(role in current_user.roles for role in allowed_roles):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"This action requires one of the following roles: {', '.join(allowed_roles)}",
            )
        return current_user

    return role_checker
