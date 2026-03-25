"""S3-compatible blob storage for full trace JSON (optional; disabled when bucket is unset)."""

from __future__ import annotations

import asyncio
import logging
from urllib.parse import quote

import boto3
from botocore.exceptions import ClientError

from app.config import settings

logger = logging.getLogger(__name__)


def trace_blob_key(tenant_id: str, trace_id: str) -> str:
    """Object key: {encoded_tenant}/{trace_id}/trace.json (environment is not part of the path)."""
    safe_tenant = quote(tenant_id, safe="")
    return f"{safe_tenant}/{trace_id}/trace.json"


def blob_storage_enabled() -> bool:
    return bool(settings.s3_bucket and settings.s3_bucket.strip())


def _s3_client():
    kwargs: dict = {"region_name": settings.s3_region or "us-east-1"}
    if settings.s3_endpoint_url and settings.s3_endpoint_url.strip():
        kwargs["endpoint_url"] = settings.s3_endpoint_url.strip()
    if settings.s3_access_key_id and settings.s3_access_key_id.strip():
        kwargs["aws_access_key_id"] = settings.s3_access_key_id.strip()
    if settings.s3_secret_access_key and settings.s3_secret_access_key.strip():
        kwargs["aws_secret_access_key"] = settings.s3_secret_access_key.strip()
    return boto3.client("s3", **kwargs)


async def put_trace_blob(key: str, body: bytes, content_type: str = "application/json") -> str:
    """Upload bytes; returns ETag (may be quoted)."""
    bucket = settings.s3_bucket.strip()
    client = _s3_client()

    def _put() -> str:
        r = client.put_object(Bucket=bucket, Key=key, Body=body, ContentType=content_type)
        return str(r.get("ETag") or "")

    return await asyncio.to_thread(_put)


async def get_trace_blob(key: str) -> bytes:
    bucket = settings.s3_bucket.strip()
    client = _s3_client()

    def _get() -> bytes:
        r = client.get_object(Bucket=bucket, Key=key)
        return r["Body"].read()

    return await asyncio.to_thread(_get)


async def delete_trace_blob(key: str) -> None:
    """Best-effort delete (e.g. rollback after failed DB commit)."""
    bucket = settings.s3_bucket.strip()
    client = _s3_client()

    def _del() -> None:
        try:
            client.delete_object(Bucket=bucket, Key=key)
        except ClientError as e:
            logger.warning("blob delete failed key=%s: %s", key, e)

    await asyncio.to_thread(_del)


def is_not_found_error(exc: BaseException) -> bool:
    if isinstance(exc, ClientError):
        err = exc.response.get("Error", {})
        return err.get("Code") in ("404", "NoSuchKey", "NotFound")
    return False
