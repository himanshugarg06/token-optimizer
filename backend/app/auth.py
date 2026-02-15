"""Authentication middleware for API key validation."""

import httpx
from fastapi import HTTPException, Security, status
from fastapi.security import APIKeyHeader
from app.settings import settings


# API Key header scheme
api_key_header = APIKeyHeader(name="X-API-Key", auto_error=False)


async def verify_api_key(api_key: str = Security(api_key_header)) -> str:
    """
    Verify the API key from request header.

    Accept either the middleware key (shared secret) or a user API key
    validated via the dashboard service (/api/keys/validate).
    """
    if not api_key:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing API key. Provide X-API-Key header."
        )

    # Fast path: shared middleware key
    if api_key == settings.middleware_api_key:
        return api_key

    # Fallback: validate against dashboard (Next) API keys
    if settings.dashboard_enabled and settings.dashboard_base_url:
        try:
            url = f"{settings.dashboard_base_url.rstrip('/')}/api/keys/validate"
            async with httpx.AsyncClient(timeout=3.0) as client:
                resp = await client.post(url, json={"apiKey": api_key})
            if resp.status_code == 200:
                data = resp.json()
                if data.get("valid"):
                    return api_key
        except Exception:
            # fall through to error below
            pass

    raise HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Invalid API key"
    )
