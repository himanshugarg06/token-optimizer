from app.core.blocks import Block, BlockType
from app.optimizers.heuristics import clean_whitespace


def test_clean_whitespace_trims_trailing_and_collapses_blank_lines():
    blocks = [
        Block.create(BlockType.USER, "hello   \n\n\nworld\t\t\n", 0),
    ]

    out = clean_whitespace(blocks, config={"enable_whitespace_cleanup": True, "max_blank_lines": 1})
    assert len(out) == 1
    assert out[0].content == "hello\n\nworld"
    assert out[0].metadata.get("whitespace_cleaned") is True


def test_clean_whitespace_skips_system_by_default():
    blocks = [
        Block.create(BlockType.SYSTEM, " system   \n\n\n", 0, must_keep=True),
        Block.create(BlockType.USER, " user   \n\n\n", 0),
    ]

    out = clean_whitespace(blocks, config={"enable_whitespace_cleanup": True, "max_blank_lines": 1})
    assert out[0].content == " system   \n\n\n"  # unchanged
    assert out[1].content == "user"  # cleaned


def test_clean_whitespace_is_conservative_around_code_fences():
    txt = "```python\nx = 1\n\n\nprint(x)\n```\n"
    blocks = [Block.create(BlockType.USER, txt, 0)]
    out = clean_whitespace(blocks, config={"enable_whitespace_cleanup": True, "max_blank_lines": 1})
    # No blank line collapsing/strip for code fences; only trailing WS/newline normalization applies.
    assert out[0].content == txt.replace("\r\n", "\n").replace("\r", "\n")

