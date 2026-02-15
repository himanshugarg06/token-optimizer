"""Prometheus metrics."""

from prometheus_client import Counter, Histogram, Gauge, generate_latest, CONTENT_TYPE_LATEST

# Request counters
requests_total = Counter(
    'token_optimizer_requests_total',
    'Total optimization requests',
    ['endpoint', 'status']
)

# Token metrics
tokens_before_total = Counter(
    'token_optimizer_tokens_before_total',
    'Total tokens before optimization'
)

tokens_after_total = Counter(
    'token_optimizer_tokens_after_total',
    'Total tokens after optimization'
)

tokens_saved_total = Counter(
    'token_optimizer_tokens_saved_total',
    'Total tokens saved'
)

# Latency histogram
latency_seconds = Histogram(
    'token_optimizer_latency_seconds',
    'Request latency in seconds',
    ['endpoint']
)

# Cache metrics
cache_hits_total = Counter(
    'token_optimizer_cache_hits_total',
    'Total cache hits'
)

cache_misses_total = Counter(
    'token_optimizer_cache_misses_total',
    'Total cache misses'
)

# Route counters
route_total = Counter(
    'token_optimizer_route_total',
    'Optimization route taken',
    ['route']
)

# Dashboard event metrics
dashboard_events_total = Counter(
    'token_optimizer_dashboard_events_total',
    'Dashboard events emitted',
    ['status']
)

# Active gauges
active_requests = Gauge(
    'token_optimizer_active_requests',
    'Number of requests currently being processed'
)


def record_optimization(stats: dict, endpoint: str = "optimize"):
    """
    Record optimization metrics.

    Args:
        stats: Optimization statistics dict
        endpoint: Endpoint name
    """
    # Increment request counter
    requests_total.labels(endpoint=endpoint, status="success").inc()

    # Record token metrics (ensure they are integers)
    try:
        tokens_before = int(stats.get("tokens_before", 0)) if stats.get("tokens_before") is not None else 0
        tokens_after = int(stats.get("tokens_after", 0)) if stats.get("tokens_after") is not None else 0
        tokens_saved = int(stats.get("tokens_saved", 0)) if stats.get("tokens_saved") is not None else 0
    except (ValueError, TypeError):
        tokens_before = 0
        tokens_after = 0
        tokens_saved = 0

    # Only increment with non-negative values (Prometheus requirement)
    if tokens_before > 0:
        tokens_before_total.inc(tokens_before)
    if tokens_after > 0:
        tokens_after_total.inc(tokens_after)
    if tokens_saved > 0:
        tokens_saved_total.inc(tokens_saved)

    # Record latency
    latency_ms = stats.get("latency_ms", 0)
    latency_seconds.labels(endpoint=endpoint).observe(latency_ms / 1000.0)

    # Record cache hit/miss
    if stats.get("cache_hit", False):
        cache_hits_total.inc()
    else:
        cache_misses_total.inc()

    # Record route
    route = stats.get("route", "unknown")
    route_total.labels(route=route).inc()


def record_dashboard_event(success: bool):
    """
    Record dashboard event emission.

    Args:
        success: Whether event was emitted successfully
    """
    status = "sent" if success else "failed"
    dashboard_events_total.labels(status=status).inc()


def get_metrics() -> bytes:
    """
    Get Prometheus metrics in text format.

    Returns:
        Metrics as bytes
    """
    return generate_latest()
