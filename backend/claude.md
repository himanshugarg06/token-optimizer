# Token Optimizer Middleware - Implementation Guide

## Project Overview

Build a production-grade Python middleware library that intelligently compresses LLM prompts before sending to providers (OpenAI/Anthropic), reducing token costs by 50-70% while preserving semantic meaning. The middleware emits real-time optimization stats to an external analytics dashboard.

## Architecture

```
┌─────────────────┐
│  User App Code  │
└────────┬────────┘
         │
         ▼
┌─────────────────────────────────────┐
│   TokenOptimizer Middleware         │
│  ┌─────────────────────────────┐   │
│  │  1. Canonicalize → Blocks   │   │
│  │  2. Heuristics              │   │
│  │  3. Cache Check (Redis)     │   │
│  │  4. Semantic Retrieval      │   │
│  │  5. LLMLingua-2 Compress    │   │
│  │  6. Validate & Fallback     │   │
│  └─────────────────────────────┘   │
└────────┬────────────────────┬───────┘
         │                    │
         ▼                    ▼
┌─────────────────┐   ┌──────────────────┐
│  LLM Provider   │   │ Analytics API    │
│  (OpenAI/       │   │ (User Dashboard) │
│   Anthropic)    │   │                  │
└─────────────────┘   └──────────────────┘
```

## Core Components

### 1. Middleware Entry Point
**File**: `token_optimizer/middleware.py`

Main class that developers instantiate. Provides drop-in replacement for OpenAI/Anthropic SDKs.

**Key Responsibilities**:
- Initialize configuration
- Provide `.chat.completions.create()` interface (OpenAI-compatible)
- Provide `.messages.create()` interface (Anthropic-compatible)
- Orchestrate compression pipeline
- Forward to provider
- Emit telemetry

### 2. Compression Pipeline
**File**: `token_optimizer/optimizer/pipeline.py`

Core algorithm orchestrator.

**Pipeline Flow**:
```python
def optimize(messages, tools=None, **kwargs):
    # Stage 0: Convert input to internal Block IR
    blocks = canonicalize(messages, tools)
    
    # Stage 1: Deterministic heuristics (always runs)
    blocks = apply_heuristics(blocks)
    
    # Stage 2: Check cache (if enabled)
    cached = check_cache(blocks)
    if cached:
        return cached
    
    # Stage 3: Semantic reduction (if over budget and enabled)
    if total_tokens(blocks) > max_tokens and enable_semantic:
        blocks = semantic_reduce(blocks)
    
    # Stage 4: LLMLingua-2 compression (if still over budget)
    if total_tokens(blocks) > max_tokens and enable_compression:
        blocks = compress_blocks(blocks)
    
    # Stage 5: Validate & fallback
    blocks, fallback_used = validate_and_fallback(blocks)
    
    # Stage 6: Assemble final prompt
    optimized_messages = blocks_to_messages(blocks)
    
    return optimized_messages, stats
```

### 3. Block Internal Representation (IR)
**File**: `token_optimizer/models.py`

**Block Structure**:
```python
@dataclass
class Block:
    id: str                    # UUID
    type: BlockType            # system, user, assistant, tool, doc, constraint
    content: str               # Actual text
    must_keep: bool            # Never compress/drop
    priority: float            # 0.0-1.0
    tokens: int                # Token count
    timestamp: datetime        # For recency scoring
    metadata: dict             # Source, fingerprint, etc.
    compressed: bool = False   # Was LLMLingua applied?
```

**BlockType Enum**:
- `system`: System prompts (must_keep=True)
- `developer`: Developer messages (must_keep=True)
- `user`: User messages (must_keep=True for latest)
- `assistant`: Assistant responses (compressible if old)
- `tool`: Tool schemas (minimizable)
- `doc`: RAG documents (retrievable/compressible)
- `constraint`: Extracted constraints (must_keep=True)

### 4. Heuristics Module
**File**: `token_optimizer/optimizer/heuristics.py`

Implements deterministic compression strategies.

**Functions to Implement**:

```python
def remove_junk(blocks: List[Block], patterns: List[str]) -> List[Block]:
    """Remove empty/whitespace blocks and apply regex patterns"""
    # Remove blocks matching junk_regexes from config
    # Only apply to assistant blocks older than keep_last_n_turns
    pass

def deduplicate(blocks: List[Block]) -> List[Block]:
    """Hash-based deduplication, keep most recent"""
    # fingerprint = sha256(normalize(content))
    # Group by fingerprint, keep max(timestamp)
    pass

def minimize_tool_schemas(blocks: List[Block], allowlist: List[str]) -> List[Block]:
    """Reduce tool schema verbosity"""
    # Keep only: name, parameters, required
    # Drop: descriptions, examples
    # Filter to allowlist
    pass

def compress_json_toon(content: str) -> str:
    """Apply TOON (Token-Oriented Object Notation) to JSON"""
    # Before: [{"id":"1","name":"Alice"},{"id":"2","name":"Bob"}]
    # After: Schema#0[1,Alice|2,Bob]
    # ~60% token reduction
    pass

def trim_logs(content: str, error_window: int, tail_lines: int) -> str:
    """Keep only relevant log lines"""
    # Find lines with ERROR/Exception/Traceback
    # Keep ±error_window lines around errors
    # Also keep last tail_lines
    pass

def extract_constraints(blocks: List[Block]) -> Optional[Block]:
    """Extract critical directives into dedicated block"""
    # Keywords: MUST, MUST NOT, ALWAYS, NEVER, FORMAT, JSON, DEADLINE
    # Create new Block(type=constraint, must_keep=True)
    pass

def keep_last_n_turns(blocks: List[Block], n: int) -> List[Block]:
    """Mark last N conversation turns as must_keep"""
    # Identify user+assistant pairs
    # Set must_keep=True for last N turns
    pass
```

