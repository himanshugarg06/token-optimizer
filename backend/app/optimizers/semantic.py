"""Semantic retrieval with embeddings and vector similarity."""

import logging
import hashlib
import re
from typing import List, Optional, Tuple
from datetime import datetime, timedelta
from contextlib import contextmanager

import numpy as np

from app.core.blocks import Block, BlockType
from app.settings import SemanticConfig

logger = logging.getLogger(__name__)


class EmbeddingService:
    """
    Manages embedding model lifecycle and batch embedding.
    Implements lazy loading and graceful degradation.
    """

    def __init__(self, config: SemanticConfig):
        self.config = config
        self.model = None
        self.available = False
        self._load_model()

    def _load_model(self):
        """Lazy load embedding model with error handling"""
        try:
            logger.info(f"Loading embedding model: {self.config.embedding_model}")

            from sentence_transformers import SentenceTransformer

            self.model = SentenceTransformer(
                self.config.embedding_model,
                device=self.config.embedding_device
            )

            # Warmup with dummy embedding
            _ = self.model.encode(["test"], show_progress_bar=False)

            self.available = True
            logger.info(f"Embedding model loaded successfully")

        except Exception as e:
            logger.error(f"Failed to load embedding model: {e}")
            logger.warning("Semantic retrieval will be disabled")
            self.available = False

    def embed(self, texts: List[str], batch_size: int = None) -> np.ndarray:
        """
        Batch embed texts with normalization.

        Args:
            texts: List of texts to embed
            batch_size: Batch size for processing

        Returns:
            np.ndarray: Shape (n, embedding_dim), L2-normalized
        """
        if not self.available:
            raise RuntimeError("Embedding model not available")

        if batch_size is None:
            batch_size = self.config.batch_size

        embeddings = self.model.encode(
            texts,
            batch_size=batch_size,
            show_progress_bar=False,
            normalize_embeddings=True,  # L2 normalize for cosine similarity
            convert_to_numpy=True
        )

        return embeddings

    def embed_single(self, text: str) -> np.ndarray:
        """Convenience method for single text embedding"""
        return self.embed([text])[0]

    def cosine_similarity(
        self,
        embedding1: np.ndarray,
        embedding2: np.ndarray
    ) -> float:
        """Compute cosine similarity between two embeddings"""
        # Embeddings already normalized, so dot product = cosine similarity
        return float(np.dot(embedding1, embedding2))

    def batch_similarity(
        self,
        query_embedding: np.ndarray,
        candidate_embeddings: np.ndarray
    ) -> np.ndarray:
        """Compute similarity between query and multiple candidates"""
        # Shape: (n_candidates,)
        return np.dot(candidate_embeddings, query_embedding)


