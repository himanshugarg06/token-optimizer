"""Anthropic provider integration."""

from typing import List, Dict, Any
import logging
from anthropic import AsyncAnthropic
from app.providers.base import BaseProvider

logger = logging.getLogger(__name__)


class AnthropicProvider(BaseProvider):
    """Anthropic API integration."""

    def __init__(self, api_key: str):
        """
        Initialize Anthropic provider.

        Args:
            api_key: Anthropic API key
        """
        self.client = AsyncAnthropic(api_key=api_key)
        logger.info("Anthropic provider initialized")

    async def chat_completion(
        self,
        messages: List[Dict[str, str]],
        model: str,
        **kwargs
    ) -> Dict[str, Any]:
        """
        Send chat completion request to Anthropic.

        Args:
            messages: List of message dicts
            model: Model name
            **kwargs: Additional parameters (temperature, max_tokens, etc.)

        Returns:
            Normalized response dict
        """
        try:
            # Anthropic expects system message separate
            system = None
            other_messages = []

            for msg in messages:
                if msg["role"] == "system":
                    system = msg["content"]
                else:
                    other_messages.append(msg)

            # Prepare kwargs
            anthropic_kwargs = {
                "model": model,
                "messages": other_messages,
                "max_tokens": kwargs.pop("max_tokens", 1000)
            }

            if system:
                anthropic_kwargs["system"] = system

            # Add other kwargs
            anthropic_kwargs.update(kwargs)

            response = await self.client.messages.create(**anthropic_kwargs)

            return self._normalize_response(response)

        except Exception as e:
            logger.error(f"Anthropic API error: {e}")
            raise

    def _normalize_response(self, raw_response) -> Dict[str, Any]:
        """
        Normalize Anthropic response.

        Args:
            raw_response: Anthropic Message object

        Returns:
            Normalized response dict
        """
        return {
            "id": raw_response.id,
            "model": raw_response.model,
            "choices": [
                {
                    "message": {
                        "role": "assistant",
                        "content": block.text
                    },
                    "finish_reason": raw_response.stop_reason
                }
                for block in raw_response.content
            ],
            "usage": {
                "prompt_tokens": raw_response.usage.input_tokens,
                "completion_tokens": raw_response.usage.output_tokens,
                "total_tokens": raw_response.usage.input_tokens + raw_response.usage.output_tokens
            }
        }
