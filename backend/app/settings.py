"""Application settings using pydantic-settings."""

from pydantic import BaseModel, Field
from pydantic_settings import BaseSettings, SettingsConfigDict
from typing import Optional, Dict, List


class SemanticConfig(BaseModel):
    """Configuration for semantic retrieval features."""

    enabled: bool = False
    postgres_url: Optional[str] = None
    embedding_model: str = "BAAI/bge-base-en-v1.5"
    embedding_dim: int = 768
    embedding_device: str = "cpu"
    vector_topk: int = 30
    mmr_lambda: float = 0.7  # Relevance vs diversity (0.7 = 70% relevance)
    similarity_threshold: float = 0.3  # Minimum cosine similarity
    batch_size: int = 32


class CompressionConfig(BaseModel):
    """Configuration for compression features."""

    model_config = {"protected_namespaces": ()}  # Allow model_name field

    enabled: bool = False
    model_name: str = "microsoft/llmlingua-2-bert-base-multilingual-cased-meetingbank"
    compression_ratio: float = 0.5
    faithfulness_threshold: float = 0.85
    device: str = "cpu"
    fallback_to_extractive: bool = True
    force_tokens: List[str] = Field(default_factory=lambda: ["\n", ".", "!", "?", "```", ":", ";"])


class BudgetConfig(BaseModel):
    """Configuration for token budget allocation."""

    per_type_fractions: Dict[str, float] = Field(default_factory=lambda: {
        "doc": 0.4,
        "assistant": 0.3,
        "tool": 0.2,
        "user": 0.1
    })


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
        env_nested_delimiter="__"  # Support SEMANTIC__ENABLED=true syntax
    )

    # Core Authentication
    middleware_api_key: str = "dev-key-12345"

    # LLM Provider API Keys
    openai_api_key: Optional[str] = None
    anthropic_api_key: Optional[str] = None

    # Dashboard Integration
    dashboard_base_url: Optional[str] = None
    dashboard_api_key: Optional[str] = None
    dashboard_enabled: bool = False
    mock_dashboard: bool = True

    # Infrastructure
    redis_url: str = "redis://localhost:6379"

    # Optimization Parameters
    max_input_tokens: int = 8000
    keep_last_n_turns: int = 4
    safety_margin_tokens: int = 300

    # Observability
    log_level: str = "INFO"

    # Nested configurations for new features
    semantic: SemanticConfig = Field(default_factory=SemanticConfig)
    compression: CompressionConfig = Field(default_factory=CompressionConfig)
    budget: BudgetConfig = Field(default_factory=BudgetConfig)

    # Legacy flat flags (for backward compatibility)
    # These will be removed in a future version
    enable_semantic_retrieval: Optional[bool] = None
    enable_toon_compression: Optional[bool] = None
    postgres_url: Optional[str] = None

    def model_post_init(self, __context):
        """Post-initialization to handle backward compatibility."""
        # If legacy flags are set, use them to override nested configs
        if self.enable_semantic_retrieval is not None:
            self.semantic.enabled = self.enable_semantic_retrieval

        if self.enable_toon_compression is not None:
            self.compression.enabled = self.enable_toon_compression

        if self.postgres_url is not None and self.semantic.postgres_url is None:
            self.semantic.postgres_url = self.postgres_url

    def get_dashboard_api_key(self) -> str:
        """Get dashboard API key, fallback to middleware key."""
        return self.dashboard_api_key or self.middleware_api_key


# Global settings instance
settings = Settings()
