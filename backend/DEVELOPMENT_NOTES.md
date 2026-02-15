# Token Optimizer Middleware - Development Notes

**Last Updated**: February 15, 2026

Technical notes for developers continuing work on this project.

---

## 🏗️ Architecture Deep Dive

### Request Flow

```
HTTP Request (POST /v1/optimize)
    ↓
[FastAPI] app/main.py:optimize_endpoint()
    ↓
[Auth] app/auth.py:verify_api_key()
    ↓
[Dashboard] app/dashboard/client.py:fetch_user_config()
    ↓
[Config Merge] app/dashboard/config_merger.py:merge_config()
    ↓
[Pipeline] app/core/pipeline.py:optimize()
    │
    ├─> [Canonicalize] app/core/canonicalize.py:canonicalize()
    │       ↓
    │   Convert messages → Block IR
    │
    ├─> [Cache Check] app/optimizers/cache.py:get_cached()
    │       ↓
    │   If cache hit → return cached result
    │
    ├─> [Heuristics] app/optimizers/heuristics.py:apply_heuristics()
    │       ↓
    │   remove_junk() → deduplicate() → keep_last_n_turns() → extract_constraints()
    │
    ├─> [Validation] app/optimizers/validate.py:validate()
    │       ↓
    │   Check must_keep blocks present, token budget satisfied
    │
    └─> [Cache Set] app/optimizers/cache.py:set_cached()
            ↓
    [Metrics] app/observability/metrics.py:record_optimization()
    [Events] app/observability/events.py:emit_optimization_event()
            ↓
HTTP Response (OptimizeResponse)
```

---

## 🔑 Key Design Decisions

### 1. Block IR (Internal Representation)

**Why?**
- Unified format for all input types (messages, tools, RAG docs, tool outputs)
- Simplifies optimization logic (operates on blocks, not raw messages)
- Enables metadata tracking (must_keep, priority, timestamps)

**Structure** (`app/core/blocks.py`):
```python
@dataclass
class Block:
    id: str                    # UUID for tracking
    type: BlockType            # system, user, assistant, tool, doc, constraint
    content: str               # Actual text
    tokens: int                # Token count (pre-computed)
    must_keep: bool = False    # Never drop this block
    priority: float = 0.5      # 0.0-1.0 for ranking
    timestamp: Optional[datetime] = None
    metadata: Dict[str, Any] = field(default_factory=dict)
```

**Block Types**:
- `system`: System prompts (always must_keep=True)
- `user`: User messages (latest must_keep=True)
- `assistant`: Assistant responses (compressible)
- `tool`: Tool schemas (minimizable)
- `doc`: RAG documents (retrievable/compressible)
- `constraint`: Extracted constraints (must_keep=True)

### 2. Optimization Pipeline Stages

**Stage 0: Canonicalization**
- Convert all inputs to Block IR
- Assign types, tokens, must_keep flags
- Set timestamps for recency tracking

**Stage 1: Heuristics (Always Runs)**
- Deterministic, fast, predictable
- remove_junk() → deduplicate() → keep_last_n_turns() → extract_constraints()
- No external dependencies
- Achieves 45-54% reduction

**Stage 2: Cache Check**
- Redis with 10-minute TTL
- Key: SHA256(messages + model + config)
- Returns entire result if hit (19.8x speedup)

**Stage 3: Validation**
- Ensure system message present
- Ensure user message present
- Ensure constraints preserved
- Ensure token budget satisfied
- Progressive fallback if validation fails

### 3. Config Merging Priority

```
Final Config = Base Config ← Dashboard Config ← Request Overrides
```

**Example**:
```python
# Base (settings.py)
base = {"max_input_tokens": 8000, "keep_last_n_turns": 4}

# Dashboard (from API)
dashboard = {"keep_last_n_turns": 6}  # User preference

# Request (from API call)
request = {"max_input_tokens": 4000}  # This specific request

# Merged
final = {"max_input_tokens": 4000, "keep_last_n_turns": 6}
```

**Implementation**: `app/dashboard/config_merger.py:merge_config()`

### 4. Dashboard Integration Resilience

**Design Principle**: Dashboard must NEVER break optimization

**Implementation**:
```python
# app/dashboard/client.py
async def fetch_user_config(self, tenant_id: str, project_id: str):
    try:
        response = await self.http.get(f"{self.base_url}/v1/config/{tenant_id}/{project_id}")
        return response.json() if response.status_code == 200 else None
    except Exception as e:
        logger.warning(f"Dashboard fetch failed: {e}")
        return None  # Silent fallback
```

