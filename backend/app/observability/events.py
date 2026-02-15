"""Event emission for analytics."""

import logging
from datetime import datetime
from typing import Dict, Any, Optional
from app.dashboard.client import DashboardClient

logger = logging.getLogger(__name__)


async def emit_optimization_event(
    dashboard_client: Optional[DashboardClient],
    tenant_id: Optional[str],
    project_id: Optional[str],
    request_id: Optional[str],
    trace_id: str,
    stats: Dict[str, Any],
    provider: Optional[str] = None,
    model: str = "gpt-4",
    endpoint: str = "/v1/optimize"
):
    """
    Emit optimization event to dashboard.

    Args:
        dashboard_client: Dashboard client instance
        tenant_id: User/tenant ID
        project_id: Project ID
        request_id: Request ID
        trace_id: Trace ID for this optimization
        stats: Optimization statistics
        provider: LLM provider (if applicable)
        model: Model name
        endpoint: API endpoint used
    """
    if not dashboard_client or not dashboard_client.enabled:
        return

    try:
        # Get API key prefix from stats if available
        api_key_prefix = stats.get("api_key_prefix")

        event = {
            "event_type": "optimization",
            "timestamp": datetime.utcnow().isoformat() + "Z",
            "tenant_id": tenant_id or "unknown",
            "project_id": project_id or "unknown",
            "api_key_prefix": api_key_prefix,
            "model": model,
            "endpoint": endpoint,
            "stats": {
                "tokens_before": stats.get("tokens_before", 0),
                "tokens_after": stats.get("tokens_after", 0),
                "tokens_saved": stats.get("tokens_saved", 0),
                "compression_ratio": stats.get("compression_ratio", 0.0),
                "latency_ms": stats.get("latency_ms", 0),
            },
            "success": True
        }

        # Emit event (async, non-blocking)
        await dashboard_client.emit_event(event)
        logger.info(f"Emitted optimization event: tenant={tenant_id}, tokens_saved={stats.get('tokens_saved', 0)}")

    except Exception as e:
        logger.warning(f"Event emission failed: {e}")