### 5. Caching Module
**File**: `token_optimizer/optimizer/cache.py`

Redis-based caching for repeated prompts.

**Implementation**:
```python
class CacheManager:
    def __init__(self, redis_url: str):
        self.redis = redis.from_url(redis_url)
    
    def get_exact(self, key: str) -> Optional[dict]:
        """Check exact prompt cache (10min TTL)"""
        # key = sha256(api_key + model + config_hash + input_hash)
        pass
    
    def set_exact(self, key: str, value: dict, ttl: int = 600):
        """Store exact prompt result"""
        pass
    
    def get_prefix(self, prefix_key: str) -> Optional[str]:
        """Check stable prefix cache (1hr TTL)"""
        # prefix = system + developer + static schema (post-minimization)
        pass
    
    def set_prefix(self, prefix_key: str, prefix: str, ttl: int = 3600):
        """Store stable prefix"""
        pass
```

### 6. Semantic Retrieval Module
**File**: `token_optimizer/optimizer/semantic.py`

Embedding-based intelligent block selection.

**Key Components**:

```python
class EmbeddingService:
    def __init__(self, model_name: str = "BAAI/bge-small-en-v1.5"):
        from sentence_transformers import SentenceTransformer
        self.model = SentenceTransformer(model_name)
    
    def embed(self, texts: List[str]) -> np.ndarray:
        """Batch embed texts"""
        return self.model.encode(texts, normalize_embeddings=True)

class VectorStore:
    def __init__(self, postgres_url: str):
        self.db = connect(postgres_url)
    
    def store_block(self, block: Block, embedding: np.ndarray):
        """Store block + embedding in pgvector"""
        pass
    
    def similarity_search(self, query_embedding: np.ndarray, 
                         top_k: int, api_key: str) -> List[Block]:
        """Retrieve similar blocks using pgvector"""
        # SELECT * FROM blocks b
        # JOIN embeddings e ON b.id = e.block_id
        # WHERE b.api_key = ?
        # ORDER BY e.embedding <=> ? LIMIT ?
        pass

def mmr_selection(candidates: List[Block], query_embedding: np.ndarray,
                  lambda_param: float, top_k: int) -> List[Block]:
    """Maximal Marginal Relevance for diversity"""
    # MMR = λ * sim(q, d) - (1-λ) * max(sim(d, selected))
    # Iteratively select blocks maximizing MMR
    pass

def compute_utility_score(block: Block, query_embedding: np.ndarray,
                         config: dict) -> float:
    """Multi-factor utility scoring"""
    sim = cosine_similarity(query_embedding, block.embedding)
    recency = recency_boost(block.timestamp)
    constraint_hits = count_constraint_keywords(block.content)
    identifier_hits = count_identifiers(block.content)
    source_trust = get_source_trust(block.metadata.get("source"))
    entity_score = entity_preservation_score(block.content)
    
    return (
        0.40 * sim +
        0.20 * recency +
        0.15 * constraint_hits +
        0.10 * identifier_hits +
        0.10 * source_trust +
        0.05 * entity_score
    )
```

### 7. Budget Selection
**File**: `token_optimizer/optimizer/budget.py`

Greedy knapsack for token budget allocation.

```python
def budget_select(blocks: List[Block], max_tokens: int, 
                  safety_margin: int, per_type_fractions: dict) -> List[Block]:
    """Select blocks within budget constraints"""
    
    # Step 1: Include all must_keep blocks
    selected = [b for b in blocks if b.must_keep]
    used_tokens = sum(b.tokens for b in selected)
    budget = max_tokens - safety_margin - used_tokens
    
    # Step 2: Calculate per-type budgets
    type_budgets = {
        t: budget * fraction 
        for t, fraction in per_type_fractions.items()
    }
    
    # Step 3: Greedy select by utility/tokens ratio
    remaining = [b for b in blocks if not b.must_keep]
    remaining.sort(key=lambda b: b.utility / b.tokens, reverse=True)
    
    for block in remaining:
        if type_budgets[block.type] >= block.tokens:
            selected.append(block)
            type_budgets[block.type] -= block.tokens
    
    return selected
```

### 8. Compression Module
**File**: `token_optimizer/optimizer/compress.py`

LLMLingua-2 integration with faithfulness checking.

