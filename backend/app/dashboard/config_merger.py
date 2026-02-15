"""Configuration merging logic."""

from typing import Dict, Any, Optional
import logging

logger = logging.getLogger(__name__)


def merge_config(
    base_config: Dict[str, Any],
    dashboard_config: Optional[Dict[str, Any]],
    request_overrides: Optional[Dict[str, Any]]
) -> Dict[str, Any]:
    """
    Merge configurations with priority: base < dashboard < request.

    Args:
        base_config: Base configuration from environment
        dashboard_config: Configuration from dashboard API (can be None)
        request_overrides: Request-specific overrides (can be None)

    Returns:
        Merged configuration dict
    """
    # Start with base
    merged = base_config.copy()

    # Apply dashboard config
    if dashboard_config:
        logger.debug("Applying dashboard config")
        for key, value in dashboard_config.items():
            if value is not None:  # Don't override with None values
                merged[key] = value

    # Apply request overrides (highest priority)
    if request_overrides:
        logger.debug("Applying request overrides")
        for key, value in request_overrides.items():
            if value is not None:
                merged[key] = value

    return merged


def map_dashboard_config_to_optimizer(dashboard_config: Dict[str, Any]) -> Dict[str, Any]:
    """
    Map dashboard config fields to optimizer config fields.

    Dashboard uses different naming (e.g., maxHistoryMessages)
    vs optimizer internal naming (e.g., keep_last_n_turns).

    Args:
        dashboard_config: Config from dashboard API

    Returns:
        Mapped config dict
    """
    mapped = {}

    # Map dashboard fields to optimizer fields
    field_mapping = {
        "maxHistoryMessages": "keep_last_n_turns",
        "maxTokensPerCall": "max_input_tokens",
        "maxInputTokens": "max_input_tokens",
        "includeSystemMessages": "include_system_messages",
        "aggressiveness": "aggressiveness",
        "preserveCodeBlocks": "preserve_code_blocks",
        "preserveFormatting": "preserve_formatting",
        "targetCostReduction": "target_cost_reduction"
    }

    for dashboard_key, optimizer_key in field_mapping.items():
        if dashboard_key in dashboard_config:
            value = dashboard_config[dashboard_key]

            # Special handling for aggressiveness
            if dashboard_key == "aggressiveness":
                # Map to compression ratio
                aggressiveness_map = {
                    "low": 0.3,
                    "medium": 0.5,
                    "high": 0.7
                }
                mapped["compression_target"] = aggressiveness_map.get(value, 0.5)
            else:
                mapped[optimizer_key] = value

    return mapped
