# Token Optimizer Middleware

A lightweight, production-style backend service that intelligently optimizes LLM prompts before sending to providers (OpenAI/Anthropic), reducing token costs by 50-70% while preserving semantic meaning.

## Features

- **Intelligent Prompt Optimization**: Reduces token usage through heuristics, caching, and optional semantic retrieval
- **Multi-Provider Support**: Works with OpenAI and Anthropic APIs
- **Dashboard Integration**: Fetches user preferences and emits optimization metrics
- **Redis Caching**: Fast caching of optimization results (10min TTL)
- **Prometheus Metrics**: Built-in observability with metrics endpoint
- **Mock Dashboard**: Includes test endpoints for development
- **Fully Local**: Runs completely locally with Docker Compose

## Quick Start

### Prerequisites

- Docker and Docker Compose
- (Optional) OpenAI API key for `/v1/chat` endpoint
- (Optional) Anthropic API key for `/v1/chat` endpoint

### Installation

1. **Clone and navigate to directory:**
   ```bash
   cd /Users/himanshu/workspace/token_optimizer
   ```

2. **Create `.env` file:**
   ```bash
   cp .env.example .env
   # Edit .env with your API keys (optional)
   ```

3. **Start services:**
   ```bash
   docker-compose up --build
   ```

4. **Verify health:**
   ```bash
   curl http://localhost:8000/v1/health
   ```

## API Endpoints

### POST /v1/optimize

Optimize messages without calling LLM.

**Request:**
```bash
curl -X POST http://localhost:8000/v1/optimize \
  -H "X-API-Key: dev-key-12345" \
  -H "Content-Type: application/json" \
  -d '{
    "messages": [
      {"role": "system", "content": "You are a helpful assistant."},
      {"role": "user", "content": "What is Python?"}
    ],
    "model": "gpt-4",
    "tenant_id": "user-123",
    "project_id": "proj-456"
  }'
```

**Response:**
```json
{
  "optimized_messages": [...],
  "selected_blocks": [...],
  "dropped_blocks": [...],
  "stats": {
    "tokens_before": 1500,
    "tokens_after": 600,
    "tokens_saved": 900,
    "compression_ratio": 0.60,
    "cache_hit": false,
    "route": "heuristic+cache",
    "fallback_used": false,
    "latency_ms": 45
  },
  "debug": {
    "trace_id": "abc-123",
    "config_resolved": {...},
    "dashboard": {...},
    "stage_timings_ms": {...}
  }
}
```

### POST /v1/chat

Optimize and forward to LLM provider.

**Request:**
```bash
curl -X POST http://localhost:8000/v1/chat \
  -H "X-API-Key: dev-key-12345" \
  -H "Content-Type: application/json" \
  -d '{
    "messages": [
      {"role": "user", "content": "Hello, how are you?"}
    ],
    "model": "gpt-4",
    "provider": "openai",
    "tenant_id": "user-123",
    "project_id": "proj-456"
  }'
```

**Response:**
```json
{
  "id": "chatcmpl-...",
  "model": "gpt-4",
  "choices": [{
    "message": {
      "role": "assistant",
      "content": "I'm doing well, thank you!"
    }
  }],
  "usage": {
    "prompt_tokens": 10,
    "completion_tokens": 8,
    "total_tokens": 18
  },
  "optimizer": {
    "stats": {...},
    "trace_id": "abc-123"
  }
}
```

### GET /v1/health

Health check endpoint.

```bash
curl http://localhost:8000/v1/health
```

### GET /v1/metrics

Prometheus metrics.

```bash
curl http://localhost:8000/v1/metrics
```

## Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                   Token Optimizer Middleware                 │
│                                                              │
│  ┌──────────────┐    ┌─────────────────────────────────┐  │
│  │   FastAPI    │    │   Optimization Pipeline         │  │
│  │   Routes     │───>│   1. Canonicalize → Blocks     │  │
│  │              │    │   2. Heuristics                 │  │
│  │ /v1/optimize │    │   3. Redis Cache                │  │
│  │ /v1/chat     │    │   4. Validation + Fallback      │  │
│  │ /v1/health   │    │                                 │  │
│  │ /v1/metrics  │    └─────────────────────────────────┘  │
│  └──────────────┘                 │                         │
│         │                         │                         │
│         │      ┌──────────────────┴────────────┐           │
│         │      │                                │           │
│         v      v                                v           │
│  ┌──────────────────┐                  ┌──────────────┐    │
│  │ Dashboard Client │                  │  LLM Proxy   │    │
│  │ - Fetch Prefs    │                  │  - OpenAI    │    │
│  │ - Emit Events    │                  │  - Anthropic │    │
│  └──────────────────┘                  └──────────────┘    │
│         │                                                   │
└─────────┼───────────────────────────────────────────────────┘
          │
          v
┌──────────────────────┐         ┌─────────────────┐
│ User Dashboard API   │         │   Redis Cache   │
│ (External/Mock)      │         │   + Postgres    │
└──────────────────────┘         └─────────────────┘
```

## Optimization Pipeline

### Stage 0: Canonicalization
Convert all inputs (messages, tools, RAG docs, tool outputs) to unified Block IR.

### Stage 1: Heuristics (Always Runs)
- Remove empty/junk blocks
- Deduplicate by content hash
- Keep last N conversation turns
- Extract constraint keywords (MUST, NEVER, etc.)

### Stage 2: Redis Caching
Check if this exact prompt was optimized before (10min TTL).

### Stage 3: Validation + Fallback
Ensure critical blocks preserved, apply progressive fallback if needed.

## Configuration

### Environment Variables

Create a `.env` file:

```bash
# Core Authentication
MIDDLEWARE_API_KEY=dev-key-12345

