from __future__ import annotations

import re
from typing import Annotated, Optional

from fastapi import Header, HTTPException
import jwt
from jwt import InvalidTokenError

from app.config import settings

_BEARER = re.compile(r"^\s*Bearer\s+(.+?)\s*$", re.IGNORECASE | re.DOTALL)


def _tenant_from_jwt(token: str) -> str:
    kwargs: dict[str, object] = {
        "algorithms": [settings.jwt_algorithm],
    }
    if settings.jwt_audience:
        kwargs["audience"] = settings.jwt_audience
    if settings.jwt_issuer:
        kwargs["issuer"] = settings.jwt_issuer
    try:
        claims = jwt.decode(token, settings.jwt_secret, **kwargs)
    except InvalidTokenError as e:
        raise HTTPException(status_code=401, detail="Invalid JWT token") from e
    tenant_raw = claims.get(settings.jwt_tenant_claim)
    tenant_id = str(tenant_raw).strip() if tenant_raw is not None else ""
    if not tenant_id:
        raise HTTPException(
            status_code=401,
            detail=f"JWT is missing required tenant claim: {settings.jwt_tenant_claim}",
        )
    return tenant_id


def _tenant_from_auth(
    authorization: Optional[str],
    x_api_key: Optional[str],
) -> str:
    token: Optional[str] = None
    if authorization:
        m = _BEARER.match(authorization)
        if m:
            token = m.group(1).strip()
        elif authorization.strip():
            raise HTTPException(
                status_code=401,
                detail="Authorization must be Bearer <token>",
            )
    if not token and x_api_key is not None and x_api_key.strip():
        token = x_api_key.strip()
        if not settings.api_keys:
            raise HTTPException(
                status_code=401,
                detail="X-API-Key is unsupported unless API key auth is configured",
            )
    if not token:
        raise HTTPException(
            status_code=401,
            detail=(
                "Authentication required: send Authorization: Bearer <api_key_or_jwt>"
                " (or X-API-Key when API keys are configured)"
            ),
        )
    if settings.api_keys:
        tenant_from_key = settings.api_keys.get(token)
        if tenant_from_key is not None:
            return tenant_from_key
    if settings.jwt_secret:
        return _tenant_from_jwt(token)
    raise HTTPException(status_code=401, detail="Invalid API key")


def _tenant_from_header(x_tenant_id: Optional[str]) -> str:
    if x_tenant_id is None or not x_tenant_id.strip():
        raise HTTPException(status_code=400, detail="X-Tenant-ID is required when API keys are not configured")
    return x_tenant_id.strip()


def get_tenant_id(
    authorization: Annotated[Optional[str], Header()] = None,
    x_api_key: Annotated[Optional[str], Header(alias="X-API-Key")] = None,
    x_tenant_id: Annotated[Optional[str], Header(alias="X-Tenant-ID")] = None,
) -> str:
    """Resolve tenant from auth (API key/JWT) when configured, else X-Tenant-ID (dev)."""
    if settings.api_keys or settings.jwt_secret:
        return _tenant_from_auth(authorization, x_api_key)
    return _tenant_from_header(x_tenant_id)


def require_admin_token(
    x_admin_token: Annotated[Optional[str], Header(alias="X-Admin-Token")] = None,
) -> None:
    if not settings.admin_token:
        raise HTTPException(status_code=503, detail="admin API is disabled")
    if x_admin_token is None or x_admin_token.strip() != settings.admin_token:
        raise HTTPException(status_code=401, detail="invalid admin token")


# Backwards-compatible name for modules that depended on the old helper.
require_tenant_id = get_tenant_id