```python
class LLMLinguaCompressor:
    def __init__(self, compression_ratio: float = 0.5):
        try:
            from llmlingua import PromptCompressor
            self.compressor = PromptCompressor(
                model_name="microsoft/llmlingua-2-bert-base-multilingual-cased-meetingbank",
                device="cpu"
            )
            self.available = True
        except ImportError:
            self.available = False
            self.fallback = ExtractiveSummarizer()
    
    def compress_block(self, block: Block, ratio: float) -> Block:
        """Compress block content"""
        if not self.available:
            return self.fallback.compress(block, ratio)
        
        compressed = self.compressor.compress_prompt(
            block.content,
            rate=ratio,
            force_tokens=["\n", ".", "!", "?", "```"]
        )
        
        # Faithfulness check
        score = self.faithfulness_score(block.content, compressed["compressed_prompt"])
        if score < 0.85:
            return block  # Don't compress if faithfulness too low
        
        block.content = compressed["compressed_prompt"]
        block.tokens = count_tokens(block.content)
        block.compressed = True
        return block
    
    def faithfulness_score(self, original: str, compressed: str) -> float:
        """Measure information preservation"""
        # Option 1: BERTScore
        # Option 2: Entity overlap
        # Option 3: ROUGE-L
        # Return 0.0-1.0 score
        pass

class ExtractiveSummarizer:
    """Fallback if LLMLingua unavailable"""
    def __init__(self):
        from sumy.parsers.plaintext import PlaintextParser
        from sumy.nlp.tokenizers import Tokenizer
        from sumy.summarizers.text_rank import TextRankSummarizer
        self.summarizer = TextRankSummarizer()
    
    def compress(self, block: Block, ratio: float) -> Block:
        """Extractive summarization fallback"""
        # Keep sentences with highest TextRank scores
        # Preserve sentences with constraints/identifiers
        pass
```

### 9. Validation & Fallback
**File**: `token_optimizer/optimizer/validate.py`

Ensure critical components preserved.

```python
def validate(blocks: List[Block], config: dict) -> tuple[bool, List[str]]:
    """Validate optimized prompt"""
    errors = []
    
    # Check 1: System message present
    if not any(b.type == "system" for b in blocks):
        errors.append("Missing system message")
    
    # Check 2: User message present
    if not any(b.type == "user" for b in blocks):
        errors.append("Missing user message")
    
    # Check 3: Constraints preserved (if existed)
    if config.get("had_constraints") and not any(b.type == "constraint" for b in blocks):
        errors.append("Constraints dropped")
    
    # Check 4: Tool schemas present (if tools enabled)
    if config.get("tools_enabled") and not any(b.type == "tool" for b in blocks):
        errors.append("Tool schemas missing")
    
    # Check 5: Token budget satisfied
    total = sum(b.tokens for b in blocks)
    if total > config["max_input_tokens"]:
        errors.append(f"Over budget: {total} > {config['max_input_tokens']}")
    
    return len(errors) == 0, errors

def apply_fallback(blocks: List[Block], config: dict, 
                   validation_errors: List[str]) -> tuple[List[Block], bool]:
    """Progressive fallback strategy"""
    
    # Fallback 1: Disable LLMLingua compression
    blocks = [b for b in blocks if not b.compressed] + \
             [Block(id=b.id, content=b.original_content, ...) 
              for b in blocks if b.compressed]
    
    if validate(blocks, config)[0]:
        return blocks, True
    
    # Fallback 2: Increase keep_last_n_turns
    config["keep_last_n_turns"] += 2
    blocks = rerun_pipeline_with_config(blocks, config)
    
    if validate(blocks, config)[0]:
        return blocks, True
    
    # Fallback 3: Minimal safe prompt
    safe_blocks = [
        b for b in blocks 
        if b.type in ["system", "developer", "user", "constraint"]
    ]
    # Add minimal tool schema if needed
    if config.get("tools_enabled"):
        safe_blocks.extend([b for b in blocks if b.type == "tool"][:1])
    
    return safe_blocks, True
```

### 10. Provider Integrations
**Files**: 
- `token_optimizer/providers/base.py`
- `token_optimizer/providers/openai.py`
- `token_optimizer/providers/anthropic.py`

**Base Interface**:
```python
class BaseProvider(ABC):
    @abstractmethod
    def chat_completion(self, messages: List[dict], **kwargs) -> dict:
        """Send optimized messages to provider"""
        pass
    
    @abstractmethod
    def normalize_response(self, raw_response: Any) -> dict:
        """Normalize provider response to common format"""
        pass
```

**OpenAI Provider**:
```python
class OpenAIProvider(BaseProvider):
    def __init__(self, api_key: str):
        import openai
        self.client = openai.Client(api_key=api_key)
    
    def chat_completion(self, messages: List[dict], **kwargs) -> dict:
        response = self.client.chat.completions.create(
            messages=messages,
            **kwargs
        )
        return self.normalize_response(response)
    
    def normalize_response(self, raw_response) -> dict:
        return {
            "id": raw_response.id,
            "model": raw_response.model,
            "choices": [
                {
                    "message": {
                        "role": choice.message.role,
                        "content": choice.message.content
                    },
                    "finish_reason": choice.finish_reason
                }
                for choice in raw_response.choices
            ],
            "usage": {
                "prompt_tokens": raw_response.usage.prompt_tokens,
                "completion_tokens": raw_response.usage.completion_tokens,
                "total_tokens": raw_response.usage.total_tokens
            }
        }