class VectorStore:
    """
    Manages block storage and similarity search with pgvector.
    Implements connection pooling and batch operations.
    """

    def __init__(self, postgres_url: str):
        self.postgres_url = postgres_url
        self.pool = self._create_pool()

    def _create_pool(self):
        """Create connection pool"""
        try:
            import psycopg2
            from psycopg2 import pool

            return pool.ThreadedConnectionPool(
                minconn=1,
                maxconn=10,
                dsn=self.postgres_url
            )
        except Exception as e:
            logger.error(f"Failed to create connection pool: {e}")
            return None

    @property
    def available(self) -> bool:
        """Check if vector store is available"""
        return self.pool is not None

    def health_check(self) -> bool:
        """
        Simple health check - tries to execute a basic query.
        Returns True if connection is healthy.
        """
        if not self.available:
            return False

        try:
            with self._get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("SELECT 1;")
                cursor.fetchone()
                cursor.close()
                return True
        except Exception as e:
            logger.error(f"Health check failed: {e}")
            return False

    @contextmanager
    def _get_connection(self):
        """Context manager for connection handling"""
        if not self.pool:
            raise RuntimeError("Connection pool not available")

        conn = self.pool.getconn()
        try:
            yield conn
            conn.commit()
        except Exception:
            conn.rollback()
            raise
        finally:
            self.pool.putconn(conn)

    def store_block(
        self,
        block: Block,
        embedding: np.ndarray,
        api_key: str,
        model_name: str
    ) -> str:
        """
        Store block and its embedding.

        Args:
            block: Block to store
            embedding: Vector embedding
            api_key: API key for isolation
            model_name: Embedding model name

        Returns:
            block_id (str)
        """
        content_hash = hashlib.sha256(block.content.encode()).hexdigest()

        with self._get_connection() as conn:
            cursor = conn.cursor()

            # Check if block already exists
            cursor.execute(
                "SELECT id FROM blocks WHERE content_hash = %s AND api_key = %s",
                (content_hash, api_key)
            )
            existing = cursor.fetchone()

            if existing:
                block_id = existing[0]
                # Update embedding if needed
                cursor.execute(
                    """
                    INSERT INTO embeddings (block_id, embedding, model_name)
                    VALUES (%s, %s, %s)
                    ON CONFLICT (block_id) DO UPDATE
                    SET embedding = EXCLUDED.embedding,
                        model_name = EXCLUDED.model_name,
                        created_at = NOW()
                    """,
                    (block_id, embedding.tolist(), model_name)
                )
                logger.debug(f"Updated existing block {block_id}")
                cursor.close()
                return str(block_id)

            # Insert new block
            cursor.execute(
                """
                INSERT INTO blocks (
                    api_key, content_hash, content, block_type,
                    tokens, must_keep, priority, metadata
                )
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
                RETURNING id
                """,
                (
                    api_key,
                    content_hash,
                    block.content,
                    block.type.value,
                    block.tokens,
                    block.must_keep,
                    block.priority,
                    None  # metadata as JSON
                )
            )
            block_id = cursor.fetchone()[0]

            # Insert embedding
            cursor.execute(
                """
                INSERT INTO embeddings (block_id, embedding, model_name)
                VALUES (%s, %s, %s)
                """,
                (block_id, embedding.tolist(), model_name)
            )

            cursor.close()
            logger.debug(f"Stored new block {block_id}")
            return str(block_id)

    def store_blocks_batch(
        self,
        blocks: List[Block],
        embeddings: np.ndarray,
        api_key: str,
        model_name: str
    ) -> List[str]:
        """Batch store blocks and embeddings"""
        block_ids = []

        for block, embedding in zip(blocks, embeddings):
            try:
                block_id = self.store_block(block, embedding, api_key, model_name)
                block_ids.append(block_id)
            except Exception as e:
                logger.error(f"Failed to store block: {e}")
                continue

        return block_ids

    def similarity_search(
        self,
        query_embedding: np.ndarray,
        api_key: str,
        top_k: int = 50,
        block_types: List[str] = None,
        similarity_threshold: float = 0.3
    ) -> List[Tuple[Block, float]]:
        """
        Retrieve similar blocks using pgvector cosine similarity.

        Args:
            query_embedding: Query vector
            api_key: API key for isolation
            top_k: Number of results
            block_types: Filter by block types
            similarity_threshold: Minimum similarity

        Returns:
            List of (Block, similarity_score) tuples
        """
        with self._get_connection() as conn:
            cursor = conn.cursor()

            type_filter = ""
            params = [query_embedding.tolist(), api_key]

            if block_types:
                type_filter = "AND b.block_type = ANY(%s)"
                params.append(block_types)

            # Add query embedding again for distance calculation
            params.extend([query_embedding.tolist(), query_embedding.tolist(), top_k])

            query = f"""
                SELECT
                    b.id, b.content, b.block_type, b.tokens,
                    b.must_keep, b.priority, b.created_at, b.metadata,
                    1 - (e.embedding <=> %s::vector) as similarity
                FROM blocks b
                JOIN embeddings e ON b.id = e.block_id
                WHERE b.api_key = %s
                {type_filter}
                AND 1 - (e.embedding <=> %s::vector) > {similarity_threshold}
                ORDER BY e.embedding <=> %s::vector
                LIMIT %s
            """

            cursor.execute(query, params)

            results = []
            for row in cursor.fetchall():
                block = Block.create(
                    block_type=BlockType(row[2]),
                    content=row[1],
                    tokens=row[3],
                    must_keep=row[4],
                    priority=row[5],
                    source="vector_store"
                )
                block.id = str(row[0])
                block.timestamp = row[6]
                similarity = row[8]
                results.append((block, similarity))

            cursor.close()
            return results

    def delete_old_blocks(
        self,
        api_key: str,
        days: int = 30
    ) -> int:
        """Clean up old blocks"""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                """
                DELETE FROM blocks
                WHERE api_key = %s
                AND created_at < NOW() - INTERVAL '%s days'
                """,
                (api_key, days)
            )
            deleted = cursor.rowcount
            cursor.close()
            return deleted


