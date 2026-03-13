"""Application configuration loaded from configs/configs.yaml."""

from pathlib import Path

import yaml
from pydantic import BaseModel, model_validator

_CONFIG_PATH = Path(__file__).parent.parent.parent / "configs" / "configs.yaml"


class Settings(BaseModel):
    """All application settings parsed from the YAML config file."""

    aws_region: str
    cognito_user_pool_id: str
    cognito_client_id: str
    allowed_hosts: list[str]
    host: str
    port: int
    jwks_ttl: float
    jwt_algorithm: str
    token_use: str
    rate_limit_signup: str
    rate_limit_login: str
    rate_limit_forgot_password: str

    @model_validator(mode="after")
    def validate_cognito_settings(self) -> "Settings":
        """Ensure required Cognito identifiers are present."""
        if not self.cognito_user_pool_id:
            raise ValueError("cognito.user_pool_id is required")
        if not self.cognito_client_id:
            raise ValueError("cognito.client_id is required")
        return self


def _load_settings() -> Settings:
    """Read configs.yaml and return a populated Settings instance."""
    with open(_CONFIG_PATH) as f:
        raw = yaml.safe_load(f)
    return Settings(
        aws_region=raw["aws"]["region"],
        cognito_user_pool_id=raw["cognito"]["user_pool_id"],
        cognito_client_id=raw["cognito"]["client_id"],
        allowed_hosts=raw["app"]["allowed_hosts"],
        host=raw["app"]["host"],
        port=raw["app"]["port"],
        jwks_ttl=raw["security"]["jwks_ttl"],
        jwt_algorithm=raw["security"]["jwt_algorithm"],
        token_use=raw["security"]["token_use"],
        rate_limit_signup=raw["rate_limits"]["signup"],
        rate_limit_login=raw["rate_limits"]["login"],
        rate_limit_forgot_password=raw["rate_limits"]["forgot_password"],
    )


settings = _load_settings()
