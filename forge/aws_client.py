"""
FORGE 2.3 — Shared AWS Client Factory

Provides centralized boto3 client creation with:
- Same-account role assumption via STS (FORGE-Assessment-Role)
- Session tags for CloudTrail audit filtering
- Retry configuration (adaptive mode, max 2 attempts)
- Connection timeouts (5s connect, 10s read)
- Safe call wrapper for graceful error handling
"""
import boto3
from botocore.config import Config
from botocore.exceptions import ClientError, NoCredentialsError
from datetime import datetime
from typing import Optional, Any, Callable


# Shared retry configuration
RETRY_CONFIG = Config(
    retries={"max_attempts": 2, "mode": "adaptive"},
    connect_timeout=5,
    read_timeout=10,
)


def create_client(
    service: str,
    region: str,
    account_id: str,
    run_id: str,
    session: Optional[boto3.Session] = None,
    profile_name: Optional[str] = None,
):
    """Create a boto3 client by assuming FORGE-Assessment-Role in the same account.

    Automatically:
    - Derives role ARN: arn:aws:iam::{account_id}:role/FORGE-Assessment-Role
    - Sets RoleSessionName: forge-skill-<ISO8601-timestamp>
    - Includes session tags: forge-skill, forge-version, forge-run-id
    - DurationSeconds: 3600

    Args:
        service: AWS service name (e.g., 'glue', 's3', 'iam')
        region: AWS region (e.g., 'us-east-1')
        account_id: AWS account ID where FORGE-Assessment-Role exists
        run_id: Unique assessment run identifier for session tagging
        session: Optional existing boto3 session to reuse
        profile_name: Optional AWS profile name from ~/.aws/credentials

    Returns:
        boto3 client for the specified service

    Raises:
        ClientError: If role assumption fails
    """
    if session is None:
        session = boto3.Session(profile_name=profile_name)

    role_arn = f"arn:aws:iam::{account_id}:role/FORGE-Assessment-Role"
    timestamp = datetime.utcnow().strftime("%Y%m%dT%H%M%S")

    sts = session.client("sts", config=RETRY_CONFIG)
    creds = sts.assume_role(
        RoleArn=role_arn,
        RoleSessionName=f"forge-skill-{timestamp}",
        DurationSeconds=3600,
        Tags=[
            {"Key": "forge-skill", "Value": run_id},
            {"Key": "forge-version", "Value": "2.3.0"},
            {"Key": "forge-run-id", "Value": run_id},
        ],
    )["Credentials"]

    assumed_session = boto3.Session(
        aws_access_key_id=creds["AccessKeyId"],
        aws_secret_access_key=creds["SecretAccessKey"],
        aws_session_token=creds["SessionToken"],
    )

    return assumed_session.client(service, region_name=region, config=RETRY_CONFIG)


def safe_call(fn: Callable, default: Any = None) -> Any:
    """Execute an AWS API call with comprehensive error handling.

    Returns the API result on success, or a dict with '_error' and '_code'
    keys on failure. Never raises exceptions.

    Args:
        fn: Callable that makes the AWS API call
        default: Default value if all else fails (not typically used)

    Returns:
        API response dict on success, or error dict on failure
    """
    try:
        return fn()
    except ClientError as e:
        code = e.response["Error"]["Code"]
        return {"_error": str(e), "_code": code}
    except NoCredentialsError:
        return {"_error": "No AWS credentials configured", "_code": "NoCredentials"}
    except Exception as e:
        return {"_error": str(e), "_code": type(e).__name__}


def is_error(result: Any) -> bool:
    """Check if a result from safe_call is an error response."""
    return isinstance(result, dict) and "_error" in result


def is_access_denied(result: Any) -> bool:
    """Check if a result from safe_call is an access denied error."""
    if not is_error(result):
        return False
    code = result.get("_code", "")
    return code in ("AccessDeniedException", "AccessDenied", "UnauthorizedOperation")
