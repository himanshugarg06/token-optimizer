"""FastAPI application - Token Optimizer Middleware."""

import logging
import importlib.util
from datetime import datetime
from fastapi import FastAPI, Depends, HTTPException
from fastapi.responses import PlainTextResponse, Response

from app.settings import settings
from app.auth import verify_api_key
from app.models import (
    OptimizeRequest,
    OptimizeResponse,
    HealthResponse,
    ChatRequest,
    ChatResponse,
    ChatChoice,
    ProviderUsage,
    OptimizationStats,
    BlockInfo,
    DebugInfo,
    Message
)
from app.core.pipeline import optimize
from app.optimizers.cache import CacheManager
from app.dashboard.client import DashboardClient
from app.dashboard.config_merger import merge_config, map_dashboard_config_to_optimizer
from app.dashboard.mock_server import mock_router
from app.observability.events import emit_optimization_event
from app.observability.metrics import record_optimization, get_metrics, CONTENT_TYPE_LATEST
from app.providers.openai_provider import OpenAIProvider
from app.providers.anthropic_provider import AnthropicProvider

# Configure logging
logging.basicConfig(
    level=getattr(logging, settings.log_level),
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)

logger = logging.getLogger(__name__)

# Avoid doing heavyweight model initialization (SentenceTransformers / LLMLingua)
# in health checks; those can take tens of seconds and will block a single-worker
# event loop if done inline.
def _module_available(module_name: str) -> bool:
    return importlib.util.find_spec(module_name) is not None

# Initialize FastAPI app
app = FastAPI(
    title="Token Optimizer Middleware",
    description="Intelligent LLM prompt compression middleware",
    version="0.1.0"
)

# Initialize cache manager
cache_manager = CacheManager(settings.redis_url)

# Initialize dashboard client
dashboard_client = None
if settings.dashboard_enabled and settings.dashboard_base_url:
    dashboard_client = DashboardClient(
        base_url=settings.dashboard_base_url,
        api_key=settings.get_dashboard_api_key(),
        enabled=True
    )

# Initialize LLM providers
openai_provider = None
anthropic_provider = None

if settings.openai_api_key:
    openai_provider = OpenAIProvider(settings.openai_api_key)

if settings.anthropic_api_key:
    anthropic_provider = AnthropicProvider(settings.anthropic_api_key)

# Mount mock dashboard router if enabled
if settings.mock_dashboard:
    app.include_router(mock_router)


@app.get("/")
async def root():
    """Root endpoint."""
    return {
        "service": "Token Optimizer Middleware",
        "version": "0.1.0",
        "endpoints": {
            "optimize": "/v1/optimize",
            "chat": "/v1/chat",
            "health": "/v1/health",
            "metrics": "/v1/metrics"
        }
    }


@app.post("/v1/optimize", response_model=OptimizeResponse)
async def optimize_endpoint(
    request: OptimizeRequest,
    api_key: str = Depends(verify_api_key)
):
    """
    Optimize a prompt without calling LLM.

    This endpoint takes messages and applies optimization techniques
    (heuristics, caching, etc.) to reduce token count while preserving meaning.
    """
    logger.info(f"Optimize request: {len(request.messages)} messages, model={request.model}")

    try:
        # Fetch dashboard config if available
        dashboard_config = None
        if dashboard_client and request.tenant_id and request.project_id:
            dashboard_config_raw = await dashboard_client.fetch_user_config(
                request.tenant_id,
                request.project_id
            )
            if dashboard_config_raw:
                dashboard_config = map_dashboard_config_to_optimizer(dashboard_config_raw)

        # Build base config from settings
        base_config = {
            "max_input_tokens": request.max_tokens or settings.max_input_tokens,
            "keep_last_n_turns": settings.keep_last_n_turns,
            "safety_margin_tokens": settings.safety_margin_tokens,
            "min_tokens_saved": settings.min_tokens_saved,
            "min_savings_ratio": settings.min_savings_ratio,
        }

        # Merge configs: base <- dashboard <- request
        config = merge_config(base_config, dashboard_config, request.user_prefs_overrides)

        # Convert messages to dict format
        messages_dict = [{"role": m.role, "content": m.content} for m in request.messages]

        # Run optimization
        optimized_messages, result = await optimize(
            messages=messages_dict,
            config=config,
            cache_manager=cache_manager,
            tools=request.tools,
            rag_context=request.rag_context,
            tool_outputs=request.tool_outputs,
            model=request.model
        )

        # Add API key prefix to stats for downstream logging/ingestion
        result["stats"]["api_key_prefix"] = api_key[:12]

        # Record metrics
        record_optimization(result["stats"], endpoint="optimize")

        # Emit event to dashboard
        if dashboard_client:
            await emit_optimization_event(
                dashboard_client=dashboard_client,
                tenant_id=request.tenant_id,
                project_id=request.project_id,
                request_id=None,
                trace_id=result["debug"]["trace_id"],
                stats=result["stats"],
                model=request.model,
                endpoint="/v1/optimize"
            )

        # Build response
        response = OptimizeResponse(
            optimized_messages=[
                Message(role=m["role"], content=m["content"])
                for m in optimized_messages
            ],
            selected_blocks=[BlockInfo(**b) for b in result["selected_blocks"]],
            dropped_blocks=[BlockInfo(**b) for b in result["dropped_blocks"]],
            stats=OptimizationStats(**result["stats"]),
            debug=DebugInfo(**result["debug"])
        )

        logger.info(
            f"Optimization complete: "
            f"{result['stats']['tokens_before']} → {result['stats']['tokens_after']} tokens "
            f"({result['stats']['compression_ratio']:.0%} reduction)"
        )

        return response

    except Exception as e:
        logger.error(f"Optimization failed: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Optimization failed: {str(e)}")


