from typing import Annotated

from fastapi import Header, HTTPException

TenantId = Annotated[str, Header(alias="X-Tenant-ID")]


def require_tenant_id(x_tenant_id: TenantId) -> str:
    if not x_tenant_id.strip():
        raise HTTPException(status_code=400, detail="X-Tenant-ID is required")
    return x_tenant_id.strip()