class UtilityScorer:
    """
    Multi-factor utility scoring for block selection.
    Combines semantic similarity with heuristic signals.
    """

    # Constraint keywords with weights
    CONSTRAINT_KEYWORDS = {
        "MUST": 1.0,
        "MUST NOT": 1.0,
        "ALWAYS": 0.9,
        "NEVER": 0.9,
        "REQUIRED": 0.8,
        "FORMAT": 0.7,
        "JSON": 0.6,
        "SCHEMA": 0.6,
        "DEADLINE": 0.8,
        "IMPORTANT": 0.7
    }

    # Source trust scores
    SOURCE_TRUST = {
        "system": 1.0,
        "developer": 1.0,
        "docs": 0.9,
        "user": 0.8,
        "inferred": 0.5
    }

    def __init__(self, config: SemanticConfig):
        self.config = config

    def compute_utility(
        self,
        block: Block,
        query_embedding: np.ndarray,
        block_embedding: np.ndarray,
        current_time: datetime = None
    ) -> float:
        """
        Compute multi-factor utility score (0.0 - 1.0).

        Factors:
        - Semantic similarity (40%)
        - Recency (20%)
        - Constraint keywords (15%)
        - Identifiers (10%)
        - Source trust (10%)
        - Entity preservation (5%)

        Args:
            block: Block to score
            query_embedding: Query vector
            block_embedding: Block vector
            current_time: Current time for recency

        Returns:
            Utility score (0.0-1.0)
        """
        if current_time is None:
            current_time = datetime.utcnow()

        # Factor 1: Semantic similarity (already normalized)
        similarity = float(np.dot(query_embedding, block_embedding))

        # Factor 2: Recency boost
        recency = self._recency_score(block.timestamp, current_time) if block.timestamp else 0.5

        # Factor 3: Constraint keywords
        constraint_score = self._constraint_score(block.content)

        # Factor 4: Identifier preservation
        identifier_score = self._identifier_score(block.content)

        # Factor 5: Source trust
        source = block.metadata.get("source", "inferred")
        trust_score = self.SOURCE_TRUST.get(source, 0.5)

        # Factor 6: Entity preservation
        entity_score = self._entity_score(block.content)

        # Weighted combination
        utility = (
            0.40 * similarity +
            0.20 * recency +
            0.15 * constraint_score +
            0.10 * identifier_score +
            0.10 * trust_score +
            0.05 * entity_score
        )

        return float(np.clip(utility, 0.0, 1.0))

    def _recency_score(
        self,
        timestamp: datetime,
        current_time: datetime
    ) -> float:
        """Exponential decay: score = e^(-days/30)"""
        age_days = (current_time - timestamp).total_seconds() / 86400
        return float(np.exp(-age_days / 30))

    def _constraint_score(self, content: str) -> float:
        """Count constraint keywords with weights"""
        score = 0.0
        content_upper = content.upper()

        for keyword, weight in self.CONSTRAINT_KEYWORDS.items():
            count = content_upper.count(keyword)
            score += count * weight

        # Normalize to 0-1 (saturate at 5 keywords)
        return min(score / 5.0, 1.0)

    def _identifier_score(self, content: str) -> float:
        """
        Detect identifiers: UUIDs, IDs, API keys, URLs, etc.
        Higher score = more identifiers
        """
        patterns = [
            r'\b[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}\b',  # UUID
            r'\bid[_-]?\d+\b',  # ID patterns
            r'\b[A-Z0-9]{20,}\b',  # API keys
            r'https?://[^\s]+',  # URLs
            r'\b[A-Z]{2,}_[A-Z_]+\b'  # Constants
        ]

        matches = sum(
            len(re.findall(pattern, content, re.IGNORECASE))
            for pattern in patterns
        )

        # Normalize (saturate at 10 identifiers)
        return min(matches / 10.0, 1.0)

    def _entity_score(self, content: str) -> float:
        """
        Simple entity detection: proper nouns, numbers, dates.
        More entities = higher score
        """
        # Count capitalized words (naive NER)
        proper_nouns = len(re.findall(r'\b[A-Z][a-z]+\b', content))

        # Count numbers
        numbers = len(re.findall(r'\b\d+\.?\d*\b', content))

        # Count dates (YYYY-MM-DD pattern)
        dates = len(re.findall(r'\d{4}-\d{2}-\d{2}', content))

        total_entities = proper_nouns + numbers + dates

        # Normalize (saturate at 20 entities)
        return min(total_entities / 20.0, 1.0)


def mmr_selection(
    candidates: List[Tuple[Block, float, np.ndarray]],
    query_embedding: np.ndarray,
    lambda_param: float = 0.7,
    top_k: int = 20
) -> List[Block]:
    """
    Maximal Marginal Relevance for diversity.

    MMR = λ * sim(q, d) - (1-λ) * max(sim(d, selected))

    Args:
        candidates: List of (block, similarity, embedding) tuples
        query_embedding: Query embedding
        lambda_param: Relevance vs diversity tradeoff (0.7 = 70% relevance)
        top_k: Number of blocks to select

    Returns:
        List of selected blocks with diversity
    """
    if not candidates:
        return []

    if len(candidates) <= top_k:
        return [block for block, _, _ in candidates]

    selected = []
    selected_embeddings = []
    remaining = candidates.copy()

    # Select first item (highest similarity)
    first = remaining.pop(0)
    selected.append(first[0])
    selected_embeddings.append(first[2])

    # Iteratively select remaining
    while len(selected) < top_k and remaining:
        mmr_scores = []

        for block, similarity, embedding in remaining:
            # Relevance term
            relevance = similarity

            # Redundancy term (max similarity to selected)
            if selected_embeddings:
                redundancy = max(
                    np.dot(embedding, sel_emb)
                    for sel_emb in selected_embeddings
                )
            else:
                redundancy = 0.0

            # MMR score
            mmr = lambda_param * relevance - (1 - lambda_param) * redundancy
            mmr_scores.append(mmr)

        # Select highest MMR
        best_idx = int(np.argmax(mmr_scores))
        best = remaining.pop(best_idx)
        selected.append(best[0])
        selected_embeddings.append(best[2])

    return selected