```

**Anthropic Provider**:
```python
class AnthropicProvider(BaseProvider):
    def __init__(self, api_key: str):
        import anthropic
        self.client = anthropic.Client(api_key=api_key)
    
    def chat_completion(self, messages: List[dict], **kwargs) -> dict:
        # Convert messages format
        system = next((m["content"] for m in messages if m["role"]=="system"), None)
        other_messages = [m for m in messages if m["role"]!="system"]
        
        response = self.client.messages.create(
            system=system,
            messages=other_messages,
            **kwargs
        )
        return self.normalize_response(response)
    
    def normalize_response(self, raw_response) -> dict:
        return {
            "id": raw_response.id,
            "model": raw_response.model,
            "choices": [
                {
                    "message": {
                        "role": "assistant",
                        "content": block.text
                    },
                    "finish_reason": raw_response.stop_reason
                }
                for block in raw_response.content
            ],
            "usage": {
                "prompt_tokens": raw_response.usage.input_tokens,
                "completion_tokens": raw_response.usage.output_tokens,
                "total_tokens": raw_response.usage.input_tokens + raw_response.usage.output_tokens
            }
        }
```

### 11. Telemetry Emitter
**File**: `token_optimizer/telemetry/emitter.py`

Async event emission to analytics dashboard.

```python
import threading
import queue
import requests
from typing import List

class TelemetryEmitter:
    def __init__(self, analytics_url: str, api_key: str,
                 batch_size: int = 10, flush_interval: int = 5):
        self.analytics_url = analytics_url
        self.api_key = api_key
        self.batch_size = batch_size
        self.flush_interval = flush_interval
        
        self.event_queue = queue.Queue()
        self.buffer = []
        self.lock = threading.Lock()
        
        # Start background flush thread
        self.flush_thread = threading.Thread(target=self._flush_loop, daemon=True)
        self.flush_thread.start()
    
    def emit(self, event: dict):
        """Add event to buffer (non-blocking)"""
        with self.lock:
            self.buffer.append(event)
            if len(self.buffer) >= self.batch_size:
                self._flush()
    
    def _flush(self):
        """Send batched events to analytics API"""
        if not self.buffer:
            return
        
        events_to_send = self.buffer.copy()
        self.buffer.clear()
        
        try:
            response = requests.post(
                self.analytics_url,
                json={
                    "api_key": self.api_key,
                    "events": events_to_send
                },
                headers={"Content-Type": "application/json"},
                timeout=5
            )
            response.raise_for_status()
        except Exception as e:
            # Log error but don't crash main execution
            import logging
            logging.error(f"Failed to emit telemetry: {e}")
    
    def _flush_loop(self):
        """Periodic flush thread"""
        import time
        while True:
            time.sleep(self.flush_interval)
            with self.lock:
                self._flush()
    
    def shutdown(self):
        """Flush remaining events on shutdown"""
        with self.lock:
            self._flush()
```

**Event Schema**:
```python
def create_optimization_event(
    trace_id: str,
    api_key: str,
    request: dict,
    optimization: dict,
    blocks: dict,
    performance: dict
) -> dict:
    return {
        "event_type": "optimization_completed",
        "timestamp": datetime.utcnow().isoformat() + "Z",
        "api_key": api_key,
        "trace_id": trace_id,
        "request": {
            "provider": request["provider"],
            "model": request["model"],
            "input_messages_count": len(request["messages"])
        },
        "optimization": {
            "tokens_before": optimization["tokens_before"],
            "tokens_after": optimization["tokens_after"],
            "tokens_saved": optimization["tokens_saved"],
            "compression_ratio": optimization["compression_ratio"],
            "route": optimization["route"],
            "cache_hit": optimization["cache_hit"],
            "fallback_used": optimization["fallback_used"]
        },
        "blocks": {
            "selected": [
                {
                    "type": b["type"],
                    "tokens": b["tokens"],
                    "reason": b["reason"]
                }
                for b in blocks["selected"]
            ],
            "dropped": [
                {
                    "type": b["type"],
                    "tokens": b["tokens"],
                    "reason": b["reason"]
                }
                for b in blocks["dropped"]
            ]
        },
        "performance": {
            "latency_ms": performance["latency_ms"],
            "stage_timings": performance["stage_timings"]
        },
        "faithfulness_score": optimization.get("faithfulness_score", 1.0),
        "metadata": {
            "sdk_version": "1.0.0",
            "python_version": platform.python_version()
        }
    }
```

### 12. Token Counting
**File**: `token_optimizer/utils.py`

Model-aware token counting.

```python
def count_tokens(text: str, model: str) -> int:
    """Count tokens for given model"""
    if model.startswith("gpt-"):
        # Use tiktoken for OpenAI models
        import tiktoken
        encoding = tiktoken.encoding_for_model(model)
        return len(encoding.encode(text))
    else:
        # Fallback: HuggingFace tokenizers
        from transformers import AutoTokenizer
        tokenizer = AutoTokenizer.from_pretrained(
            _get_tokenizer_name(model),
            trust_remote_code=True
        )
        return len(tokenizer.encode(text))

def _get_tokenizer_name(model: str) -> str:
    """Map model names to tokenizer names"""
    mappings = {
        "claude-": "anthropic/claude-tokenizer",  # Hypothetical
        # Add more mappings
    }
    for prefix, tokenizer in mappings.items():
        if model.startswith(prefix):
            return tokenizer
    return "gpt2"  # Safe fallback
