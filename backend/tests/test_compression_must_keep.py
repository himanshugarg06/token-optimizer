import types

from app.core.blocks import Block, BlockType
from app.optimizers.compress import LLMLinguaCompressor
from app.settings import CompressionConfig


def test_compress_can_reduce_must_keep_when_allowed(monkeypatch):
    # Avoid importing/loading any real models during tests.
    def _noop_load(self):
        self.available = False
        self.compressor = None

        # Provide a deterministic fallback that always returns a short string.
        self.fallback = types.SimpleNamespace(compress=lambda content, ratio: "short")

    monkeypatch.setattr(LLMLinguaCompressor, "_load_model", _noop_load)

    cfg = CompressionConfig(enabled=True, allow_must_keep=True, fallback_to_extractive=True)
    compressor = LLMLinguaCompressor(cfg)

    # No entities/numbers/caps => faithfulness_score returns 1.0.
    original = "lorem ipsum " * 400
    block = Block.create(BlockType.USER, original, tokens=200, must_keep=True)

    compressed, stats = compressor.compress_block(block, ratio=0.1)

    assert "tokens_saved" in stats
    assert compressed.compressed is True
    assert compressed.tokens < block.tokens


def test_compress_never_compresses_constraint_or_system(monkeypatch):
    def _noop_load(self):
        self.available = False
        self.compressor = None
        self.fallback = types.SimpleNamespace(compress=lambda content, ratio: "short")

    monkeypatch.setattr(LLMLinguaCompressor, "_load_model", _noop_load)

    cfg = CompressionConfig(enabled=True, allow_must_keep=True, fallback_to_extractive=True)
    compressor = LLMLinguaCompressor(cfg)

    for bt in (BlockType.SYSTEM, BlockType.CONSTRAINT):
        block = Block.create(bt, "lorem ipsum " * 400, tokens=200, must_keep=True)
        compressed, stats = compressor.compress_block(block, ratio=0.1)
        assert compressed.content == block.content
        assert stats.get("skipped") is True

