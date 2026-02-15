"""Pydantic models for API request/response."""

from pydantic import BaseModel, Field
from typing import Optional, List, Dict, Any


class Message(BaseModel):
    """Single message in a conversation."""
    role: str = Field(..., description="Message role (system, user, assistant)")
    content: str = Field(..., description="Message content")


class OptimizeRequest(BaseModel):
    """Request to optimize a prompt."""
    messages: List[Message] = Field(..., description="Conversation messages")
    model: str = Field(default="gpt-4", description="Target model name")
    max_tokens: Optional[int] = Field(None, description="Max input tokens")
    tenant_id: Optional[str] = Field(None, description="User/tenant ID")
    project_id: Optional[str] = Field(None, description="Project ID")
    tools: Optional[Dict[str, Any]] = Field(None, description="Tool schemas")
    rag_context: Optional[List[Dict[str, Any]]] = Field(None, description="RAG documents")
    tool_outputs: Optional[List[Dict[str, Any]]] = Field(None, description="Tool execution outputs")
    user_prefs_overrides: Optional[Dict[str, Any]] = Field(None, description="User preference overrides")


class BlockInfo(BaseModel):
    """Information about a block."""
    id: str
    type: str
    tokens: int
    reason: str = Field(..., description="Why this block was selected/dropped")


class OptimizationStats(BaseModel):
    """Statistics about the optimization."""
    tokens_before: int
    tokens_after: int
    tokens_saved: int
    compression_ratio: float
    cache_hit: bool
    route: str = Field(..., description="Optimization route taken")
    fallback_used: bool
    latency_ms: int


class DebugInfo(BaseModel):
    """Debug information."""
    trace_id: str
    config_resolved: Dict[str, Any]
    dashboard: Dict[str, bool]
    stage_timings_ms: Dict[str, int]


class OptimizeResponse(BaseModel):
    """Response from optimization."""
    optimized_messages: List[Message]
    selected_blocks: List[BlockInfo]
    dropped_blocks: List[BlockInfo]
    stats: OptimizationStats
    debug: DebugInfo


class ChatRequest(OptimizeRequest):
    """Request to optimize and forward to LLM provider."""
    provider: str = Field(..., description="LLM provider (openai, anthropic)")
    temperature: Optional[float] = Field(0.7, description="Sampling temperature")
    max_completion_tokens: Optional[int] = Field(None, description="Max tokens to generate")


class ProviderUsage(BaseModel):
    """Token usage from provider."""
    prompt_tokens: int
    completion_tokens: int
    total_tokens: int


class ChatChoice(BaseModel):
    """Single completion choice."""
    message: Message
    finish_reason: Optional[str] = None


class ChatResponse(BaseModel):
    """Response from chat endpoint."""
    id: str
    model: str
    choices: List[ChatChoice]
    usage: ProviderUsage
    optimizer: Dict[str, Any] = Field(..., description="Optimizer stats")


class HealthResponse(BaseModel):
    """Health check response."""
    status: str
    redis: Optional[str] = None
    postgres: Optional[str] = None
    dashboard: Optional[str] = None
    timestamp: str
