"""Mock dashboard server for testing."""

from fastapi import APIRouter, Header, HTTPException
from typing import Optional
import logging

logger = logging.getLogger(__name__)

# Create router for mock endpoints.
# We expose both:
# - /api/v1/...  (what DashboardClient calls)
# - /mock/v1/... (legacy/local testing)
api_router = APIRouter(prefix="/api/v1")
mock_router = APIRouter(prefix="/mock/v1")

@api_router.get("/config/{tenant_id}/{project_id}")
@mock_router.get("/config/{tenant_id}/{project_id}")
async def mock_get_config(
    tenant_id: str,
    project_id: str,
    x_api_key: Optional[str] = Header(None)
):
    """
    Mock endpoint for fetching user configuration.

    Returns a stub configuration for testing.
    """
    logger.info(f"Mock config request: {tenant_id}/{project_id}")

    if not x_api_key:
        raise HTTPException(status_code=401, detail="Missing API key")

    # Return mock config
    return {
        "tenant_id": tenant_id,
        "project_id": project_id,
        "config": {
            "maxHistoryMessages": 4,
            "includeSystemMessages": True,
            "maxTokensPerCall": 8000,
            "maxInputTokens": 8000,
            "aggressiveness": "medium",
            "preserveCodeBlocks": True,
            "preserveFormatting": True,
            "targetCostReduction": 0.5
        },
        "updated_at": "2026-02-15T10:00:00Z"
    }


@api_router.post("/events")
@mock_router.post("/events")
async def mock_emit_event(
    event: dict,
    x_api_key: Optional[str] = Header(None),
    x_source: Optional[str] = Header(None)
):
    """
    Mock endpoint for receiving optimization events.

    Logs events for testing/debugging.
    """
    logger.info(f"Mock event received: {event.get('event_type')} from {x_source}")
    logger.debug(f"Event details: {event}")

    if not x_api_key:
        raise HTTPException(status_code=401, detail="Missing API key")

    return {"status": "received", "event_id": "mock-event-123"}
