"""Main optimization pipeline orchestration."""

import time
import uuid
import logging
from typing import List, Dict, Any, Tuple, Optional

from app.core.blocks import Block
from app.core.canonicalize import canonicalize, blocks_to_messages
from app.core.utils import total_tokens, format_compression_ratio
from app.optimizers.heuristics import apply_heuristics
from app.optimizers.cache import CacheManager
from app.optimizers.validate import validate, apply_fallback
from app.settings import Settings

logger = logging.getLogger(__name__)


class OptimizationPipeline:
    """
    Class-based optimization pipeline with lazy-loaded services.

    Supports semantic retrieval, compression, and budget allocation
    with graceful degradation if services unavailable.
    """

    def __init__(self, settings: Settings, cache_manager: Optional[CacheManager] = None):
        self.settings = settings
        self.cache_manager = cache_manager

        # Lazy-loaded services (initialized on first access)
        self._embedding_service = None
        self._vector_store = None
        self._utility_scorer = None
        self._budget_allocator = None
        self._compressor = None

        # Track initialization attempts
        self._embedding_service_attempted = False
        self._vector_store_attempted = False
        self._utility_scorer_attempted = False
        self._budget_allocator_attempted = False
        self._compressor_attempted = False

    @property
    def embedding_service(self):
        """Lazy load embedding service."""
        if not self._embedding_service_attempted:
            self._embedding_service_attempted = True
            if self.settings.semantic.enabled:
                try:
                    from app.optimizers.semantic import EmbeddingService
                    self._embedding_service = EmbeddingService(self.settings.semantic)
                    if self._embedding_service.available:
                        logger.info("Embedding service loaded successfully")
                    else:
                        logger.warning("Embedding service unavailable")
                except Exception as e:
                    logger.error(f"Failed to load embedding service: {e}")
        return self._embedding_service

    @property
    def vector_store(self):
        """Lazy load vector store."""
        if not self._vector_store_attempted:
            self._vector_store_attempted = True
            if self.settings.semantic.enabled and self.settings.semantic.postgres_url:
                try:
                    from app.optimizers.semantic import VectorStore
                    self._vector_store = VectorStore(self.settings.semantic.postgres_url)
                    if self._vector_store.available:
                        logger.info("Vector store connected successfully")
                    else:
                        logger.warning("Vector store unavailable")
                except Exception as e:
                    logger.error(f"Failed to load vector store: {e}")
        return self._vector_store

    @property
    def utility_scorer(self):
        """Lazy load utility scorer."""
        if not self._utility_scorer_attempted:
            self._utility_scorer_attempted = True
            if self.settings.semantic.enabled:
                try:
                    from app.optimizers.semantic import UtilityScorer
                    self._utility_scorer = UtilityScorer()
                    logger.info("Utility scorer initialized")
                except Exception as e:
                    logger.error(f"Failed to load utility scorer: {e}")
        return self._utility_scorer

    @property
    def budget_allocator(self):
        """Lazy load budget allocator."""
        if not self._budget_allocator_attempted:
            self._budget_allocator_attempted = True
            try:
                from app.optimizers.budget import BudgetAllocator
                self._budget_allocator = BudgetAllocator(self.settings.budget)
                logger.info("Budget allocator initialized")
            except Exception as e:
                logger.error(f"Failed to load budget allocator: {e}")
        return self._budget_allocator

    @property
    def compressor(self):
        """Lazy load compressor."""
        if not self._compressor_attempted:
            self._compressor_attempted = True
            if self.settings.compression.enabled:
                try:
                    from app.optimizers.compress import LLMLinguaCompressor
                    self._compressor = LLMLinguaCompressor(self.settings.compression)
                    if self._compressor.available:
                        logger.info("Compressor loaded successfully")
                    else:
                        logger.info("Compressor using fallback mode")
                except Exception as e:
                    logger.error(f"Failed to load compressor: {e}")
        return self._compressor

    async def optimize(
        self,
        messages: List[Dict[str, str]],
        config: dict,
        tools: Optional[Dict[str, Any]] = None,
        rag_context: Optional[List[Dict[str, Any]]] = None,
        tool_outputs: Optional[List[Dict[str, Any]]] = None,
        model: str = "gpt-4"
    ) -> Tuple[List[Dict[str, str]], Dict[str, Any]]:
        """
        Main optimization pipeline.

        Pipeline stages:
        0. Canonicalize → Blocks
        1. Apply heuristics (always)
        2. Check cache
        3. Semantic retrieval (if enabled and over budget)
        4. Compression (if enabled and still over budget)
        5. Validation + fallback

        Args:
            messages: Input messages
            config: Configuration dict
            tools: Optional tool schemas
            rag_context: Optional RAG documents
            tool_outputs: Optional tool outputs
            model: Model name

        Returns:
            Tuple of (optimized_messages, stats_dict)
        """
        start_time = time.time()
        trace_id = str(uuid.uuid4())
        stage_timings = {}
        route_stages = ["heuristic"]

        # Generate cache key
        cache_key = None
        if self.cache_manager and self.cache_manager.available:
            cache_key = self.cache_manager.generate_cache_key(
                {"messages": messages, "model": model},
                config
            )

            # Check cache
            t0 = time.time()
            cached_result = self.cache_manager.get_cached(cache_key)
            stage_timings["cache_check"] = int((time.time() - t0) * 1000)

            if cached_result:
                logger.info(f"Cache hit for key: {cache_key}")
                cached_result["stats"]["cache_hit"] = True
                cached_result["stats"]["latency_ms"] = int((time.time() - start_time) * 1000)
                cached_result["debug"]["trace_id"] = trace_id
                return cached_result["optimized_messages"], cached_result

        # Stage 0: Canonicalize
        t0 = time.time()
        blocks = canonicalize(messages, tools, rag_context, tool_outputs, model)
        tokens_before = total_tokens(blocks)
        stage_timings["canonicalize"] = int((time.time() - t0) * 1000)

        logger.info(f"Canonicalized {len(blocks)} blocks, {tokens_before} tokens")

        # Stage 1: Apply heuristics
        t0 = time.time()
        blocks = apply_heuristics(blocks, config)
        stage_timings["heuristics"] = int((time.time() - t0) * 1000)

        tokens_after_heuristics = total_tokens(blocks)
        logger.info(f"After heuristics: {len(blocks)} blocks, {tokens_after_heuristics} tokens")

        # Stage 2: Semantic retrieval (if enabled and over budget)
        max_tokens = config.get("max_input_tokens", self.settings.max_input_tokens)
        safety_margin = config.get("safety_margin_tokens", self.settings.safety_margin_tokens)

        if self.settings.semantic.enabled and tokens_after_heuristics > max_tokens:
            t0 = time.time()
            blocks = await self._apply_semantic(blocks, max_tokens, safety_margin, model)
            stage_timings["semantic"] = int((time.time() - t0) * 1000)
            tokens_after_semantic = total_tokens(blocks)
            logger.info(f"After semantic: {len(blocks)} blocks, {tokens_after_semantic} tokens")
            route_stages.append("semantic")
        else:
            tokens_after_semantic = tokens_after_heuristics

        # Stage 3: Compression (if enabled and still over budget)
        if self.settings.compression.enabled and tokens_after_semantic > max_tokens:
            t0 = time.time()
            blocks = self._apply_compression(blocks)
            stage_timings["compression"] = int((time.time() - t0) * 1000)
            tokens_after_compression = total_tokens(blocks)
            logger.info(f"After compression: {len(blocks)} blocks, {tokens_after_compression} tokens")
            route_stages.append("compression")
        else:
            tokens_after_compression = tokens_after_semantic

        # Stage 4: Validation
        t0 = time.time()
        is_valid, errors = validate(blocks, config)
        fallback_used = False

        if not is_valid:
            logger.warning(f"Validation failed: {errors}")
            blocks, fallback_used = apply_fallback(blocks, config)
            logger.info(f"Fallback applied: {len(blocks)} blocks")

        stage_timings["validate"] = int((time.time() - t0) * 1000)

        tokens_after = total_tokens(blocks)

        # Convert back to messages
        optimized_messages = blocks_to_messages(blocks)

        # Build stats
        latency_ms = int((time.time() - start_time) * 1000)
        route = "+".join(route_stages)

        stats = {
            "tokens_before": tokens_before,
            "tokens_after": tokens_after,
            "tokens_saved": tokens_before - tokens_after,
            "compression_ratio": format_compression_ratio(tokens_before, tokens_after),
            "cache_hit": False,
            "route": route,
            "fallback_used": fallback_used,
            "latency_ms": latency_ms
        }

        # Build block info
        selected_blocks = [
            {
                "id": b.id,
                "type": b.type.value,
                "tokens": b.tokens,
                "reason": "must_keep" if b.must_keep else "selected"
            }
            for b in blocks
        ]

        # All blocks not in final result are "dropped"
        final_block_ids = {b.id for b in blocks}
        original_blocks = canonicalize(messages, tools, rag_context, tool_outputs, model)
        dropped_blocks = [
            {
                "id": b.id,
                "type": b.type.value,
                "tokens": b.tokens,
                "reason": "filtered"
            }
            for b in original_blocks if b.id not in final_block_ids
        ]

        result = {
            "optimized_messages": optimized_messages,
            "selected_blocks": selected_blocks,
            "dropped_blocks": dropped_blocks,
            "stats": stats,
            "debug": {
                "trace_id": trace_id,
                "config_resolved": config,
                "dashboard": {},
                "stage_timings_ms": stage_timings
            }
        }

        # Cache result
        if self.cache_manager and self.cache_manager.available and cache_key:
            t0 = time.time()
            self.cache_manager.set_cached(cache_key, result)
            stage_timings["cache_set"] = int((time.time() - t0) * 1000)

        return optimized_messages, result

    async def _apply_semantic(
        self,
        blocks: List[Block],
        max_tokens: int,
        safety_margin: int,
        model: str
    ) -> List[Block]:
        """
        Stage 3: Apply semantic retrieval.

        Uses embeddings and utility scoring to intelligently select
        the most relevant blocks within budget.
        """
        try:
            # Check if services available
            if not self.embedding_service or not self.embedding_service.available:
                logger.warning("Embedding service unavailable, skipping semantic retrieval")
                return blocks

            if not self.utility_scorer:
                logger.warning("Utility scorer unavailable, skipping semantic retrieval")
                return blocks

            if not self.budget_allocator:
                logger.warning("Budget allocator unavailable, skipping semantic retrieval")
                return blocks

            # Separate must_keep from optional
            must_keep = [b for b in blocks if b.must_keep]
            optional = [b for b in blocks if not b.must_keep]

            if not optional:
                logger.debug("No optional blocks to optimize")
                return blocks

            # Create query embedding from last 3 user messages
            user_blocks = [b for b in blocks if b.type.value == "user"]
            if user_blocks:
                query_texts = [b.content for b in user_blocks[-3:]]
                query_text = " ".join(query_texts)
                query_embedding = self.embedding_service.embed_single(query_text)
            else:
                # No user messages, use first block as query
                query_embedding = self.embedding_service.embed_single(blocks[0].content)

            # Embed optional blocks
            optional_contents = [b.content for b in optional]
            optional_embeddings = self.embedding_service.embed(optional_contents)

            # Compute utility scores
            for block, emb in zip(optional, optional_embeddings):
                utility = self.utility_scorer.compute_utility(block, query_embedding, emb)
                block.metadata["utility"] = utility

            # Apply MMR for diversity
            from app.optimizers.semantic import mmr_selection
            candidates = [
                (block, block.metadata["utility"], emb)
                for block, emb in zip(optional, optional_embeddings)
            ]

            diverse_blocks = mmr_selection(
                candidates,
                query_embedding,
                lambda_param=self.settings.semantic.mmr_lambda,
                top_k=self.settings.semantic.vector_topk
            )

            # Budget selection
            selected, dropped = self.budget_allocator.select_blocks(
                must_keep + diverse_blocks,
                max_tokens,
                safety_margin
            )

            logger.info(
                f"Semantic retrieval: {len(optional)} optional → "
                f"{len(diverse_blocks)} diverse → {len(selected) - len(must_keep)} selected"
            )

            return selected

        except Exception as e:
            logger.error(f"Semantic retrieval failed: {e}", exc_info=True)
            return blocks  # Graceful fallback

    def _apply_compression(self, blocks: List[Block]) -> List[Block]:
        """
        Stage 4: Apply LLMLingua-2 compression.

        Compresses block content while preserving faithfulness.
        """
        try:
            if not self.compressor:
                logger.warning("Compressor unavailable, skipping compression")
                return blocks

            compressed_blocks = []
            total_saved = 0

            for block in blocks:
                compressed, stats = self.compressor.compress_block(block)
                compressed_blocks.append(compressed)

                if "tokens_saved" in stats:
                    total_saved += stats["tokens_saved"]

            logger.info(f"Compression saved {total_saved} tokens")
            return compressed_blocks

        except Exception as e:
            logger.error(f"Compression failed: {e}", exc_info=True)
            return blocks  # Graceful fallback


# Legacy function for backward compatibility
async def optimize(
    messages: List[Dict[str, str]],
    config: dict,
    cache_manager: Optional[CacheManager],
    tools: Optional[Dict[str, Any]] = None,
    rag_context: Optional[List[Dict[str, Any]]] = None,
    tool_outputs: Optional[List[Dict[str, Any]]] = None,
    model: str = "gpt-4"
) -> Tuple[List[Dict[str, str]], Dict[str, Any]]:
    """
    Legacy function-based interface (backward compatible).

    Creates a pipeline instance and runs optimization.
    """
    from app.settings import settings

    pipeline = OptimizationPipeline(settings, cache_manager)
    return await pipeline.optimize(messages, config, tools, rag_context, tool_outputs, model)
