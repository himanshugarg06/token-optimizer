"""Utility functions for token counting and helpers."""

import tiktoken
from typing import Optional
import logging

logger = logging.getLogger(__name__)


def count_tokens(text: str, model: str = "gpt-4") -> int:
    """
    Count tokens in text using tiktoken.

    Args:
        text: Input text
        model: Model name (for tokenizer selection)

    Returns:
        Number of tokens
    """
    try:
        # Try model-specific encoding first
        if model.startswith("gpt-"):
            encoding = tiktoken.encoding_for_model(model)
        else:
            # Fallback to cl100k_base (GPT-4/ChatGPT/GPT-3.5-turbo)
            encoding = tiktoken.get_encoding("cl100k_base")

        tokens = encoding.encode(text)
        return len(tokens)

    except Exception as e:
        logger.warning(f"Token counting failed: {e}, using estimate")
        # Rough estimate: 1 token ~= 4 characters
        return len(text) // 4


def total_tokens(blocks: list) -> int:
    """
    Calculate total tokens across all blocks.

    Args:
        blocks: List of Block objects

    Returns:
        Sum of tokens
    """
    return sum(block.tokens for block in blocks)


def format_compression_ratio(tokens_before: int, tokens_after: int) -> float:
    """
    Calculate compression ratio.

    Args:
        tokens_before: Original token count
        tokens_after: Optimized token count

    Returns:
        Compression ratio (0.0-1.0)
    """
    if tokens_before == 0:
        return 0.0
    return round((tokens_before - tokens_after) / tokens_before, 2)