**Result**: If dashboard is down, optimization continues with base config.

### 5. Prometheus Metrics Type Safety

**Problem**: Counters can only increment by non-negative amounts
**Solution**: Explicit type conversion and validation

```python
# app/observability/metrics.py
try:
    tokens_before = int(stats.get("tokens_before", 0)) if stats.get("tokens_before") is not None else 0
except (ValueError, TypeError):
    tokens_before = 0

if tokens_before > 0:  # Only increment if positive
    tokens_before_total.inc(tokens_before)
```

---

## 🧩 Code Organization

### Module Responsibilities

**app/main.py**
- FastAPI application setup
- Route handlers (`/v1/optimize`, `/v1/chat`, `/v1/health`, `/v1/metrics`)
- Request/response validation
- Metrics recording, event emission

**app/settings.py**
- Environment variable loading (pydantic-settings)
- Configuration validation
- Defaults for all settings

**app/auth.py**
- X-API-Key authentication
- FastAPI dependency injection

**app/models.py**
- Pydantic models for requests/responses
- Type safety, validation

**app/core/pipeline.py**
- Main orchestration logic
- Calls canonicalize → heuristics → cache → validate
- Returns optimized messages + stats

**app/core/canonicalize.py**
- Converts messages/tools/docs → Block IR
- Assigns must_keep flags (system=True, latest user=True)
- Sets timestamps

**app/core/utils.py**
- Token counting (tiktoken)
- Utility functions

**app/optimizers/heuristics.py**
- Deterministic optimization functions
- Pure functions (no side effects)

**app/optimizers/cache.py**
- Redis cache manager
- Key generation (SHA256)
- get_cached(), set_cached()

**app/optimizers/validate.py**
- Validation logic
- Fallback strategies