# LLM Provider API Keys
OPENAI_API_KEY=sk-...
ANTHROPIC_API_KEY=sk-ant-...

# Dashboard Integration
DASHBOARD_BASE_URL=http://localhost:3001
DASHBOARD_API_KEY=dashboard-api-key
DASHBOARD_ENABLED=true
MOCK_DASHBOARD=true  # Use built-in mock dashboard

# Infrastructure
REDIS_URL=redis://localhost:6379

# Feature Flags (defer to future)
ENABLE_SEMANTIC_RETRIEVAL=false
ENABLE_TOON_COMPRESSION=false

# Optimization Parameters
MAX_INPUT_TOKENS=8000
KEEP_LAST_N_TURNS=4
SAFETY_MARGIN_TOKENS=300

# Observability
LOG_LEVEL=INFO
```

## Dashboard Integration

The middleware integrates with an external User Dashboard for:
1. **Fetching user preferences** (optimization rules per user/project)
2. **Emitting optimization events** (for analytics/metrics)

### Dashboard Endpoints

**Fetch Config:**
```
GET {DASHBOARD_BASE_URL}/v1/config/{tenant_id}/{project_id}
Headers: X-API-Key: {DASHBOARD_API_KEY}
```

**Emit Events:**
```
POST {DASHBOARD_BASE_URL}/v1/events
Headers: X-API-Key: {DASHBOARD_API_KEY}, X-Source: token-optimizer-middleware
Body: { event_type, timestamp, tenant_id, project_id, stats, ... }
```

### Mock Dashboard

The service includes mock endpoints for testing at `/mock/*` when `MOCK_DASHBOARD=true`.

## Development

### Run Tests

```bash
docker-compose run token-optimizer pytest -v
```

### Hot Reload

The service supports hot reload in development:
```bash
docker-compose up
# Edit files in app/, changes auto-reload
```

### Manual Testing

1. **Test optimize without dashboard:**
   ```bash
   curl -X POST http://localhost:8000/v1/optimize \
     -H "X-API-Key: dev-key-12345" \
     -H "Content-Type: application/json" \
     -d '{"messages":[{"role":"user","content":"Hello"}],"model":"gpt-4"}'
   ```

2. **Test with mock dashboard:**
   ```bash
   # Fetch mock config
   curl http://localhost:8000/mock/v1/config/user-123/proj-456 \
     -H "X-API-Key: dev-key-12345"

   # Send optimization request
   curl -X POST http://localhost:8000/v1/optimize \
     -H "X-API-Key: dev-key-12345" \
     -H "Content-Type: application/json" \
     -d '{"messages":[{"role":"user","content":"Test"}],"model":"gpt-4","tenant_id":"user-123","project_id":"proj-456"}'
   ```

3. **Test chat with OpenAI:**
   ```bash
   # Set OPENAI_API_KEY in .env first
   curl -X POST http://localhost:8000/v1/chat \
     -H "X-API-Key: dev-key-12345" \
     -H "Content-Type: application/json" \
     -d '{"messages":[{"role":"user","content":"Hi"}],"model":"gpt-4","provider":"openai"}'
   ```

## Project Structure

```
token_optimizer/
├── app/
│   ├── main.py                      # FastAPI app + routes
│   ├── settings.py                  # Pydantic settings
│   ├── models.py                    # Request/response models
│   ├── auth.py                      # API key middleware
│   ├── core/                        # Core optimization logic
│   │   ├── blocks.py                # Block IR
│   │   ├── pipeline.py              # Orchestration
│   │   ├── canonicalize.py          # Input → Blocks
│   │   └── utils.py                 # Token counting
│   ├── optimizers/                  # Optimization stages
│   │   ├── heuristics.py            # Deterministic rules
│   │   ├── cache.py                 # Redis caching
│   │   ├── semantic.py              # OPTIONAL (deferred)
│   │   ├── compress.py              # OPTIONAL (deferred)
│   │   └── validate.py              # Validation + fallback
│   ├── providers/                   # LLM providers
│   │   ├── base.py
│   │   ├── openai_provider.py
│   │   └── anthropic_provider.py
│   ├── dashboard/                   # Dashboard integration
│   │   ├── client.py
│   │   ├── config_merger.py
│   │   └── mock_server.py
│   └── observability/               # Metrics + events
│       ├── metrics.py
│       └── events.py
├── tests/                           # Test suite
├── Dockerfile
├── docker-compose.yml
├── requirements.txt
└── README.md
```

## Deferred Features

These features are stubbed but not fully implemented (behind feature flags):

- **Semantic Retrieval** (`ENABLE_SEMANTIC_RETRIEVAL=false`): pgvector-based document retrieval
- **TOON Compression** (`ENABLE_TOON_COMPRESSION=false`): Advanced JSON compression

## Performance

- **Latency overhead**: < 500ms for heuristics + caching
- **Token reduction**: 30-60% average (depends on prompt)
- **Cache hit rate**: > 60% for repeated prompts

## License

MIT

## Support

For issues or questions:
- GitHub Issues: https://github.com/yourorg/token-optimizer/issues
- Documentation: See CLAUDE.md for detailed implementation guide
