"""LLM compression with LLMLingua-2 and extractive fallback."""

import logging
import re
from typing import Optional, List, Tuple, Dict

from app.core.blocks import Block, BlockType
from app.settings import CompressionConfig

logger = logging.getLogger(__name__)


class LLMLinguaCompressor:
    """
    LLMLingua-2 compression with faithfulness validation.
    Falls back to extractive summarization if model unavailable.
    """

    def __init__(self, config: CompressionConfig):
        self.config = config
        self.compressor = None
        self.available = False
        self.fallback = None
        self._load_model()

    def _load_model(self):
        """Lazy load LLMLingua-2 model"""
        try:
            logger.info(f"Loading compression model: {self.config.model_name}")

            from llmlingua import PromptCompressor

            self.compressor = PromptCompressor(
                model_name=self.config.model_name,
                device_map=self.config.device
            )

            # Warmup
            _ = self.compressor.compress_prompt(
                "This is a test.",
                rate=0.5
            )

            self.available = True
            logger.info("Compression model loaded successfully")

        except ImportError:
            logger.warning("LLMLingua not available, using extractive fallback")
            if self.config.fallback_to_extractive:
                self.fallback = ExtractiveSummarizer()
            self.available = False

        except Exception as e:
            logger.error(f"Failed to load compression model: {e}")
            if self.config.fallback_to_extractive:
                logger.info("Falling back to extractive summarization")
                self.fallback = ExtractiveSummarizer()
            self.available = False

    def compress_block(
        self,
        block: Block,
        ratio: float = None
    ) -> Tuple[Block, Dict]:
        """
        Compress block content with faithfulness check.

        Args:
            block: Block to compress
            ratio: Compression ratio (default: config value)

        Returns:
            (compressed_block, stats)
        """
        if ratio is None:
            ratio = self.config.compression_ratio

        # Never compress system/constraint blocks (high risk of changing behavior).
        if block.type in (BlockType.SYSTEM, BlockType.CONSTRAINT):
            return block, {"skipped": True, "reason": "protected_type"}

        # Don't compress must_keep unless explicitly allowed.
        if block.must_keep and not self.config.allow_must_keep:
            return block, {"skipped": True, "reason": "must_keep"}

        # Don't double-compress.
        if block.compressed:
            return block, {"skipped": True, "reason": "already_compressed"}

        # Don't compress short blocks (not worth it)
        if block.tokens < 100:
            return block, {"skipped": True, "reason": "too_short"}

        original_content = block.content
        original_tokens = block.tokens

        try:
            # Compress
            if self.available:
                compressed_content = self._compress_llmlingua(
                    original_content,
                    ratio
                )
            elif self.fallback:
                compressed_content = self._compress_extractive(
                    original_content,
                    ratio
                )
            else:
                return block, {"skipped": True, "reason": "no_compressor"}

            from app.core.utils import count_tokens
            compressed_tokens = count_tokens(compressed_content)

            # Faithfulness check
            faithfulness = self._faithfulness_score(
                original_content,
                compressed_content
            )

            # Accept only if faithful enough
            if faithfulness < self.config.faithfulness_threshold:
                logger.debug(
                    f"Compression rejected: faithfulness {faithfulness:.2f} "
                    f"< threshold {self.config.faithfulness_threshold}"
                )
                return block, {
                    "rejected": True,
                    "faithfulness": faithfulness
                }

            # Create compressed block
            compressed_block = Block.create(
                block_type=block.type,
                content=compressed_content,
                tokens=compressed_tokens,
                must_keep=block.must_keep,
                priority=block.priority,
                source=block.metadata.get("source", "unknown"),
                metadata={
                    **block.metadata,
                    "original_tokens": original_tokens,
                    "compression_ratio": compressed_tokens / original_tokens,
                    "faithfulness": faithfulness
                }
            )
            compressed_block.compressed = True

            stats = {
                "original_tokens": original_tokens,
                "compressed_tokens": compressed_tokens,
                "tokens_saved": original_tokens - compressed_tokens,
                "compression_ratio": compressed_tokens / original_tokens,
                "faithfulness": faithfulness
            }

            logger.debug(
                f"Compressed block {block.id}: "
                f"{original_tokens} → {compressed_tokens} tokens "
                f"(ratio: {stats['compression_ratio']:.2f}, "
                f"faithfulness: {faithfulness:.2f})"
            )

            return compressed_block, stats

        except Exception as e:
            logger.error(f"Compression failed: {e}")
            return block, {"error": str(e)}

    def _compress_llmlingua(self, content: str, ratio: float) -> str:
        """Apply LLMLingua-2 compression"""
        result = self.compressor.compress_prompt(
            content,
            rate=ratio,
            force_tokens=self.config.force_tokens,
            drop_consecutive=True
        )
        return result["compressed_prompt"]

    def _compress_extractive(self, content: str, ratio: float) -> str:
        """Fallback extractive summarization"""
        return self.fallback.compress(content, ratio)

    def _faithfulness_score(
        self,
        original: str,
        compressed: str
    ) -> float:
        """
        Measure information preservation using entity overlap.

        Compares:
        1. Named entities (proper nouns)
        2. Numbers and measurements
        3. Key constraint words

        Returns: 0.0-1.0 score
        """
        # Extract entities from both
        original_entities = self._extract_entities(original)
        compressed_entities = self._extract_entities(compressed)

        if not original_entities:
            return 1.0  # Nothing to preserve

        # Jaccard similarity
        intersection = original_entities & compressed_entities
        union = original_entities | compressed_entities

        jaccard = len(intersection) / len(union) if union else 1.0

        # Boost score if all critical entities preserved
        critical_preserved = all(
            entity in compressed_entities
            for entity in original_entities
            if self._is_critical(entity)
        )

        if critical_preserved:
            jaccard = min(jaccard + 0.1, 1.0)

        return jaccard

    def _extract_entities(self, text: str) -> set:
        """Extract entities: proper nouns, numbers, IDs"""
        entities = set()

        # Proper nouns (capitalized words)
        entities.update(re.findall(r'\b[A-Z][a-z]+\b', text))

        # Numbers
        entities.update(re.findall(r'\b\d+\.?\d*\b', text))

        # UUIDs
        entities.update(re.findall(
            r'\b[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}\b',
            text.lower()
        ))

        # Constraint keywords
        for keyword in ["MUST", "NEVER", "ALWAYS", "REQUIRED", "FORMAT"]:
            if keyword in text.upper():
                entities.add(keyword)

        return entities

    def _is_critical(self, entity: str) -> bool:
        """Check if entity is critical to preserve"""
        critical_patterns = [
            r'^\d+$',  # Pure numbers
            r'^[A-Z]+$',  # All caps (acronyms)
            r'MUST|NEVER|ALWAYS|REQUIRED'  # Constraints
        ]

        return any(re.match(pattern, entity) for pattern in critical_patterns)

    def compress_blocks_batch(
        self,
        blocks: List[Block],
        ratio: float = None
    ) -> Tuple[List[Block], Dict]:
        """Batch compress multiple blocks"""
        compressed_blocks = []
        total_stats = {
            "compressed_count": 0,
            "skipped_count": 0,
            "rejected_count": 0,
            "error_count": 0,
            "total_tokens_before": 0,
            "total_tokens_after": 0
        }

        for block in blocks:
            compressed, stats = self.compress_block(block, ratio)
            compressed_blocks.append(compressed)

            if "skipped" in stats:
                total_stats["skipped_count"] += 1
            elif "rejected" in stats:
                total_stats["rejected_count"] += 1
            elif "error" in stats:
                total_stats["error_count"] += 1
            else:
                total_stats["compressed_count"] += 1
                total_stats["total_tokens_before"] += stats["original_tokens"]
                total_stats["total_tokens_after"] += stats["compressed_tokens"]

        if total_stats["compressed_count"] > 0:
            total_stats["overall_compression_ratio"] = (
                total_stats["total_tokens_after"] /
                total_stats["total_tokens_before"]
            )

        return compressed_blocks, total_stats


