"""Canonicalization - convert inputs to Block IR."""

from typing import List, Dict, Any, Optional
from app.core.blocks import Block, BlockType
from app.core.utils import count_tokens


def messages_to_blocks(messages: List[Dict[str, str]], model: str = "gpt-4") -> List[Block]:
    """
    Convert message list to Block IR.

    Args:
        messages: List of message dicts with 'role' and 'content'
        model: Model name for token counting

    Returns:
        List of Block objects
    """
    blocks = []

    for i, msg in enumerate(messages):
        role = msg.get("role", "user")
        content = msg.get("content", "")

        # Map roles to block types
        if role == "system":
            block_type = BlockType.SYSTEM
            must_keep = True  # System messages are always kept
            priority = 1.0
        elif role == "user":
            block_type = BlockType.USER
            # Keep the latest user message
            must_keep = (i == len(messages) - 1 and role == "user")
            priority = 0.9 if must_keep else 0.7
        elif role == "assistant":
            block_type = BlockType.ASSISTANT
            must_keep = False
            priority = 0.5
        else:
            block_type = BlockType.ASSISTANT
            must_keep = False
            priority = 0.3

        # Count tokens
        tokens = count_tokens(content, model)

        # Create block
        block = Block.create(
            block_type=block_type,
            content=content,
            tokens=tokens,
            must_keep=must_keep,
            priority=priority,
            source="message",
            index=i
        )

        blocks.append(block)

    return blocks


def tools_to_blocks(tools: Optional[Dict[str, Any]], model: str = "gpt-4") -> List[Block]:
    """
    Convert tool schemas to blocks.

    Args:
        tools: Tool schema dictionary
        model: Model name for token counting

    Returns:
        List of Block objects
    """
    if not tools:
        return []

    blocks = []

    # Simple serialization of tool schema
    content = str(tools)
    tokens = count_tokens(content, model)

    block = Block.create(
        block_type=BlockType.TOOL,
        content=content,
        tokens=tokens,
        must_keep=True,  # Tool schemas are important
        priority=0.8,
        source="tool_schema"
    )

    blocks.append(block)

    return blocks


def rag_context_to_blocks(rag_context: Optional[List[Dict[str, Any]]], model: str = "gpt-4") -> List[Block]:
    """
    Convert RAG documents to blocks.

    Args:
        rag_context: List of RAG documents
        model: Model name for token counting

    Returns:
        List of Block objects
    """
    if not rag_context:
        return []

    blocks = []

    for i, doc in enumerate(rag_context):
        # Accept common RAG doc shapes:
        # - {"text": "..."} (legacy)
        # - {"content": "...", "metadata": {...}} (used by test_e2e.py)
        # - {"page_content": "..."} (langchain-ish)
        metadata = doc.get("metadata") or {}
        content = doc.get("text") or doc.get("content") or doc.get("page_content") or ""
        doc_id = doc.get("id") or metadata.get("id") or f"doc-{i}"
        source = doc.get("source") or metadata.get("source") or metadata.get("type") or "rag"

        # If we can't find any content, skip to avoid wasting tokens on empty blocks.
        if not str(content).strip():
            continue

        tokens = count_tokens(content, model)

        block = Block.create(
            block_type=BlockType.DOC,
            content=content,
            tokens=tokens,
            must_keep=False,  # RAG docs can be dropped
            priority=0.6,
            source=source,
            doc_id=doc_id
        )

        blocks.append(block)

    return blocks


def tool_outputs_to_blocks(tool_outputs: Optional[List[Dict[str, Any]]], model: str = "gpt-4") -> List[Block]:
    """
    Convert tool execution outputs to blocks.

    Args:
        tool_outputs: List of tool outputs
        model: Model name for token counting

    Returns:
        List of Block objects
    """
    if not tool_outputs:
        return []

    blocks = []

    for i, output in enumerate(tool_outputs):
        tool_name = output.get("tool", f"tool-{i}")
        content = output.get("text", "")

        tokens = count_tokens(content, model)

        block = Block.create(
            block_type=BlockType.TOOL,
            content=content,
            tokens=tokens,
            must_keep=False,  # Tool outputs can be compressed
            priority=0.7,
            source="tool_output",
            tool_name=tool_name
        )

        blocks.append(block)

    return blocks


def canonicalize(
    messages: List[Dict[str, str]],
    tools: Optional[Dict[str, Any]] = None,
    rag_context: Optional[List[Dict[str, Any]]] = None,
    tool_outputs: Optional[List[Dict[str, Any]]] = None,
    model: str = "gpt-4"
) -> List[Block]:
    """
    Convert all inputs to unified Block IR.

    Args:
        messages: Conversation messages
        tools: Tool schemas
        rag_context: RAG documents
        tool_outputs: Tool execution outputs
        model: Model name for token counting

    Returns:
        List of Block objects
    """
    blocks = []

    # Convert each input type
    blocks.extend(messages_to_blocks(messages, model))
    blocks.extend(tools_to_blocks(tools, model))
    blocks.extend(rag_context_to_blocks(rag_context, model))
    blocks.extend(tool_outputs_to_blocks(tool_outputs, model))

    return blocks


def blocks_to_messages(blocks: List[Block]) -> List[Dict[str, str]]:
    """
    Convert blocks back to message format.

    Args:
        blocks: List of Block objects

    Returns:
        List of message dicts
    """
    messages = []

    for block in blocks:
        # Only convert message blocks (not tools, docs, etc.)
        if block.type in [BlockType.SYSTEM, BlockType.USER, BlockType.ASSISTANT]:
            messages.append({
                "role": block.type.value,
                "content": block.content
            })

    return messages
