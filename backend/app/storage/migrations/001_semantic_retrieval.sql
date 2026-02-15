-- Migration: 001_semantic_retrieval
-- Description: Set up pgvector tables for semantic retrieval
-- Created: 2026-02-15

-- Enable required extensions
CREATE EXTENSION IF NOT EXISTS vector;
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";

-- Blocks table: Store content with metadata
CREATE TABLE IF NOT EXISTS blocks (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    api_key TEXT NOT NULL,
    content_hash TEXT NOT NULL,
    content TEXT NOT NULL,
    block_type TEXT NOT NULL,
    tokens INTEGER NOT NULL,
    must_keep BOOLEAN DEFAULT FALSE,
    priority FLOAT DEFAULT 0.5,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    metadata JSONB DEFAULT '{}'::jsonb,

    CONSTRAINT valid_block_type CHECK (block_type IN (
        'system', 'user', 'assistant', 'tool', 'doc', 'constraint'
    )),
    CONSTRAINT valid_priority CHECK (priority BETWEEN 0 AND 1),
    CONSTRAINT valid_tokens CHECK (tokens >= 0)
);

-- Embeddings table: 768 dimensions for BAAI/bge-base-en-v1.5
CREATE TABLE IF NOT EXISTS embeddings (
    block_id UUID PRIMARY KEY REFERENCES blocks(id) ON DELETE CASCADE,
    embedding vector(768) NOT NULL,
    model_name TEXT NOT NULL DEFAULT 'BAAI/bge-base-en-v1.5',
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- Compression history: Track compression results
CREATE TABLE IF NOT EXISTS compression_history (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    block_id UUID REFERENCES blocks(id) ON DELETE CASCADE,
    original_tokens INTEGER NOT NULL,
    compressed_tokens INTEGER NOT NULL,
    compression_ratio FLOAT NOT NULL,
    faithfulness_score FLOAT,
    model_name TEXT NOT NULL,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),

    CONSTRAINT valid_compression_ratio CHECK (compression_ratio BETWEEN 0 AND 1),
    CONSTRAINT valid_faithfulness CHECK (faithfulness_score IS NULL OR faithfulness_score BETWEEN 0 AND 1)
);

-- Request traces: Store optimization results for analytics
CREATE TABLE IF NOT EXISTS request_traces (
    trace_id UUID PRIMARY KEY,
    api_key TEXT NOT NULL,
    tokens_before INTEGER NOT NULL,
    tokens_after INTEGER NOT NULL,
    tokens_saved INTEGER NOT NULL,
    compression_ratio FLOAT NOT NULL,
    route TEXT NOT NULL,
    cache_hit BOOLEAN NOT NULL,
    semantic_enabled BOOLEAN NOT NULL,
    compression_enabled BOOLEAN NOT NULL,
    fallback_used BOOLEAN NOT NULL,
    latency_ms INTEGER NOT NULL,
    selected_blocks JSONB NOT NULL,
    dropped_blocks JSONB NOT NULL,
    stage_timings JSONB NOT NULL,
    faithfulness_score FLOAT,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),

    CONSTRAINT valid_tokens CHECK (tokens_before >= 0 AND tokens_after >= 0),
    CONSTRAINT valid_compression CHECK (compression_ratio BETWEEN 0 AND 1)
);

-- Indexes for performance

-- Blocks table indexes
CREATE INDEX IF NOT EXISTS idx_blocks_api_key ON blocks(api_key);
CREATE INDEX IF NOT EXISTS idx_blocks_created_at ON blocks(created_at DESC);
CREATE INDEX IF NOT EXISTS idx_blocks_content_hash ON blocks(content_hash);
CREATE INDEX IF NOT EXISTS idx_blocks_type ON blocks(block_type);
CREATE INDEX IF NOT EXISTS idx_blocks_api_key_type ON blocks(api_key, block_type);

-- Vector similarity index (IVFFlat for cosine similarity)
-- Lists parameter set to 100 (good starting point, can be adjusted based on data size)
CREATE INDEX IF NOT EXISTS idx_embeddings_vector ON embeddings
USING ivfflat (embedding vector_cosine_ops) WITH (lists = 100);

-- Compression history indexes
CREATE INDEX IF NOT EXISTS idx_compression_history_block_id ON compression_history(block_id);
CREATE INDEX IF NOT EXISTS idx_compression_history_created_at ON compression_history(created_at DESC);

-- Request traces indexes
CREATE INDEX IF NOT EXISTS idx_request_traces_api_key ON request_traces(api_key, created_at DESC);
CREATE INDEX IF NOT EXISTS idx_request_traces_created_at ON request_traces(created_at DESC);
CREATE INDEX IF NOT EXISTS idx_request_traces_route ON request_traces(route);

-- Create materialized view for block statistics (optional, for analytics)
CREATE MATERIALIZED VIEW IF NOT EXISTS block_statistics AS
SELECT
    api_key,
    block_type,
    COUNT(*) as total_blocks,
    AVG(tokens) as avg_tokens,
    SUM(tokens) as total_tokens,
    MAX(created_at) as last_updated
FROM blocks
GROUP BY api_key, block_type;

CREATE INDEX IF NOT EXISTS idx_block_stats_api_key ON block_statistics(api_key);

-- Function to refresh materialized view
CREATE OR REPLACE FUNCTION refresh_block_statistics()
RETURNS void AS $$
BEGIN
    REFRESH MATERIALIZED VIEW CONCURRENTLY block_statistics;
END;
$$ LANGUAGE plpgsql;

-- Comments for documentation
COMMENT ON TABLE blocks IS 'Stores content blocks with metadata for semantic retrieval';
COMMENT ON TABLE embeddings IS 'Stores 768-dimensional embeddings for BAAI/bge-base-en-v1.5 model';
COMMENT ON TABLE compression_history IS 'Tracks compression results and faithfulness scores';
COMMENT ON TABLE request_traces IS 'Stores optimization request traces for analytics';
COMMENT ON COLUMN blocks.content_hash IS 'SHA256 hash of content for deduplication';
COMMENT ON COLUMN embeddings.embedding IS 'L2-normalized vector embedding (768 dimensions)';
COMMENT ON INDEX idx_embeddings_vector IS 'IVFFlat index for fast cosine similarity search';
