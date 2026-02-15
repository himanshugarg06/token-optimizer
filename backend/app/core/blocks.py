"""Block Internal Representation (IR) for prompt optimization."""

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Optional, Dict, Any
import uuid


class BlockType(str, Enum):
    """Types of blocks in the prompt."""
    SYSTEM = "system"
    USER = "user"
    ASSISTANT = "assistant"
    TOOL = "tool"
    DOC = "doc"
    CONSTRAINT = "constraint"


@dataclass
class Block:
    """
    Internal representation of a prompt block.

    A Block is the atomic unit of optimization - can be kept, dropped, or compressed independently.
    """

    id: str
    type: BlockType
    content: str
    tokens: int
    must_keep: bool = False
    priority: float = 0.5
    timestamp: Optional[datetime] = None
    metadata: Dict[str, Any] = field(default_factory=dict)
    compressed: bool = False
    original_content: Optional[str] = None  # Store original before compression

    @staticmethod
    def create(
        block_type: BlockType,
        content: str,
        tokens: int,
        must_keep: bool = False,
        priority: float = 0.5,
        **metadata
    ) -> "Block":
        """
        Factory method to create a new Block.

        Args:
            block_type: Type of the block
            content: Text content
            tokens: Token count
            must_keep: Whether this block must never be dropped
            priority: Priority score (0.0-1.0)
            **metadata: Additional metadata

        Returns:
            New Block instance
        """
        return Block(
            id=str(uuid.uuid4()),
            type=block_type,
            content=content,
            tokens=tokens,
            must_keep=must_keep,
            priority=priority,
            timestamp=datetime.utcnow(),
            metadata=metadata
        )

    def to_dict(self) -> dict:
        """Convert block to dictionary representation."""
        return {
            "id": self.id,
            "type": self.type.value,
            "content": self.content,
            "tokens": self.tokens,
            "must_keep": self.must_keep,
            "priority": self.priority,
            "timestamp": self.timestamp.isoformat() if self.timestamp else None,
            "metadata": self.metadata,
            "compressed": self.compressed
        }

    def get_fingerprint(self) -> str:
        """
        Get content fingerprint for deduplication.

        Returns:
            Normalized content (lowercased, stripped)
        """
        return self.content.strip().lower()