**app/providers/**
- LLM provider integrations
- Base interface, OpenAI, Anthropic

**app/dashboard/**
- Dashboard client (HTTP)
- Config merging
- Mock server for testing

**app/observability/**
- Prometheus metrics
- Event emission (async)

---

## 🧪 Testing Strategy

### Unit Tests (`tests/test_heuristics.py`)
- Test each heuristic function in isolation
- Use fixtures for common test data
- Assert expected behavior

**Example**:
```python
def test_remove_junk():
    blocks = [
        Block.create(BlockType.ASSISTANT, "   ", 0),
        Block.create(BlockType.ASSISTANT, "Real content", 5),
    ]
    result = remove_junk(blocks)
    assert len(result) == 1
    assert result[0].content == "Real content"
```

### Performance Tests (`tests/performance_test.sh`)
- End-to-end API tests
- Measure latency, token reduction, cache performance
- 8 test scenarios covering different use cases

**Test Scenarios**:
1. Small prompt baseline
2. Cache hit performance
3. Medium prompt with optimization
4. Large prompt (200+ tokens)
5. Constraint extraction
6. Concurrent load (10 requests)
7. Sequential throughput (20 requests)
8. Memory efficiency (1,400+ tokens)

### Future Test Ideas
- Integration tests with mocked Redis
- Integration tests with mocked dashboard
- Semantic retrieval tests (when implemented)
- Provider integration tests (OpenAI/Anthropic)
- Stress tests (1000+ requests)
- Edge case tests (empty messages, very long messages, unicode)

---

## 🔧 Development Workflow

### Local Development Setup

```bash
# 1. Clone repository
git clone git@github.com:himanshugarg06/token-optimizer.git
cd token-optimizer/backend

# 2. Copy environment template
cp .env.example .env

# 3. Edit .env with your settings
vim .env

# 4. Start services
docker-compose up --build

# 5. In another terminal, run tests
bash tests/performance_test.sh

# 6. Make changes to code
vim app/core/heuristics.py

# 7. Restart service to apply changes
docker restart token_optimizer-token-optimizer-1

# 8. Test changes
curl -X POST http://localhost:8000/v1/optimize ...

# 9. Commit changes
git add .
git commit -m "Improve heuristics"
git push
```

### Hot Reload (Optional)

For faster development, mount code as volume:

Edit `docker-compose.yml`:
```yaml
token-optimizer:
  volumes:
    - ./app:/app/app:ro  # Mount app directory
  command: uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
```

Now code changes apply immediately without restart!

### Adding New Dependencies

```bash
# 1. Add to requirements.txt
echo "new-package==1.0.0" >> requirements.txt

# 2. Rebuild container
docker-compose up --build

# 3. Commit
git add requirements.txt
git commit -m "Add new-package dependency"
```

---

## 🚀 Future Feature Implementation

### Adding Semantic Retrieval

**Files to create**:
- `app/optimizers/semantic.py` - Embedding service, vector store
- `app/optimizers/budget.py` - Budget-aware selection
- `migrations/001_init.sql` - Database schema

**Steps**:
1. Enable pgvector in PostgreSQL
2. Create embeddings table
3. Implement embedding service (sentence-transformers)
4. Implement MMR selection
5. Integrate into pipeline after heuristics
6. Set `ENABLE_SEMANTIC_RETRIEVAL=true`

**Estimated effort**: 2-3 days

### Adding TOON Compression

**Files to create**:
- `app/optimizers/compress.py` - TOON compression logic
- `app/optimizers/faithfulness.py` - Faithfulness scoring

**Steps**:
1. Implement TOON schema extraction
2. Implement TOON compression/decompression
3. Add faithfulness checks (entity overlap, ROUGE-L)
4. Integrate into pipeline after semantic retrieval
5. Set `ENABLE_TOON_COMPRESSION=true`

**Estimated effort**: 2-3 days

### Adding More Heuristics

**Easy additions** to `app/optimizers/heuristics.py`:

1. **minimize_tool_schemas()**
   - Strip descriptions, examples from tool schemas
   - Keep only: name, parameters, required
   - ~30% reduction on tool-heavy prompts

2. **compress_json_toon()**
   - Apply TOON to JSON in messages
   - Schema#0[1,Alice|2,Bob] format
   - ~60% reduction on JSON-heavy prompts

3. **trim_logs()**
   - Extract ERROR lines ± 30 lines context
   - Keep last 80 lines
   - ~80% reduction on log-heavy prompts

**Estimated effort per heuristic**: 2-4 hours

---

## 🐛 Debugging Tips

### Common Gotchas

1. **Prometheus counters**: Must always increment by non-negative amounts
   - Always validate: `if value > 0: counter.inc(value)`

2. **Redis JSON serialization**: Values become strings
   - Always convert: `int(stats.get("tokens_before", 0))`

3. **macOS date command**: Doesn't support `%N` (nanoseconds)
   - Use Python instead: `python3 -c "import time; print(int(time.time() * 1000))"`

4. **Docker port conflicts**: Port 8000 might be in use
   - Check with: `lsof -i :8000`
   - Kill process: `kill -9 $(lsof -t -i:8000)`

5. **Cache stale data**: Redis cache lasts 10 minutes
   - Clear with: `docker exec token_optimizer-redis-1 redis-cli FLUSHALL`

### Adding Debug Logging

```python
# app/core/pipeline.py
import logging
logger = logging.getLogger(__name__)

def optimize(...):
    logger.debug(f"Input: {len(messages)} messages")
    logger.debug(f"Config: {config}")

    # ... optimization logic ...

    logger.debug(f"Output: {len(optimized_messages)} messages")
    logger.debug(f"Stats: {stats}")
```

Set `LOG_LEVEL=DEBUG` in `.env` to see these logs.

---

## 📊 Metrics & Monitoring

### Prometheus Metrics Exposed

**Counters**:
- `token_optimizer_requests_total{endpoint, status}` - Total requests
- `token_optimizer_tokens_before_total` - Total tokens before optimization
- `token_optimizer_tokens_after_total` - Total tokens after optimization
- `token_optimizer_tokens_saved_total` - Total tokens saved
- `token_optimizer_cache_hits_total` - Cache hits
- `token_optimizer_cache_misses_total` - Cache misses
- `token_optimizer_route_total{route}` - Route taken (heuristic, semantic, etc.)
- `token_optimizer_dashboard_events_total{status}` - Dashboard events

**Histograms**:
- `token_optimizer_latency_seconds{endpoint}` - Request latency distribution

**Gauges**:
- `token_optimizer_active_requests` - Current requests being processed

### Adding New Metrics

```python
# app/observability/metrics.py
from prometheus_client import Counter

# Define metric
custom_metric = Counter(
    'token_optimizer_custom_metric',
    'Description of metric',
    ['label1', 'label2']
)

# Record metric
def record_custom(label1_value, label2_value):
    custom_metric.labels(label1=label1_value, label2=label2_value).inc()
```

Use in code:
```python
from app.observability.metrics import record_custom
record_custom("value1", "value2")
```

### Grafana Dashboard (Future)

Example queries:
```promql
# Token savings over time
rate(token_optimizer_tokens_saved_total[5m])

# Cache hit rate
rate(token_optimizer_cache_hits_total[5m]) /
  (rate(token_optimizer_cache_hits_total[5m]) + rate(token_optimizer_cache_misses_total[5m]))

# P95 latency
histogram_quantile(0.95, rate(token_optimizer_latency_seconds_bucket[5m]))

# Requests per second
rate(token_optimizer_requests_total[1m])
```

---

## 🔐 Security Considerations

### Current Security

1. **API Key Authentication**: X-API-Key header required
2. **Input Validation**: Pydantic models validate all inputs
3. **No SQL Injection**: Using parameterized queries (when DB used)
4. **No XSS**: No HTML rendering
5. **Docker Isolation**: Services run in isolated containers

### Future Security Enhancements

1. **Rate Limiting** per API key
   ```python
   from slowapi import Limiter
   limiter = Limiter(key_func=get_api_key)

   @app.post("/v1/optimize")
   @limiter.limit("100/minute")
   async def optimize_endpoint(...):
   ```

2. **JWT Authentication** instead of API keys
3. **HTTPS/TLS** for production
4. **API Key Rotation** mechanism
5. **Audit Logging** for all requests
6. **Content Filtering** for sensitive data

---

## 📈 Performance Optimization Tips

### Current Performance

- **Latency**: 2-10ms average
- **Throughput**: 22 req/sec
- **Cache speedup**: 19.8x

### Further Optimizations

1. **Async Everything**
   - Already using: FastAPI async, httpx async
   - Consider: asyncio.gather() for parallel operations

2. **Connection Pooling**
   - Redis: Already pooled by redis-py
   - PostgreSQL: Use asyncpg with pool
   - HTTP: httpx already pools connections

3. **Caching Strategy**
   - Consider longer TTL for stable prompts
   - Implement prefix caching for system messages
   - Use bloom filters for cache existence checks

4. **Token Counting Optimization**
   - Cache tokenizer instances
   - Batch token counting
   - Consider approximate counting for large texts

5. **Horizontal Scaling**
   ```yaml
   # docker-compose.yml
   token-optimizer:
     deploy:
       replicas: 3
   ```

   Then add nginx load balancer.

---

## 📝 Code Style & Conventions

### Python Style
- **PEP 8** compliant
- **Type hints** everywhere
- **Docstrings** for all public functions
- **Constants** in UPPER_CASE
- **Private functions** prefixed with `_`

### Example Function
```python
def optimize_prompt(
    messages: List[Dict[str, str]],
    config: Dict[str, Any],
    cache_manager: Optional[CacheManager] = None
) -> Tuple[List[Dict[str, str]], Dict[str, Any]]:
    """
    Optimize a prompt using heuristics and caching.

    Args:
        messages: List of message dicts with role and content
        config: Configuration dict with optimization parameters
        cache_manager: Optional cache manager for result caching

    Returns:
        Tuple of (optimized_messages, stats_dict)

    Raises:
        ValueError: If messages list is empty
    """
    if not messages:
        raise ValueError("Messages list cannot be empty")

    # Implementation...
    return optimized_messages, stats
```

### Commit Messages
```
<type>: <subject>

<body>

<footer>
```

**Types**: feat, fix, docs, style, refactor, test, chore

**Example**:
```
feat: add TOON compression for JSON-heavy prompts

Implements Token-Oriented Object Notation compression for JSON
content in messages. Achieves ~60% token reduction on JSON-heavy
prompts while preserving data structure.

Closes #42
```

---

## 🎓 Learning Resources

### FastAPI
- https://fastapi.tiangolo.com/
- Async/await patterns
- Dependency injection

### Pydantic
- https://docs.pydantic.dev/
- Data validation
- Settings management

### Redis
- https://redis.io/docs/
- Caching strategies
- TTL management

### Prometheus
- https://prometheus.io/docs/
- Metrics best practices
- PromQL queries

### Docker
- https://docs.docker.com/
- Multi-container applications
- docker-compose

---

## 📞 Contact & Support

**Repository**: https://github.com/himanshugarg06/token-optimizer
**Issues**: https://github.com/himanshugarg06/token-optimizer/issues
**Documentation**: See backend/ directory

---

**Happy coding! 🚀**
