from __future__ import annotations

import pytest
from botocore.exceptions import ClientError

from app.config import settings
from app.services import blob_storage


def _client_error(code: str, status: int) -> ClientError:
    return ClientError(
        {
            "Error": {"Code": code, "Message": "boom"},
            "ResponseMetadata": {"HTTPStatusCode": status},
        },
        operation_name="TestOp",
    )


def test_is_retryable_error_for_transient_status() -> None:
    assert blob_storage._is_retryable_error(_client_error("InternalError", 503))


def test_is_retryable_error_for_throttling_code() -> None:
    assert blob_storage._is_retryable_error(_client_error("SlowDown", 400))


def test_is_retryable_error_for_not_found_is_false() -> None:
    assert not blob_storage._is_retryable_error(_client_error("NoSuchKey", 404))


@pytest.mark.asyncio
async def test_put_trace_blob_retries_then_succeeds(monkeypatch: pytest.MonkeyPatch) -> None:
    class FakeClient:
        def __init__(self) -> None:
            self.calls = 0

        def put_object(self, **kwargs):
            self.calls += 1
            if self.calls < 3:
                raise _client_error("ServiceUnavailable", 503)
            return {"ETag": '"etag-1"'}

    fake = FakeClient()
    monkeypatch.setattr(settings, "s3_bucket", "bucket-test")
    monkeypatch.setattr(blob_storage, "_s3_client", lambda: fake)
    monkeypatch.setattr(blob_storage, "_BASE_BACKOFF_SECONDS", 0.0)
    monkeypatch.setattr(blob_storage.random, "uniform", lambda _a, _b: 0.0)

    etag = await blob_storage.put_trace_blob("k", b"{}", "application/json")
    assert etag == '"etag-1"'
    assert fake.calls == 3


@pytest.mark.asyncio
async def test_get_trace_blob_does_not_retry_not_found(monkeypatch: pytest.MonkeyPatch) -> None:
    class FakeClient:
        def __init__(self) -> None:
            self.calls = 0

        def get_object(self, **kwargs):
            self.calls += 1
            raise _client_error("NoSuchKey", 404)

    fake = FakeClient()
    monkeypatch.setattr(settings, "s3_bucket", "bucket-test")
    monkeypatch.setattr(blob_storage, "_s3_client", lambda: fake)
    monkeypatch.setattr(blob_storage, "_BASE_BACKOFF_SECONDS", 0.0)
    monkeypatch.setattr(blob_storage.random, "uniform", lambda _a, _b: 0.0)

    with pytest.raises(ClientError):
        await blob_storage.get_trace_blob("k")
    assert fake.calls == 1