@app.post("/v1/chat", response_model=ChatResponse)
async def chat_endpoint(
    request: ChatRequest,
    api_key: str = Depends(verify_api_key)
):
    """
    Optimize prompt and forward to LLM provider.

    This endpoint optimizes the prompt first, then forwards to the specified
    provider (OpenAI or Anthropic).
    """
    logger.info(
        f"Chat request: {len(request.messages)} messages, "
        f"provider={request.provider}, model={request.model}"
    )

    try:
        # Validate provider
        if request.provider == "openai" and not openai_provider:
            raise HTTPException(
                status_code=400,
                detail="OpenAI provider not configured. Set OPENAI_API_KEY."
            )
        if request.provider == "anthropic" and not anthropic_provider:
            raise HTTPException(
                status_code=400,
                detail="Anthropic provider not configured. Set ANTHROPIC_API_KEY."
            )

        # First, optimize the prompt (same logic as /v1/optimize)
        # Fetch dashboard config
        dashboard_config = None
        if dashboard_client and request.tenant_id and request.project_id:
            dashboard_config_raw = await dashboard_client.fetch_user_config(
                request.tenant_id,
                request.project_id
            )
            if dashboard_config_raw:
                dashboard_config = map_dashboard_config_to_optimizer(dashboard_config_raw)

        # Build config
        base_config = {
            "max_input_tokens": request.max_tokens or settings.max_input_tokens,
            "keep_last_n_turns": settings.keep_last_n_turns,
            "safety_margin_tokens": settings.safety_margin_tokens,
            "min_tokens_saved": settings.min_tokens_saved,
            "min_savings_ratio": settings.min_savings_ratio,
        }
        config = merge_config(base_config, dashboard_config, request.user_prefs_overrides)

        # Convert messages
        messages_dict = [{"role": m.role, "content": m.content} for m in request.messages]

        # Run optimization
        optimized_messages, opt_result = await optimize(
            messages=messages_dict,
            config=config,
            cache_manager=cache_manager,
            tools=request.tools,
            rag_context=request.rag_context,
            tool_outputs=request.tool_outputs,
            model=request.model
        )

        logger.info(
            f"Optimized: {opt_result['stats']['tokens_before']} → "
            f"{opt_result['stats']['tokens_after']} tokens"
        )

        # Forward to provider
        provider = openai_provider if request.provider == "openai" else anthropic_provider

        provider_kwargs = {}
        if request.temperature is not None:
            provider_kwargs["temperature"] = request.temperature
        if request.max_completion_tokens:
            provider_kwargs["max_tokens"] = request.max_completion_tokens

        provider_response = await provider.chat_completion(
            messages=optimized_messages,
            model=request.model,
            **provider_kwargs
        )

        # Add API key prefix to stats for downstream logging/ingestion
        opt_result["stats"]["api_key_prefix"] = api_key[:12]

        # Record metrics
        record_optimization(opt_result["stats"], endpoint="chat")

        # Emit event
        if dashboard_client:
            await emit_optimization_event(
                dashboard_client=dashboard_client,
                tenant_id=request.tenant_id,
                project_id=request.project_id,
                request_id=None,
                trace_id=opt_result["debug"]["trace_id"],
                stats=opt_result["stats"],
                provider=request.provider,
                model=request.model,
                endpoint="/v1/chat"
            )

        # Build response
        response = ChatResponse(
            id=provider_response["id"],
            model=provider_response["model"],
            choices=[
                ChatChoice(
                    message=Message(**choice["message"]),
                    finish_reason=choice.get("finish_reason")
                )
                for choice in provider_response["choices"]
            ],
            usage=ProviderUsage(**provider_response["usage"]),
            optimizer={
                "stats": opt_result["stats"],
                "trace_id": opt_result["debug"]["trace_id"],
                "features_used": opt_result.get("debug", {}).get("features_used", {}),
            }
        )

        logger.info(f"Chat complete: {provider_response['usage']['total_tokens']} total tokens")

        return response

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Chat failed: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Chat failed: {str(e)}")


