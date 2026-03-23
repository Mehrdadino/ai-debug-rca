from __future__ import annotations

import re
from typing import Annotated, Optional

from fastapi import Header, HTTPException

from app.config import settings

_BEARER = re.compile(r"^\s*Bearer\s+(.+?)\s*$", re.IGNORECASE | re.DOTALL)


def _tenant_from_api_key(authorization: Optional[str], x_api_key: Optional[str]) -> str:
    token: Optional[str] = None
    if authorization:
        m = _BEARER.match(authorization)
        if m:
            token = m.group(1).strip()
        elif authorization.strip():
            # Reject malformed Authorization so clients do not assume it worked.
            raise HTTPException(
                status_code=401,
                detail="Authorization must be Bearer <api_key> when using API key auth",
            )
    if not token and x_api_key is not None and x_api_key.strip():
        token = x_api_key.strip()
    if not token:
        raise HTTPException(
            status_code=401,
            detail="Authentication required: send Authorization: Bearer <api_key> or X-API-Key",
        )
    tenant_id = settings.api_keys.get(token)
    if tenant_id is None:
        raise HTTPException(status_code=401, detail="Invalid API key")
    return tenant_id


def _tenant_from_header(x_tenant_id: Optional[str]) -> str:
    if x_tenant_id is None or not x_tenant_id.strip():
        raise HTTPException(status_code=400, detail="X-Tenant-ID is required when API keys are not configured")
    return x_tenant_id.strip()


def get_tenant_id(
    authorization: Annotated[Optional[str], Header()] = None,
    x_api_key: Annotated[Optional[str], Header(alias="X-API-Key")] = None,
    x_tenant_id: Annotated[Optional[str], Header(alias="X-Tenant-ID")] = None,
) -> str:
    """Resolve tenant: server-issued mapping from API keys when configured, else X-Tenant-ID (dev)."""
    if settings.api_keys:
        return _tenant_from_api_key(authorization, x_api_key)
    return _tenant_from_header(x_tenant_id)


# Backwards-compatible name for modules that depended on the old helper.
require_tenant_id = get_tenant_id
