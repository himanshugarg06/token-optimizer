"""Base provider interface."""

from abc import ABC, abstractmethod
from typing import List, Dict, Any


class BaseProvider(ABC):
    """Base class for LLM provider integrations."""

    @abstractmethod
    async def chat_completion(
        self,
        messages: List[Dict[str, str]],
        model: str,
        **kwargs
    ) -> Dict[str, Any]:
        """
        Send chat completion request to provider.

        Args:
            messages: List of message dicts
            model: Model name
            **kwargs: Additional provider-specific parameters

        Returns:
            Normalized response dict
        """
        pass

    def _normalize_response(self, raw_response: Any) -> Dict[str, Any]:
        """
        Normalize provider response to common format.

        Args:
            raw_response: Raw response from provider

        Returns:
            Normalized response dict
        """
        raise NotImplementedError("Subclass must implement _normalize_response")
