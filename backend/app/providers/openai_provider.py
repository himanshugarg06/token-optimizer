"""OpenAI provider integration."""

from typing import List, Dict, Any
import logging
from openai import AsyncOpenAI
from app.providers.base import BaseProvider

logger = logging.getLogger(__name__)


class OpenAIProvider(BaseProvider):
    """OpenAI API integration."""

    def __init__(self, api_key: str):
        """
        Initialize OpenAI provider.

        Args:
            api_key: OpenAI API key
        """
        self.client = AsyncOpenAI(api_key=api_key)
        logger.info("OpenAI provider initialized")

    async def chat_completion(
        self,
        messages: List[Dict[str, str]],
        model: str,
        **kwargs
    ) -> Dict[str, Any]:
        """
        Send chat completion request to OpenAI.

        Args:
            messages: List of message dicts
            model: Model name
            **kwargs: Additional parameters (temperature, max_tokens, etc.)

        Returns:
            Normalized response dict
        """
        try:
            response = await self.client.chat.completions.create(
                model=model,
                messages=messages,
                **kwargs
            )

            return self._normalize_response(response)

        except Exception as e:
            logger.error(f"OpenAI API error: {e}")
            raise

    def _normalize_response(self, raw_response) -> Dict[str, Any]:
        """
        Normalize OpenAI response.

        Args:
            raw_response: OpenAI ChatCompletion object

        Returns:
            Normalized response dict
        """
        return {
            "id": raw_response.id,
            "model": raw_response.model,
            "choices": [
                {
                    "message": {
                        "role": choice.message.role,
                        "content": choice.message.content
                    },
                    "finish_reason": choice.finish_reason
                }
                for choice in raw_response.choices
            ],
            "usage": {
                "prompt_tokens": raw_response.usage.prompt_tokens,
                "completion_tokens": raw_response.usage.completion_tokens,
                "total_tokens": raw_response.usage.total_tokens
            }
        }
