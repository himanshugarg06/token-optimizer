"""Tests for heuristics module."""

import pytest
from datetime import datetime
from app.core.blocks import Block, BlockType
from app.optimizers.heuristics import (
    remove_junk,
    deduplicate,
    keep_last_n_turns,
    extract_constraints,
    apply_heuristics
)


def test_remove_junk():
    """Test junk removal."""
    blocks = [
        Block.create(BlockType.ASSISTANT, "   ", 0),
        Block.create(BlockType.ASSISTANT, "Sure, I can help.", 5),
        Block.create(BlockType.ASSISTANT, "Real content here.", 5),
    ]

    result = remove_junk(blocks)

    assert len(result) == 1
    assert result[0].content == "Real content here."


def test_deduplicate():
    """Test deduplication."""
    blocks = [
        Block.create(BlockType.ASSISTANT, "Hello world", 2, timestamp=datetime(2024, 1, 1)),
        Block.create(BlockType.ASSISTANT, "Hello world", 2, timestamp=datetime(2024, 1, 2)),
        Block.create(BlockType.ASSISTANT, "Different message", 2),
    ]

    result = deduplicate(blocks)

    # Should keep only one "Hello world" (the most recent)
    assert len(result) <= 2


def test_keep_last_n_turns():
    """Test keeping last N conversation turns."""
    blocks = [
        Block.create(BlockType.USER, "Question 1", 2),
        Block.create(BlockType.ASSISTANT, "Answer 1", 2),
        Block.create(BlockType.USER, "Question 2", 2),
        Block.create(BlockType.ASSISTANT, "Answer 2", 2),
        Block.create(BlockType.USER, "Question 3", 2),
    ]

    result = keep_last_n_turns(blocks, n=1)

    # Last turn should be marked as must_keep
    must_keep_count = sum(1 for b in result if b.must_keep)
    assert must_keep_count >= 1


def test_extract_constraints():
    """Test constraint extraction."""
    blocks = [
        Block.create(BlockType.SYSTEM, "You MUST respond in JSON format.", 10),
        Block.create(BlockType.USER, "NEVER include personal information.", 10),
        Block.create(BlockType.ASSISTANT, "Just a normal message.", 5),
    ]

    constraint_block = extract_constraints(blocks)

    assert constraint_block is not None
    assert "MUST" in constraint_block.content
    assert "NEVER" in constraint_block.content


def test_apply_heuristics():
    """Test full heuristics pipeline."""
    config = {
        "keep_last_n_turns": 2
    }

    blocks = [
        Block.create(BlockType.SYSTEM, "System message", 3),
        Block.create(BlockType.USER, "Hello", 2),
        Block.create(BlockType.ASSISTANT, "Hi", 1),
        Block.create(BlockType.USER, "How are you?", 3),
    ]

    result = apply_heuristics(blocks, config)

    # Should have blocks after optimization
    assert len(result) > 0

    # System message should be preserved
    assert any(b.type == BlockType.SYSTEM for b in result)
