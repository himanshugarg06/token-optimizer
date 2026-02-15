"""Deterministic heuristics for prompt optimization."""

from typing import List, Optional
import re
import hashlib
from collections import defaultdict
from app.core.blocks import Block, BlockType


def remove_junk(blocks: List[Block]) -> List[Block]:
    """
    Remove empty/whitespace blocks.

    Args:
        blocks: Input blocks

    Returns:
        Filtered blocks
    """
    cleaned = []

    for block in blocks:
        # Skip if must_keep
        if block.must_keep:
            cleaned.append(block)
            continue

        # Check if empty or whitespace-only
        content = block.content.strip()
        if not content:
            continue

        # Check common junk patterns
        junk_patterns = [
            r"^(Sure|Of course|I can help|Let me help).*$",
            r"^(Thank you|Thanks).*$",
            r"^\s*$"
        ]

        is_junk = False
        for pattern in junk_patterns:
            if re.match(pattern, content, re.IGNORECASE):
                is_junk = True
                break

        if not is_junk:
            cleaned.append(block)

    return cleaned


def deduplicate(blocks: List[Block]) -> List[Block]:
    """
    Remove duplicate blocks, keeping most recent.

    Args:
        blocks: Input blocks

    Returns:
        Deduplicated blocks
    """
    # Group by fingerprint
    fingerprint_map = defaultdict(list)

    for block in blocks:
        if block.must_keep:
            # Always keep must_keep blocks
            fingerprint_map[block.id].append(block)
        else:
            # Hash content for deduplication
            fingerprint = hashlib.sha256(
                block.get_fingerprint().encode()
            ).hexdigest()[:16]
            fingerprint_map[fingerprint].append(block)

    # Keep most recent from each group
    deduped = []
    for group in fingerprint_map.values():
        if len(group) == 1:
            deduped.append(group[0])
        else:
            # Sort by timestamp, keep latest
            sorted_group = sorted(
                group,
                key=lambda b: b.timestamp or 0,
                reverse=True
            )
            deduped.append(sorted_group[0])

    # Sort by original order (using metadata index if available)
    deduped.sort(key=lambda b: b.metadata.get("index", 0))

    return deduped


def keep_last_n_turns(blocks: List[Block], n: int = 4) -> List[Block]:
    """
    Mark last N conversation turns as must_keep.

    Args:
        blocks: Input blocks
        n: Number of turns to keep

    Returns:
        Updated blocks
    """
    # Find user+assistant pairs (conversation turns)
    turns = []
    current_turn = []

    for block in blocks:
        if block.type in [BlockType.USER, BlockType.ASSISTANT]:
            current_turn.append(block)

            # End of turn when we see a user message after assistant
            if block.type == BlockType.USER and len(current_turn) > 1:
                turns.append(current_turn[:-1])
                current_turn = [block]

    # Add last turn
    if current_turn:
        turns.append(current_turn)

    # Mark last N turns as must_keep
    last_n_turns = turns[-n:] if len(turns) > n else turns

    must_keep_ids = set()
    for turn in last_n_turns:
        for block in turn:
            must_keep_ids.add(block.id)

    # Update blocks
    for block in blocks:
        if block.id in must_keep_ids:
            block.must_keep = True
            block.priority = max(block.priority, 0.9)

    return blocks


def extract_constraints(blocks: List[Block]) -> Optional[Block]:
    """
    Extract critical directives into dedicated constraint block.

    Args:
        blocks: Input blocks

    Returns:
        Constraint block if found, else None
    """
    constraint_keywords = [
        "MUST", "MUST NOT", "ALWAYS", "NEVER",
        "REQUIRED", "FORBIDDEN", "ONLY",
        "FORMAT", "JSON", "OUTPUT", "DEADLINE"
    ]

    # Collect sentences with constraints
    constraint_sentences = []

    for block in blocks:
        if block.type not in [BlockType.SYSTEM, BlockType.USER]:
            continue

        content = block.content
        sentences = re.split(r'[.!?]\s+', content)

        for sentence in sentences:
            # Check if sentence contains constraint keywords
            if any(kw in sentence.upper() for kw in constraint_keywords):
                constraint_sentences.append(sentence.strip())

    if not constraint_sentences:
        return None

    # Create constraint block
    constraint_content = "\n".join(constraint_sentences)

    # Use utility import to avoid circular dependency
    from app.core.utils import count_tokens

    constraint_block = Block.create(
        block_type=BlockType.CONSTRAINT,
        content=constraint_content,
        tokens=count_tokens(constraint_content),
        must_keep=True,
        priority=1.0,
        source="extracted_constraints"
    )

    return constraint_block


def apply_heuristics(blocks: List[Block], config: dict) -> List[Block]:
    """
    Apply all heuristic transformations.

    Args:
        blocks: Input blocks
        config: Configuration dict

    Returns:
        Optimized blocks
    """
    # Stage 1: Remove junk
    blocks = remove_junk(blocks)

    # Stage 2: Deduplicate
    blocks = deduplicate(blocks)

    # Stage 3: Keep last N turns
    keep_n = config.get("keep_last_n_turns", 4)
    blocks = keep_last_n_turns(blocks, n=keep_n)

    # Stage 4: Extract constraints
    constraint_block = extract_constraints(blocks)
    if constraint_block:
        # Add constraint block at the beginning
        blocks = [constraint_block] + blocks

    return blocks
