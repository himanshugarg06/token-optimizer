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
    model: str = "gpt-4"
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
    """
    if not dashboard_client or not dashboard_client.enabled:
        return

    try:
        event = {
            "event_type": "token_optimizer.request",
            "timestamp": datetime.utcnow().isoformat() + "Z",
            "tenant_id": tenant_id or "unknown",
            "project_id": project_id or "unknown",
            "request_id": request_id or trace_id,
            "trace_id": trace_id,
            "target": {
                "provider": provider or "none",
                "model": model
            },
            "stats": {
                "tokens_before": stats.get("tokens_before", 0),
                "tokens_after": stats.get("tokens_after", 0),
                "tokens_saved": stats.get("tokens_saved", 0),
                "compression_ratio": stats.get("compression_ratio", 0.0),
                "latency_ms": stats.get("latency_ms", 0),
                "cache_hit": stats.get("cache_hit", False),
                "route": stats.get("route", "unknown"),
                "fallback_used": stats.get("fallback_used", False)
            }
        }

        # Emit event (async, non-blocking)
        await dashboard_client.emit_event(event)

    except Exception as e:
        logger.warning(f"Event emission failed: {e}")
