"""Utility functions for token counting and helpers."""

import tiktoken
from typing import Optional, List
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


def truncate_text_to_tokens(text: str, max_tokens: int, model: str = "gpt-4") -> str:
    """
    Truncate text to at most max_tokens using the model tokenizer.
    Best-effort: if tokenization fails, fall back to character truncation.
    """
    if max_tokens <= 0:
        return ""
    try:
        if model.startswith("gpt-"):
            enc = tiktoken.encoding_for_model(model)
        else:
            enc = tiktoken.get_encoding("cl100k_base")
        toks = enc.encode(text)
        if len(toks) <= max_tokens:
            return text
        return enc.decode(toks[:max_tokens])
    except Exception as e:
        logger.warning(f"Token truncation failed: {e}, using char truncation")
        # Approx 1 token ~= 4 chars
        return text[: max_tokens * 4]


def head_tail_truncate(text: str, max_tokens: int, model: str = "gpt-4", head_frac: float = 0.5) -> str:
    """
    Keep a prefix and suffix of the text within max_tokens, inserting a truncation marker.
    Useful when the end of the message contains critical instructions.
    """
    if max_tokens <= 0:
        return ""
    marker = "\n... [TRUNCATED] ...\n"
    # Reserve some tokens for the marker itself (rough estimate is OK).
    marker_tokens = max(8, count_tokens(marker, model))
    budget = max(1, max_tokens - marker_tokens)

    head_budget = max(1, int(budget * head_frac))
    tail_budget = max(1, budget - head_budget)

    head = truncate_text_to_tokens(text, head_budget, model)
    # For tail, truncate from the end.
    try:
        if model.startswith("gpt-"):
            enc = tiktoken.encoding_for_model(model)
        else:
            enc = tiktoken.get_encoding("cl100k_base")
        toks = enc.encode(text)
        tail = enc.decode(toks[-tail_budget:]) if len(toks) > tail_budget else text
    except Exception:
        # Char fallback.
        tail = text[-tail_budget * 4 :]

    return head + marker + tail