class ExtractiveSummarizer:
    """Fallback extractive summarization using TextRank"""

    def __init__(self):
        try:
            from sumy.parsers.plaintext import PlaintextParser
            from sumy.nlp.tokenizers import Tokenizer
            from sumy.summarizers.text_rank import TextRankSummarizer

            self.parser_class = PlaintextParser
            self.tokenizer_class = Tokenizer
            self.summarizer = TextRankSummarizer()
            self.available = True
        except ImportError:
            logger.warning("sumy not available, extractive summarization disabled")
            self.available = False

    def compress(self, content: str, ratio: float) -> str:
        """Extract key sentences to achieve compression ratio"""
        if not self.available:
            return content

        try:
            # TextRank over very large blobs is slow and can dominate end-to-end latency.
            # For big inputs, do a cheap head/tail cut that preserves tail instructions.
            from app.core.utils import count_tokens, head_tail_truncate
            orig_tokens = count_tokens(content, model="gpt-4")
            if orig_tokens > 2000:
                target_tokens = max(64, int(orig_tokens * max(0.05, min(float(ratio or 0.5), 1.0))))
                # Cap to keep this fallback fast and predictable.
                target_tokens = min(target_tokens, 1200)
                return head_tail_truncate(content, target_tokens, model="gpt-4", head_frac=0.35)

            from io import StringIO

            # Parse content
            parser = self.parser_class.from_string(
                content,
                self.tokenizer_class("english")
            )

            # Calculate sentence count
            sentences = list(parser.document.sentences)
            target_count = max(1, int(len(sentences) * ratio))

            # Summarize
            summary_sentences = self.summarizer(parser.document, target_count)

            # Reconstruct text
            return " ".join(str(s) for s in summary_sentences)

        except Exception as e:
            # Common failure in minimal containers: missing NLTK punkt.
            msg = str(e)
            logger.error(f"Extractive summarization failed: {e}")

            # Best-effort: if punkt is missing, try downloading once at runtime.
            if "Resource" in msg and "punkt" in msg:
                try:
                    import nltk
                    nltk.download("punkt", quiet=True)
                    parser = self.parser_class.from_string(content, self.tokenizer_class("english"))
                    sentences = list(parser.document.sentences)
                    target_count = max(1, int(len(sentences) * ratio))
                    summary_sentences = self.summarizer(parser.document, target_count)
                    return " ".join(str(s) for s in summary_sentences)
                except Exception:
                    pass

            # Deterministic fallback that preserves tail instructions:
            # keep a head+tail slice by token budget (approx) so the end-of-message
            # constraints like "IMPORTANT:" survive.
            try:
                from app.core.utils import head_tail_truncate, count_tokens
                orig_tokens = max(1, count_tokens(content, model="gpt-4"))
                target_tokens = max(32, int(orig_tokens * max(0.05, min(ratio, 1.0))))
                return head_tail_truncate(content, target_tokens, model="gpt-4", head_frac=0.35)
            except Exception:
                return content
