from app.core.blocks import Block, BlockType
from app.optimizers.validate import apply_fallback


def test_apply_fallback_truncates_when_still_over_budget():
    # Simulate a case where must_keep blocks exceed the budget.
    big = "x " * 5000
    blocks = [
        Block.create(BlockType.SYSTEM, "system", tokens=5, must_keep=True),
        Block.create(BlockType.USER, big, tokens=5000, must_keep=True),
    ]

    cfg = {"max_input_tokens": 200, "safety_margin_tokens": 50, "model": "gpt-4o-mini"}
    out, used = apply_fallback(blocks, cfg)
    assert used is True
    # Should mark truncation on the user block.
    assert any(b.metadata.get("truncated_to_budget") for b in out if b.type == BlockType.USER)