```

### 13. Configuration Management
**File**: `token_optimizer/config.py`

```python
@dataclass
class OptimizerConfig:
    # Required
    api_key: str
    analytics_url: str
    provider: str
    target_model: str
    max_input_tokens: int = 8000
    
    # Heuristics
    safety_margin_tokens: int = 300
    keep_last_n_turns: int = 4
    junk_regexes: List[str] = field(default_factory=lambda: [
        r"^\s*$",
        r"^(Sure\.|Of course\.|I can help.*)$"
    ])
    dedupe_window: int = 200
    json_truncate_items: int = 200
    json_truncate_chars: int = 60000
    log_error_window_lines: int = 30
    log_tail_lines: int = 80
    
    # Features
    enable_tools: bool = True
    tool_allowlist: List[str] = field(default_factory=lambda: ["*"])
    enable_caching: bool = False
    enable_semantic_retrieval: bool = False
    enable_compression: bool = True
    
    # Semantic retrieval
    vector_topk_per_type: dict = field(default_factory=lambda: {
        "chat": 20,
        "doc": 30,
        "tool": 15
    })
    mmr_lambda: float = 0.7
    embedding_model: str = "BAAI/bge-small-en-v1.5"
    
    # Compression
    compression_ratio: float = 0.5
    faithfulness_threshold: float = 0.85
    
    # Budget allocation
    per_type_budget_fraction: dict = field(default_factory=lambda: {
        "doc": 0.4,
        "chat": 0.3,
        "tool": 0.2,
        "assistant": 0.1
    })
    
    # Storage
    redis_url: Optional[str] = None
    postgres_url: Optional[str] = None
    
    # Telemetry
    emit_batch_size: int = 10
    emit_interval_seconds: int = 5
    emit_async: bool = True
    
    def validate(self):
        """Validate configuration"""
        if self.enable_caching and not self.redis_url:
            raise ValueError("redis_url required when enable_caching=True")
        if self.enable_semantic_retrieval and not self.postgres_url:
            raise ValueError("postgres_url required when enable_semantic_retrieval=True")
```

## Database Schema

### Postgres + pgvector

**Migration**: `token_optimizer/storage/migrations/001_init.sql`

```sql
-- Enable pgvector extension
CREATE EXTENSION IF NOT EXISTS vector;

-- Blocks table
CREATE TABLE blocks (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    api_key TEXT NOT NULL,
    content_hash TEXT NOT NULL,
    content TEXT NOT NULL,
    type TEXT NOT NULL,
    tokens INTEGER NOT NULL,
    created_at TIMESTAMP DEFAULT NOW(),
    metadata JSONB,
    CONSTRAINT valid_type CHECK (type IN ('system', 'developer', 'user', 'assistant', 'tool', 'doc', 'constraint'))
);

-- Embeddings table (384 dimensions for BAAI/bge-small-en-v1.5)
CREATE TABLE embeddings (
    block_id UUID PRIMARY KEY REFERENCES blocks(id) ON DELETE CASCADE,
    embedding vector(384) NOT NULL
);

-- Indexes
CREATE INDEX idx_blocks_api_key ON blocks(api_key);
CREATE INDEX idx_blocks_created_at ON blocks(created_at DESC);
CREATE INDEX idx_blocks_content_hash ON blocks(content_hash);

-- Vector similarity index (IVFFlat)
CREATE INDEX idx_embeddings_vector ON embeddings 
USING ivfflat (embedding vector_cosine_ops) 
WITH (lists = 100);

-- Request traces (optional - for debugging)
CREATE TABLE request_traces (
    trace_id UUID PRIMARY KEY,
    api_key TEXT NOT NULL,
    tokens_before INTEGER NOT NULL,
    tokens_after INTEGER NOT NULL,
    tokens_saved INTEGER NOT NULL,
    compression_ratio FLOAT NOT NULL,
    route TEXT NOT NULL,
    cache_hit BOOLEAN NOT NULL,
    fallback_used BOOLEAN NOT NULL,
    latency_ms INTEGER NOT NULL,
    selected_blocks JSONB NOT NULL,
    dropped_blocks JSONB NOT NULL,
    stage_timings JSONB NOT NULL,
    faithfulness_score FLOAT,
    created_at TIMESTAMP DEFAULT NOW()
);

