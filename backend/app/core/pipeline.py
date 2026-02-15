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

logger = logging.getLogger(__name__)


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
    Main optimization pipeline.

    Pipeline stages:
    0. Canonicalize → Blocks
    1. Apply heuristics (always)
    2. Check cache
    3. Validation + fallback

    Args:
        messages: Input messages
        config: Configuration dict
        cache_manager: Cache manager instance
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

    # Generate cache key
    cache_key = None
    if cache_manager and cache_manager.available:
        cache_key = cache_manager.generate_cache_key(
            {"messages": messages, "model": model},
            config
        )

        # Check cache
        t0 = time.time()
        cached_result = cache_manager.get_cached(cache_key)
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

    # Stage 2: Validation
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

    stats = {
        "tokens_before": tokens_before,
        "tokens_after": tokens_after,
        "tokens_saved": tokens_before - tokens_after,
        "compression_ratio": format_compression_ratio(tokens_before, tokens_after),
        "cache_hit": False,
        "route": "heuristic+cache",
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
    if cache_manager and cache_manager.available and cache_key:
        t0 = time.time()
        cache_manager.set_cached(cache_key, result)
        stage_timings["cache_set"] = int((time.time() - t0) * 1000)

    return optimized_messages, result