@app.get("/v1/health", response_model=HealthResponse)
async def health():
    """
    Health check endpoint.

    Returns service health status and dependency connectivity.
    """
    # Check Redis
    redis_status = "connected" if cache_manager.available else "disconnected"

    # Check Postgres
    postgres_status = None
    if settings.semantic.enabled and settings.semantic.postgres_url:
        try:
            from app.optimizers.semantic import VectorStore
            test_store = VectorStore(settings.semantic.postgres_url)
            postgres_status = "connected" if test_store.health_check() else "disconnected"
        except Exception as e:
            logger.error(f"Postgres health check failed: {e}")
            postgres_status = "error"

    # Check Dashboard
    dashboard_status = None
    if dashboard_client and dashboard_client.enabled:
        dashboard_status = "configured"

    # "Available" here means "configured and dependencies are importable".
    # Do not instantiate models (they download/load large weights and can hang).
    semantic_available = bool(
        settings.semantic.enabled
        and settings.semantic.postgres_url
        and _module_available("sentence_transformers")
    )

    compression_available = bool(
        settings.compression.enabled
        and (_module_available("llmlingua") or _module_available("sumy"))
    )

    return HealthResponse(
        status="healthy" if cache_manager.available else "degraded",
        redis=redis_status,
        postgres=postgres_status,
        dashboard=dashboard_status,
        timestamp=datetime.utcnow().isoformat() + "Z",
        semantic_available=semantic_available,
        compression_available=compression_available
    )


@app.get("/v1/metrics")
async def metrics():
    """
    Prometheus metrics endpoint.

    Returns metrics in Prometheus text format.
    """
    metrics_data = get_metrics()
    return Response(content=metrics_data, media_type=CONTENT_TYPE_LATEST)


@app.on_event("startup")
async def startup_event():
    """Application startup handler."""
    logger.info("Token Optimizer Middleware starting...")

    # Run migrations if enabled
    if settings.run_migrations_on_startup and settings.semantic.enabled and settings.semantic.postgres_url:
        try:
            from app.storage.migration_runner import run_migrations_from_settings
            logger.info("Running database migrations...")
            success = run_migrations_from_settings(settings)
            if success:
                logger.info("Database migrations completed successfully")
            else:
                logger.warning("Database migrations failed, semantic retrieval may not work")
        except Exception as e:
            logger.error(f"Migration runner failed: {e}")

    logger.info(f"Redis: {'connected' if cache_manager.available else 'unavailable'}")
    logger.info(f"Dashboard integration: {'enabled' if settings.dashboard_enabled else 'disabled'}")
    logger.info(f"Mock dashboard: {'enabled' if settings.mock_dashboard else 'disabled'}")
    logger.info(f"OpenAI provider: {'configured' if openai_provider else 'not configured'}")
    logger.info(f"Anthropic provider: {'configured' if anthropic_provider else 'not configured'}")
    logger.info(f"Semantic retrieval: {'enabled' if settings.semantic.enabled else 'disabled'}")
    logger.info(f"Compression: {'enabled' if settings.compression.enabled else 'disabled'}")


@app.on_event("shutdown")
async def shutdown_event():
    """Application shutdown handler."""
    logger.info("Token Optimizer Middleware shutting down...")
    if dashboard_client:
        await dashboard_client.close()


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