CREATE INDEX idx_traces_api_key ON request_traces(api_key, created_at DESC);
```

## Implementation Checklist

### Phase 1: Core Foundation (Days 1-2)
- [ ] Project structure scaffolding
- [ ] `models.py`: Block, OptimizerConfig, Response models
- [ ] `config.py`: Configuration management
- [ ] `utils.py`: Token counting (tiktoken + HF fallback)
- [ ] Basic tests for token counting

### Phase 2: Heuristics Engine (Days 2-3)
- [ ] `optimizer/heuristics.py`:
  - [ ] `remove_junk()`
  - [ ] `deduplicate()`
  - [ ] `minimize_tool_schemas()`
  - [ ] `compress_json_toon()`
  - [ ] `trim_logs()`
  - [ ] `extract_constraints()`
  - [ ] `keep_last_n_turns()`
- [ ] Unit tests for each heuristic
- [ ] Golden test: verify must_keep blocks never dropped

### Phase 3: Pipeline Orchestration (Days 3-4)
- [ ] `optimizer/canonicalize.py`: Convert inputs → Blocks
- [ ] `optimizer/pipeline.py`: Main orchestration logic
- [ ] `optimizer/validate.py`: Validation + fallback
- [ ] Integration test: end-to-end heuristics-only path

### Phase 4: Provider Integrations (Day 4)
- [ ] `providers/base.py`: BaseProvider interface
- [ ] `providers/openai.py`: OpenAI integration
- [ ] `providers/anthropic.py`: Anthropic integration
- [ ] Tests with mocked provider APIs

### Phase 5: Middleware Interface (Day 5)
- [ ] `middleware.py`: Main TokenOptimizer class
- [ ] OpenAI-compatible interface: `.chat.completions.create()`
- [ ] Anthropic-compatible interface: `.messages.create()`
- [ ] Integration test: full request → response flow

### Phase 6: Telemetry (Day 5)
- [ ] `telemetry/emitter.py`: Event emission logic
- [ ] `telemetry/collector.py`: Local metrics (optional)
- [ ] Test: events sent to mock analytics endpoint

### Phase 7: Caching (Day 6)
- [ ] `optimizer/cache.py`: Redis integration
- [ ] Exact cache implementation
- [ ] Prefix cache implementation
- [ ] Tests with Redis mock

### Phase 8: Semantic Retrieval (Days 6-7)
- [ ] `optimizer/semantic.py`:
  - [ ] EmbeddingService
  - [ ] VectorStore (pgvector)
  - [ ] `mmr_selection()`
  - [ ] `compute_utility_score()`
- [ ] `optimizer/budget.py`: Budget-aware selection
- [ ] Database migration script
- [ ] Tests with Postgres+pgvector

### Phase 9: Compression (Day 7-8)
- [ ] `optimizer/compress.py`:
  - [ ] LLMLinguaCompressor
  - [ ] ExtractiveSummarizer (fallback)
  - [ ] `faithfulness_score()`
- [ ] Tests: verify faithfulness threshold

### Phase 10: Packaging & Docs (Day 8)
- [ ] `setup.py`: Package configuration
- [ ] `requirements.txt`: Dependencies
- [ ] `README.md`: Usage examples
- [ ] `examples/`: Basic, with caching, with semantic, custom config
- [ ] `docker-compose.yml`: Redis + Postgres for local dev

### Phase 11: Optional Service (Day 9)
- [ ] `service/main.py`: FastAPI wrapper
- [ ] `service/api.py`: REST endpoints
- [ ] `service/Dockerfile`
- [ ] Service integration tests

### Phase 12: Polish & Testing (Day 9-10)
- [ ] Comprehensive test suite
- [ ] Performance benchmarks
- [ ] Documentation review
- [ ] Example applications

## Testing Strategy

### Unit Tests
```python
# tests/test_heuristics.py
def test_junk_removal():
    blocks = [
        Block(content="   ", type="assistant"),
        Block(content="Sure, I can help.", type="assistant"),
        Block(content="Real content", type="assistant")
    ]
    result = remove_junk(blocks, [r"^\s*$", r"^Sure.*$"])
    assert len(result) == 1

def test_deduplication():
    blocks = [
        Block(content="Hello", timestamp=datetime(2024,1,1)),
        Block(content="Hello", timestamp=datetime(2024,1,2))
    ]
    result = deduplicate(blocks)
    assert len(result) == 1
    assert result[0].timestamp.day == 2

def test_constraint_extraction():
    blocks = [
        Block(content="You MUST return JSON format.", type="user"),
        Block(content="Also, NEVER include personal info.", type="system")
    ]
    constraint_block = extract_constraints(blocks)
    assert "MUST return JSON" in constraint_block.content
    assert "NEVER include" in constraint_block.content
```

### Integration Tests
```python
# tests/test_integration.py
def test_full_optimization_flow():
    optimizer = TokenOptimizer(
        api_key="test_key",
        analytics_url="http://localhost:9999/events",
        provider="openai",
        target_model="gpt-4",
        max_input_tokens=4000
    )
    
    # Long conversation that needs compression
    messages = [
        {"role": "system", "content": "You are helpful." * 100},
        {"role": "user", "content": "Hi" * 50},
        {"role": "assistant", "content": "Hello!" * 50},
        {"role": "user", "content": "What is 2+2?"}
    ]
    
    response = optimizer.chat.completions.create(
        messages=messages,
        model="gpt-4"
    )
    
    assert response.optimizer_stats["tokens_after"] < 4000
    assert response.optimizer_stats["tokens_saved"] > 0
    assert response.choices[0].message.content
```

### Golden Tests
```python
# tests/test_golden.py
def test_must_keep_blocks_preserved():
    """Ensure critical blocks never dropped"""
    blocks = [
        Block(type="system", content="System", must_keep=True, tokens=100),
        Block(type="user", content="User", must_keep=True, tokens=100),
        Block(type="constraint", content="MUST", must_keep=True, tokens=50),
        Block(type="assistant", content="Old", must_keep=False, tokens=5000)
    ]
    
    result = budget_select(blocks, max_tokens=500, safety_margin=100)
    
    assert all(b in result for b in blocks if b.must_keep)
    assert sum(b.tokens for b in result) <= 500

