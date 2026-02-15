"""Validation and fallback logic."""

from typing import List, Tuple
from app.core.blocks import Block, BlockType
from app.core.utils import total_tokens, head_tail_truncate, count_tokens
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
        # Last resort: if still over budget, deterministically truncate the largest
        # non-system/constraint block (prefer the last user) to fit within budget.
        max_tokens = int(config.get("max_input_tokens", 8000))
        safety_margin = int(config.get("safety_margin_tokens", 300))
        safety_margin = min(safety_margin, max_tokens // 4)
        budget = max(1, max_tokens - safety_margin)
        model = config.get("model", "gpt-4")  # optional; passed by pipeline when available

        candidates = [b for b in fallback_blocks if b.type not in (BlockType.SYSTEM, BlockType.CONSTRAINT)]
        if candidates:
            # Prefer last user block if present, else largest by tokens.
            user_blocks = [b for b in candidates if b.type == BlockType.USER]
            target = user_blocks[-1] if user_blocks else max(candidates, key=lambda b: b.tokens)

            other_tokens = sum(b.tokens for b in fallback_blocks if b.id != target.id)
            remaining = max(1, budget - other_tokens)
            truncated = head_tail_truncate(target.content, remaining, model=model, head_frac=0.4)
            target.content = truncated
            target.tokens = count_tokens(truncated, model=model)
            target.metadata["truncated_to_budget"] = True

            is_valid2, errors2 = validate(fallback_blocks, config)
            if is_valid2:
                return fallback_blocks, True
            logger.error(f"Truncation fallback still invalid: {errors2}")

        # Final last resort: return must_keep blocks only (may still be over budget).
        return [b for b in blocks if b.must_keep], True

    return fallback_blocks, True
