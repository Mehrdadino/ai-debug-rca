"""S3-compatible blob storage for full trace JSON (optional; disabled when bucket is unset)."""

from __future__ import annotations

import asyncio
import logging
import random
import time
from typing import Any, Callable, Optional
from urllib.parse import quote

import boto3
from botocore.exceptions import BotoCoreError, ClientError

from app.config import settings

logger = logging.getLogger(__name__)
_MAX_ATTEMPTS = 3
_BASE_BACKOFF_SECONDS = 0.2


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


def _is_retryable_error(exc: BaseException) -> bool:
    if isinstance(exc, ClientError):
        err = exc.response.get("Error", {})
        code = str(err.get("Code", ""))
        status = int(exc.response.get("ResponseMetadata", {}).get("HTTPStatusCode", 0) or 0)
        if status in (429, 500, 502, 503, 504):
            return True
        if code in (
            "RequestTimeout",
            "RequestTimeoutException",
            "SlowDown",
            "Throttling",
            "ThrottlingException",
            "InternalError",
            "ServiceUnavailable",
        ):
            return True
    return isinstance(exc, BotoCoreError)


async def _with_retries(op_name: str, key: str, op: Callable[[], Any]) -> Any:
    last_exc: Optional[BaseException] = None
    started = time.perf_counter()
    for attempt in range(1, _MAX_ATTEMPTS + 1):
        try:
            result = await asyncio.to_thread(op)
            elapsed_ms = int((time.perf_counter() - started) * 1000)
            logger.info("s3.%s success key=%s attempt=%d elapsed_ms=%d", op_name, key, attempt, elapsed_ms)
            return result
        except Exception as exc:  # noqa: BLE001
            last_exc = exc
            retryable = _is_retryable_error(exc)
            elapsed_ms = int((time.perf_counter() - started) * 1000)
            logger.warning(
                "s3.%s failure key=%s attempt=%d retryable=%s elapsed_ms=%d error=%s",
                op_name,
                key,
                attempt,
                retryable,
                elapsed_ms,
                type(exc).__name__,
            )
            if (not retryable) or attempt >= _MAX_ATTEMPTS:
                raise
            sleep_s = _BASE_BACKOFF_SECONDS * (2 ** (attempt - 1)) + random.uniform(0, 0.1)
            await asyncio.sleep(sleep_s)
    if last_exc is not None:
        raise last_exc
    raise RuntimeError(f"s3.{op_name} failed without exception")


async def put_trace_blob(key: str, body: bytes, content_type: str = "application/json") -> str:
    """Upload bytes; returns ETag (may be quoted)."""
    bucket = settings.s3_bucket.strip()
    client = _s3_client()

    def _put() -> str:
        r = client.put_object(Bucket=bucket, Key=key, Body=body, ContentType=content_type)
        return str(r.get("ETag") or "")

    return await _with_retries("put", key, _put)


async def get_trace_blob(key: str) -> bytes:
    bucket = settings.s3_bucket.strip()
    client = _s3_client()

    def _get() -> bytes:
        r = client.get_object(Bucket=bucket, Key=key)
        return r["Body"].read()

    return await _with_retries("get", key, _get)


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
