"""Deterministic heuristics for prompt optimization."""

from typing import List, Optional
import re
import hashlib
import json
from collections import defaultdict
from app.core.blocks import Block, BlockType


def remove_junk(blocks: List[Block]) -> List[Block]:
    """
    Remove empty/whitespace blocks.

    Args:
        blocks: Input blocks

    Returns:
        Filtered blocks
    """
    cleaned = []

    for block in blocks:
        # Skip if must_keep
        if block.must_keep:
            cleaned.append(block)
            continue

        # Check if empty or whitespace-only
        content = block.content.strip()
        if not content:
            continue

        # Check common junk patterns
        junk_patterns = [
            r"^(Sure|Of course|I can help|Let me help).*$",
            r"^(Thank you|Thanks).*$",
            r"^\s*$"
        ]

        is_junk = False
        for pattern in junk_patterns:
            if re.match(pattern, content, re.IGNORECASE):
                is_junk = True
                break

        if not is_junk:
            cleaned.append(block)

    return cleaned


def deduplicate(blocks: List[Block]) -> List[Block]:
    """
    Remove duplicate blocks, keeping most recent.

    Args:
        blocks: Input blocks

    Returns:
        Deduplicated blocks
    """
    # Group by fingerprint
    fingerprint_map = defaultdict(list)

    for block in blocks:
        if block.must_keep:
            # Always keep must_keep blocks
            fingerprint_map[block.id].append(block)
        else:
            # Hash content for deduplication
            fingerprint = hashlib.sha256(
                block.get_fingerprint().encode()
            ).hexdigest()[:16]
            fingerprint_map[fingerprint].append(block)

    # Keep most recent from each group
    deduped = []
    for group in fingerprint_map.values():
        if len(group) == 1:
            deduped.append(group[0])
        else:
            # Sort by timestamp, keep latest
            sorted_group = sorted(
                group,
                key=lambda b: b.timestamp or 0,
                reverse=True
            )
            deduped.append(sorted_group[0])

    # Sort by original order (using metadata index if available)
    deduped.sort(key=lambda b: b.metadata.get("index", 0))

    return deduped


def keep_last_n_turns(blocks: List[Block], n: int = 4) -> List[Block]:
    """
    Mark last N conversation turns as must_keep.

    Args:
        blocks: Input blocks
        n: Number of turns to keep

    Returns:
        Updated blocks
    """
    # Find user+assistant pairs (conversation turns)
    turns = []
    current_turn = []

    for block in blocks:
        if block.type in [BlockType.USER, BlockType.ASSISTANT]:
            current_turn.append(block)

            # End of turn when we see a user message after assistant
            if block.type == BlockType.USER and len(current_turn) > 1:
                turns.append(current_turn[:-1])
                current_turn = [block]

    # Add last turn
    if current_turn:
        turns.append(current_turn)

    # Mark last N turns as must_keep
    last_n_turns = turns[-n:] if len(turns) > n else turns

    must_keep_ids = set()
    for turn in last_n_turns:
        for block in turn:
            must_keep_ids.add(block.id)

    # Update blocks
    for block in blocks:
        if block.id in must_keep_ids:
            block.must_keep = True
            block.priority = max(block.priority, 0.9)

    return blocks


def extract_constraints(blocks: List[Block]) -> Optional[Block]:
    """
    Extract critical directives into dedicated constraint block.

    Args:
        blocks: Input blocks

    Returns:
        Constraint block if found, else None
    """
    # Extract "hard constraints" into a dedicated block, but be conservative:
    # - require ALL-CAPS keywords to avoid pulling in prose ("Must-keep", etc.)
    # - cap sentence length to avoid duplicating huge blocks
    constraint_keywords = [
        "MUST NOT",
        "MUST",
        "ALWAYS",
        "NEVER",
        "REQUIRED",
        "FORBIDDEN",
        "ONLY",
        "FORMAT",
        "JSON",
        "OUTPUT",
        "DEADLINE",
    ]

    keyword_patterns = [
        re.compile(rf"\b{re.escape(kw)}\b") for kw in constraint_keywords
    ]

    # Collect sentences with constraints
    constraint_sentences = []

    for block in blocks:
        if block.type not in [BlockType.SYSTEM, BlockType.USER]:
            continue

        content = block.content
        sentences = re.split(r'[.!?]\s+', content)

        for sentence in sentences:
            s = sentence.strip()
            # Skip extremely long sentences; these are usually not actual "constraints".
            if len(s) > 400:
                continue
            # Require ALL-CAPS matches.
            if any(p.search(s) for p in keyword_patterns):
                constraint_sentences.append(s)

    if not constraint_sentences:
        return None

    # De-duplicate while keeping order.
    seen = set()
    deduped = []
    for s in constraint_sentences:
        if s in seen:
            continue
        seen.add(s)
        deduped.append(s)

    constraint_content = "\n".join(deduped)

    # Use utility import to avoid circular dependency
    from app.core.utils import count_tokens

    # Hard cap to avoid duplicating a massive section into an extra must_keep block.
    constraint_tokens = count_tokens(constraint_content)
    if constraint_tokens > 200:
        return None

    constraint_block = Block.create(
        block_type=BlockType.CONSTRAINT,
        content=constraint_content,
        tokens=constraint_tokens,
        must_keep=True,
        priority=1.0,
        source="extracted_constraints"
    )

    return constraint_block