def test_faithfulness_preservation():
    """Ensure compression preserves key information"""
    original = "The API returns 200 on success, 404 on not found, and 500 on error."
    compressed = compress_block(Block(content=original), ratio=0.5)
    
    assert "200" in compressed.content
    assert "404" in compressed.content
    assert "500" in compressed.content
    assert faithfulness_score(original, compressed.content) >= 0.85
```

## Usage Examples

### Example 1: Basic Usage
```python
# examples/basic_usage.py
from token_optimizer import TokenOptimizer

optimizer = TokenOptimizer(
    api_key="tok_your_api_key",
    analytics_url="https://your-dashboard.com/api/v1/events",
    provider="openai",
    target_model="gpt-4",
    max_input_tokens=8000
)

response = optimizer.chat.completions.create(
    messages=[
        {"role": "system", "content": "You are a helpful coding assistant."},
        {"role": "user", "content": "Explain recursion in Python."}
    ],
    model="gpt-4",
    temperature=0.7
)

print(f"Response: {response.choices[0].message.content}")
print(f"Tokens saved: {response.optimizer_stats['tokens_saved']}")
print(f"Compression ratio: {response.optimizer_stats['compression_ratio']:.2%}")
```

### Example 2: With Caching
```python
# examples/with_caching.py
optimizer = TokenOptimizer(
    api_key="tok_your_api_key",
    analytics_url="https://your-dashboard.com/api/v1/events",
    provider="openai",
    target_model="gpt-4",
    max_input_tokens=8000,
    enable_caching=True,
    redis_url="redis://localhost:6379"
)

# First call - cache miss
response1 = optimizer.chat.completions.create(
    messages=[{"role": "user", "content": "What is Python?"}]
)
print(f"Cache hit: {response1.optimizer_stats['cache_hit']}")  # False

# Second call - cache hit (if within TTL)
response2 = optimizer.chat.completions.create(
    messages=[{"role": "user", "content": "What is Python?"}]
)
print(f"Cache hit: {response2.optimizer_stats['cache_hit']}")  # True
```

### Example 3: With Semantic Retrieval
```python
# examples/with_semantic.py
optimizer = TokenOptimizer(
    api_key="tok_your_api_key",
    analytics_url="https://your-dashboard.com/api/v1/events",
    provider="openai",
    target_model="gpt-4",
    max_input_tokens=8000,
    enable_semantic_retrieval=True,
    postgres_url="postgresql://localhost:5432/optimizer",
    redis_url="redis://localhost:6379"
)

# Pre-load documents into vector store
import requests
requests.post("http://localhost:8000/v1/ingest", json={
    "api_key": "tok_your_api_key",
    "documents": [
        {
            "id": "doc1",
            "content": "Python is a high-level programming language...",
            "type": "doc",
            "metadata": {"source": "docs.python.org"}
        },
        # ... more docs
    ]
})

# Use optimizer - will retrieve relevant docs automatically
response = optimizer.chat.completions.create(
    messages=[
        {"role": "user", "content": "How do I handle exceptions in Python?"}
    ]
)

print(f"Route: {response.optimizer_stats['route']}")  # heuristic+semantic
```

### Example 4: Custom Configuration
```python
# examples/custom_config.py
from token_optimizer import TokenOptimizer, OptimizerConfig

config = OptimizerConfig(
    api_key="tok_your_api_key",
    analytics_url="https://your-dashboard.com/api/v1/events",
    provider="anthropic",
    target_model="claude-3-sonnet-20240229",
    max_input_tokens=100000,  # Claude's large context
    
    # Custom heuristics
    keep_last_n_turns=6,
    junk_regexes=[
        r"^\s*$",
        r"^(Sure\.|Of course\.|I can help.*)$",
        r"^(That's a great question!.*)$"
    ],
    
    # Aggressive compression
    enable_compression=True,
    compression_ratio=0.3,  # 70% reduction
    
    # Budget allocation
    per_type_budget_fraction={
        "doc": 0.5,      # Prioritize documents
        "chat": 0.2,
        "tool": 0.2,
        "assistant": 0.1
    }
)

optimizer = TokenOptimizer(config)

response = optimizer.messages.create(
    messages=[
        {"role": "user", "content": "Analyze this dataset..."}
    ],
    max_tokens=1000
)
```

## Deployment

### Local Development
```bash
# Clone repo
git clone https://github.com/yourorg/token-optimizer
cd token-optimizer

# Install in editable mode
pip install -e ".[dev]"

# Start dependencies
docker-compose up -d

# Run tests
pytest

# Try examples
python examples/basic_usage.py
```

### Docker Compose Setup
```yaml
# docker-compose.yml
version: '3.8'

services:
  redis:
    image: redis:7-alpine
    ports:
      - "6379:6379"
    volumes:
      - redis_data:/data

  postgres:
    image: pgvector/pgvector:pg16
    environment:
      POSTGRES_DB: token_optimizer
      POSTGRES_USER: postgres
      POSTGRES_PASSWORD: postgres
    ports:
      - "5432:5432"
    volumes:
      - postgres_data:/var/lib/postgresql/data
      - ./token_optimizer/storage/migrations:/docker-entrypoint-initdb.d

