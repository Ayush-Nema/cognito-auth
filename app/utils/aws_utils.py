"""AWS utility helpers."""

import json

import boto3
from botocore.exceptions import ClientError

from app.core.config import settings


_clients: dict[str, object] = {}


def _get_client(service_name: str, region_name: str | None = None):
    """Return a cached boto3 client for the given service."""
    region = region_name or settings.aws_region
    key = f"{service_name}:{region}"
    if key not in _clients:
        _clients[key] = boto3.client(service_name, region_name=region)
    return _clients[key]


def get_secret(secret_name: str, region_name: str | None = None) -> dict:
    """Fetch and JSON-decode a secret from AWS Secrets Manager."""
    client = _get_client("secretsmanager", region_name=region_name)
    try:
        response = client.get_secret_value(SecretId=secret_name)
    except ClientError:
        raise
    return json.loads(response["SecretString"])