def minimize_tool_schemas(blocks: List[Block], allowlist: List[str] = None) -> List[Block]:
    """
    Minimize tool schema verbosity by keeping only essential fields.

    Keeps only: name, parameters, required
    Removes: descriptions, examples, enum descriptions

    Achieves ~60% token reduction for tool blocks.

    Args:
        blocks: Input blocks
        allowlist: Tool names to keep (default ["*"] = all)

    Returns:
        Blocks with minimized tool schemas
    """
    if allowlist is None:
        allowlist = ["*"]

    from app.core.utils import count_tokens

    result = []
    for block in blocks:
        if block.type != BlockType.TOOL:
            result.append(block)
            continue

        try:
            schema = json.loads(block.content)

            # Apply allowlist filter
            if "*" not in allowlist:
                tool_name = schema.get("name", "")
                if tool_name not in allowlist:
                    continue  # Skip this tool

            # Keep only essential fields
            minimized = {}

            if "name" in schema:
                minimized["name"] = schema["name"]

            if "parameters" in schema:
                minimized["parameters"] = _minimize_parameters(schema["parameters"])

            if "required" in schema:
                minimized["required"] = schema["required"]

            # Compact JSON (no whitespace)
            minimized_content = json.dumps(minimized, separators=(',', ':'))

            # Create new block
            minimized_block = Block.create(
                block_type=block.type,
                content=minimized_content,
                tokens=count_tokens(minimized_content),
                must_keep=block.must_keep,
                priority=block.priority,
                source=block.metadata.get("source", "tool_schema"),
                metadata={**block.metadata, "minimized": True}
            )
            result.append(minimized_block)

        except (json.JSONDecodeError, KeyError):
            # If not valid JSON, keep original
            result.append(block)

    return result


def _minimize_parameters(params: dict) -> dict:
    """Remove descriptions and examples from parameter schema."""
    if not isinstance(params, dict):
        return params

    minimized = {}

    if "type" in params:
        minimized["type"] = params["type"]

    if "properties" in params:
        minimized_props = {}
        for name, spec in params["properties"].items():
            prop = {"type": spec.get("type")}
            # Keep enum values but not descriptions
            if "enum" in spec:
                prop["enum"] = spec["enum"]
            minimized_props[name] = prop
        minimized["properties"] = minimized_props

    if "required" in params:
        minimized["required"] = params["required"]

    return minimized


def trim_logs(content: str, error_window: int = 30, tail_lines: int = 80) -> str:
    """
    Keep only relevant log lines around errors and tail.

    Strategy:
    - Find lines with ERROR/Exception/Traceback keywords
    - Keep ±error_window lines around errors
    - Always keep last tail_lines lines

    Achieves ~70-80% reduction for log blocks.

    Args:
        content: Log content
        error_window: Lines to keep around errors
        tail_lines: Lines to always keep at end

    Returns:
        Trimmed log content
    """
    error_keywords = [
        "ERROR", "CRITICAL", "Exception", "Traceback",
        "Failed", "failed", "FATAL", "panic", "Panic"
    ]

    lines = content.split("\n")
    total_lines = len(lines)

    if total_lines <= tail_lines:
        return content  # Already small

    # Find error line indices
    error_indices = set()
    for i, line in enumerate(lines):
        if any(keyword in line for keyword in error_keywords):
            error_indices.add(i)

    # Expand to include context window
    keep_indices = set()
    for error_idx in error_indices:
        start = max(0, error_idx - error_window)
        end = min(total_lines, error_idx + error_window + 1)
        keep_indices.update(range(start, end))

    # Always keep tail lines
    tail_start = max(0, total_lines - tail_lines)
    keep_indices.update(range(tail_start, total_lines))

    # Reconstruct log with ellipsis for gaps
    kept_lines = []
    last_idx = -2

    for idx in sorted(keep_indices):
        if idx > last_idx + 1:
            kept_lines.append("... [logs truncated] ...")
        kept_lines.append(lines[idx])
        last_idx = idx

    return "\n".join(kept_lines)


