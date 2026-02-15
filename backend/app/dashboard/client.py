"""Dashboard API client for fetching preferences and emitting events."""

import httpx
import logging
from typing import Optional, Dict, Any

logger = logging.getLogger(__name__)


class DashboardClient:
    """
    HTTP client for User Dashboard API integration.

    This client handles:
    - Fetching user optimization preferences
    - Emitting optimization events/metrics

    Designed to be resilient - never breaks main optimization flow.
    """

    def __init__(self, base_url: str, api_key: str, enabled: bool = True):
        """
        Initialize dashboard client.

        Args:
            base_url: Dashboard API base URL
            api_key: API key for authentication
            enabled: Whether dashboard integration is enabled
        """
        self.base_url = base_url.rstrip("/")
        self.api_key = api_key
        self.enabled = enabled

        if enabled:
            self.http = httpx.AsyncClient(timeout=5.0)
            logger.info(f"Dashboard client initialized: {self.base_url}")
        else:
            self.http = None
            logger.info("Dashboard client disabled")

    async def fetch_user_config(
        self,
        tenant_id: str,
        project_id: str
    ) -> Optional[Dict[str, Any]]:
        """
        Fetch user optimization configuration from dashboard.

        Args:
            tenant_id: User/tenant ID
            project_id: Project ID

        Returns:
            Config dict or None on failure (graceful fallback)
        """
        if not self.enabled or not self.http:
            return None

        try:
            url = f"{self.base_url}/api/config/{tenant_id}/{project_id}"
            headers = {"X-API-Key": self.api_key}

            response = await self.http.get(url, headers=headers)

            if response.status_code == 200:
                data = response.json()
                logger.info(f"Fetched config for {tenant_id}/{project_id}")
                return data.get("config", {})
            else:
                logger.warning(
                    f"Dashboard config fetch failed: {response.status_code}"
                )
                return None

        except Exception as e:
            logger.warning(f"Dashboard config fetch error: {e}")
            return None

    async def emit_event(self, event: Dict[str, Any]):
        """
        Emit optimization event to dashboard (non-blocking, fire-and-forget).

        Args:
            event: Event dict to send
        """
        if not self.enabled or not self.http:
            return

        try:
            url = f"{self.base_url}/api/events"
            headers = {
                "X-API-Key": self.api_key,
                "X-Source": "token-optimizer-middleware",
                "Content-Type": "application/json"
            }

            # Fire-and-forget (don't await response)
            response = await self.http.post(url, json=event, headers=headers)
            logger.info(f"Emitted event: {event.get('event_type')}, status: {response.status_code}")

        except Exception as e:
            # Log but don't fail - events are best-effort
            logger.warning(f"Dashboard event emission failed: {e}")

    async def close(self):
        """Close HTTP client."""
        if self.http:
            await self.http.aclose()
