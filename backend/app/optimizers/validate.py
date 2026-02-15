"""Validation and fallback logic."""

from typing import List, Tuple
from app.core.blocks import Block, BlockType
from app.core.utils import total_tokens
import logging

logger = logging.getLogger(__name__)


def validate(blocks: List[Block], config: dict) -> Tuple[bool, List[str]]:
    """
    Validate optimized prompt.

    Args:
        blocks: Optimized blocks
        config: Configuration dict

    Returns:
        Tuple of (is_valid, error_messages)
    """
    errors = []

    # Check 1: At least one block exists
    if not blocks:
        errors.append("No blocks remaining after optimization")
        return False, errors

    # Check 2: System or user message present
    has_system_or_user = any(
        b.type in [BlockType.SYSTEM, BlockType.USER] for b in blocks
    )
    if not has_system_or_user:
        errors.append("Missing system or user message")

    # Check 3: Token budget satisfied
    max_tokens = int(config.get("max_input_tokens", 8000))
    safety_margin = int(config.get("safety_margin_tokens", 300))
    # Guardrail: for tiny budgets, cap safety margin so validation doesn't fail
    # purely due to a large static reserve.
    safety_margin = min(safety_margin, max_tokens // 4)
    total = total_tokens(blocks)

    if total > max_tokens - safety_margin:
        errors.append(
            f"Over budget: {total} > {max_tokens - safety_margin} "
            f"(max={max_tokens}, safety_margin={safety_margin})"
        )

    # Check 4: All must_keep blocks present
    must_keep_blocks = [b for b in blocks if b.must_keep]
    if not must_keep_blocks:
        errors.append("No must_keep blocks found (validation might be too aggressive)")

    is_valid = len(errors) == 0
    return is_valid, errors


def apply_fallback(blocks: List[Block], config: dict) -> Tuple[List[Block], bool]:
    """
    Apply fallback strategy if validation fails.

    Args:
        blocks: Current blocks
        config: Configuration dict

    Returns:
        Tuple of (fallback_blocks, fallback_used)
    """
    # Fallback 1: Keep only must_keep blocks + latest user message
    logger.warning("Applying fallback: keeping only critical blocks")

    fallback_blocks = []

    # Add all must_keep blocks
    for block in blocks:
        if block.must_keep:
            fallback_blocks.append(block)

    # Ensure we have at least a user message
    if not any(b.type == BlockType.USER for b in fallback_blocks):
        # Find last user block in original
        user_blocks = [b for b in blocks if b.type == BlockType.USER]
        if user_blocks:
            fallback_blocks.append(user_blocks[-1])

    # Validate fallback
    is_valid, errors = validate(fallback_blocks, config)

    if not is_valid:
        logger.error(f"Fallback still invalid: {errors}")
        # Last resort: return original must_keep blocks only
        return [b for b in blocks if b.must_keep], True

    return fallback_blocks, True
