"""
FORGE 2.3 — Pillar Assessors Common Utilities

Shared helper functions used across all pillar assessor modules.
"""
import boto3
from datetime import datetime, timezone
from botocore.exceptions import ClientError, NoCredentialsError


def get_client(service, region):
    """Create boto3 client for a service. Returns None if service unavailable."""
    try:
        return boto3.client(service, region_name=region)
    except Exception:
        return None


class NullClient:
    """Dummy client that returns error on any method call."""
    def __getattr__(self, name):
        def method(*args, **kwargs):
            raise ClientError(
                {"Error": {"Code": "ServiceUnavailable", "Message": "Service not available"}},
                name)
        return method


def get_client_safe(service, region):
    """Create boto3 client, returns NullClient if creation fails."""
    try:
        return boto3.client(service, region_name=region)
    except Exception:
        return NullClient()


def safe_call(fn, default=None):
    """Safely call an AWS API and return result or default on error.
    Handles: AccessDenied, service not in region, endpoint not found,
    invalid credentials, throttling, and any other exception."""
    try:
        return fn()
    except ClientError as e:
        return {"_error": str(e), "_code": e.response["Error"]["Code"]}
    except NoCredentialsError:
        return {"_error": "No AWS credentials configured", "_code": "NoCredentials"}
    except Exception as e:
        # Catches: EndpointConnectionError, UnknownServiceError,
        # BotoCoreError, ConnectionError, etc.
        return {"_error": str(e), "_code": type(e).__name__}


def make_criterion(index, name, met, evidence, confidence=80):
    """Build a criterion result dict."""
    return {
        "index": index,
        "name": name,
        "met": met,
        "evidence": {
            "description": evidence,
            "confidence_percent": confidence,
            "timestamp": datetime.now(timezone.utc).isoformat()
        }
    }