volumes:
  redis_data:
  postgres_data:
```

### Package Installation
```bash
# From PyPI (once published)
pip install token-optimizer

# With optional dependencies
pip install token-optimizer[semantic]  # Includes postgres, pgvector
pip install token-optimizer[all]       # All optional features
```

## Dependencies

**Core**:
```
# requirements.txt
requests>=2.31.0
tiktoken>=0.5.0
pydantic>=2.5.0
structlog>=24.1.0
```

**Optional**:
```
# Caching
redis>=5.0.0

# Semantic retrieval
psycopg2-binary>=2.9.9
pgvector>=0.2.4
sentence-transformers>=2.2.2
numpy>=1.24.0

# Compression
llmlingua>=0.1.0  # If available
sumy>=0.11.0      # Fallback

# Providers
openai>=1.0.0
anthropic>=0.18.0

# Development
pytest>=7.4.0
pytest-asyncio>=0.21.0
pytest-mock>=3.12.0
black>=23.12.0
mypy>=1.8.0
```

## Performance Targets

- **Latency overhead**: < 500ms for heuristics-only
- **Latency overhead**: < 2s for semantic+compression
- **Token reduction**: 50-70% average
- **Faithfulness score**: > 0.85 average
- **Cache hit rate**: > 60% for repeated prompts
- **Telemetry delivery**: 99%+ success rate

## Monitoring (What Dashboard Receives)

Your analytics dashboard should expect these events:

**Event Types**:
1. `optimization_started`
2. `optimization_completed`
3. `optimization_failed`
4. `cache_hit`
5. `cache_miss`
6. `compression_applied`
7. `fallback_triggered`
8. `provider_error`

**Key Metrics to Visualize**:
- Total tokens saved over time (line chart)
- Compression ratio distribution (histogram)
- P50/P95/P99 latency (line chart)
- Cache hit rate (gauge)
- Fallback rate (gauge)
- Top projects by savings (bar chart)
- Route breakdown (pie chart: heuristic_only vs heuristic+semantic vs heuristic+semantic+compression)
- Faithfulness scores (histogram)

**Example Dashboard Queries** (if using SQL backend):
```sql
-- Total tokens saved today
SELECT SUM(tokens_saved) 
FROM events 
WHERE event_type = 'optimization_completed' 
  AND date(timestamp) = CURRENT_DATE;

-- Average compression ratio by project
SELECT api_key, AVG(compression_ratio) 
FROM events 
WHERE event_type = 'optimization_completed' 
GROUP BY api_key;

-- P95 latency
SELECT PERCENTILE_CONT(0.95) WITHIN GROUP (ORDER BY latency_ms)
FROM events
WHERE event_type = 'optimization_completed';
```

## Security Considerations

1. **API Key Storage**: Never hardcode API keys. Use environment variables or secret management.

2. **Data Privacy**: 
   - Don't log raw prompt content by default
   - Hash content before storing
   - Provide opt-in debug mode for local dev

3. **Rate Limiting**: Dashboard should implement rate limits per api_key.

4. **TLS**: Always use HTTPS for analytics_url.

5. **Input Validation**: Validate all inputs to prevent injection attacks.

## Common Issues & Troubleshooting

**Issue**: "LLMLingua not available"
- **Solution**: Install with `pip install llmlingua`. If fails, fallback to extractive summarization is automatic.

**Issue**: Redis connection error
- **Solution**: Ensure Redis is running. Set `enable_caching=False` if not needed.

**Issue**: "Token count still over budget"
- **Solution**: Check `safety_margin_tokens`, increase `compression_ratio`, or adjust `per_type_budget_fraction`.

**Issue**: Low faithfulness scores
- **Solution**: Decrease `compression_ratio`, increase `faithfulness_threshold`, or disable compression for critical content types.

**Issue**: Telemetry events not appearing
- **Solution**: Check `analytics_url` is reachable, verify API key, check dashboard logs.

## Future Enhancements

- [ ] More providers (Google, Cohere, local models)
- [ ] Streaming support
- [ ] Fine-tuned compression models
- [ ] Multi-modal support (images, audio)
- [ ] A/B testing framework
- [ ] Cost estimation before/after
- [ ] Prompt templates library
- [ ] Auto-tuning based on feedback

## Success Criteria

✅ Library installable via `pip install token-optimizer`
✅ Works with OpenAI SDK interface
✅ Works with Anthropic SDK interface
✅ Achieves 50-70% token reduction
✅ Maintains >0.85 faithfulness score
✅ Emits telemetry to external dashboard
✅ Handles errors gracefully (fallback)
✅ Well-documented with examples
✅ Comprehensive test coverage (>80%)
✅ One-command local dev setup

---

## Quick Reference Commands

```bash
# Setup
pip install -e ".[dev]"
docker-compose up -d

# Run tests
pytest
pytest -v tests/test_heuristics.py
pytest --cov=token_optimizer

# Format code
black token_optimizer/
mypy token_optimizer/

# Build package
python setup.py sdist bdist_wheel

# Install locally
pip install -e .

# Try examples
python examples/basic_usage.py
```

---

**This guide should be treated as the source of truth for implementation. Follow the structure, implement components in order, and ensure all tests pass before moving to the next phase.**