def compress_json_toon(content: str, max_items: int = 200) -> str:
    """
    Apply TOON (Token-Oriented Object Notation) to JSON arrays.

    Before: [{"id":"1","name":"Alice"},{"id":"2","name":"Bob"}]
    After: Schema#id,name[1,Alice|2,Bob]

    Achieves ~60% token reduction for JSON arrays.

    Args:
        content: JSON content
        max_items: Maximum items to process

    Returns:
        TOON-compressed content or original if not applicable
    """
    try:
        data = json.loads(content)

        if not isinstance(data, list) or len(data) == 0:
            return content  # Not a list

        # Truncate if too large
        if len(data) > max_items:
            data = data[:max_items]

        # Check if all items are dicts
        if not all(isinstance(item, dict) for item in data):
            return content

        # Extract schema from first item
        if not data[0]:
            return content

        keys = list(data[0].keys())
        if not keys:
            return content

        schema = ",".join(keys)

        # Convert to TOON format
        rows = []
        for item in data:
            values = [str(item.get(k, "")) for k in keys]
            rows.append(",".join(values))

        toon = f"Schema#{schema}[" + "|".join(rows) + "]"

        # Only use if actually shorter
        if len(toon) < len(content):
            return toon
        return content

    except (json.JSONDecodeError, KeyError, TypeError):
        return content


def apply_heuristics(blocks: List[Block], config: dict) -> List[Block]:
    """
    Apply all heuristic transformations.

    Args:
        blocks: Input blocks
        config: Configuration dict

    Returns:
        Optimized blocks
    """
    from app.core.utils import count_tokens

    # Stage 1: Remove junk
    blocks = remove_junk(blocks)

    # Stage 2: Deduplicate
    blocks = deduplicate(blocks)

    # Stage 3: Keep last N turns
    keep_n = config.get("keep_last_n_turns", 4)
    blocks = keep_last_n_turns(blocks, n=keep_n)

    # Stage 4: Extract constraints (only keep if it reduces tokens)
    constraint_block = extract_constraints(blocks)
    if constraint_block:
        tokens_before_constraints = count_tokens(blocks)
        candidate = [constraint_block] + blocks
        if count_tokens(candidate) <= tokens_before_constraints:
            blocks = candidate

    # Stage 5: Minimize tool schemas (if enabled)
    if config.get("enable_tool_minimization", True):
        tool_allowlist = config.get("tool_allowlist", ["*"])
        blocks = minimize_tool_schemas(blocks, allowlist=tool_allowlist)

    # Stage 6: Trim logs in long assistant blocks
    for i, block in enumerate(blocks):
        if block.type == BlockType.ASSISTANT and block.tokens > 500:
            # Check if it looks like logs (has multiple lines with log patterns)
            if "\n" in block.content and any(
                keyword in block.content
                for keyword in ["INFO", "DEBUG", "ERROR", "WARNING"]
            ):
                trimmed_content = trim_logs(block.content)
                if len(trimmed_content) < len(block.content):
                    blocks[i] = Block.create(
                        block_type=block.type,
                        content=trimmed_content,
                        tokens=count_tokens(trimmed_content),
                        must_keep=block.must_keep,
                        priority=block.priority,
                        source=block.metadata.get("source", "assistant"),
                        metadata={**block.metadata, "log_trimmed": True}
                    )

    # Stage 7: Apply TOON compression to doc blocks with JSON
    for i, block in enumerate(blocks):
        if block.type == BlockType.DOC:
            # Try TOON compression
            compressed = compress_json_toon(block.content)
            if compressed != block.content:
                blocks[i] = Block.create(
                    block_type=block.type,
                    content=compressed,
                    tokens=count_tokens(compressed),
                    must_keep=block.must_keep,
                    priority=block.priority,
                    source=block.metadata.get("source", "doc"),
                    metadata={**block.metadata, "toon_compressed": True}
                )

    return blocks
