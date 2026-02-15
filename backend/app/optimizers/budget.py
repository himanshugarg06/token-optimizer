"""Token budget allocation for block selection."""

import logging
from typing import List, Dict, Tuple

from app.core.blocks import Block
from app.settings import BudgetConfig

logger = logging.getLogger(__name__)


class BudgetAllocator:
    """
    Greedy knapsack algorithm for token budget allocation.
    Ensures must_keep blocks always included, then fills budget
    by utility/token ratio.
    """

    def __init__(self, config: BudgetConfig):
        self.config = config

    def select_blocks(
        self,
        blocks: List[Block],
        max_tokens: int,
        safety_margin: int = 300
    ) -> Tuple[List[Block], List[Block]]:
        """
        Select blocks within token budget.

        Args:
            blocks: Candidate blocks (must have utility scores in metadata)
            max_tokens: Maximum token budget
            safety_margin: Reserve tokens for safety

        Returns:
            (selected_blocks, dropped_blocks)
        """
        # Step 1: Separate must_keep blocks
        must_keep = [b for b in blocks if b.must_keep]
        optional = [b for b in blocks if not b.must_keep]

        must_keep_tokens = sum(b.tokens for b in must_keep)

        # Validate must_keep fits in budget
        if must_keep_tokens > max_tokens - safety_margin:
            logger.warning(
                f"Must-keep blocks ({must_keep_tokens} tokens) exceed budget "
                f"({max_tokens - safety_margin} tokens). Including anyway."
            )
            # Still include must_keep (override budget)
            return must_keep, optional

        # Step 2: Calculate available budget
        available_budget = max_tokens - safety_margin - must_keep_tokens

        logger.debug(
            f"Budget allocation: must_keep={must_keep_tokens}, "
            f"available={available_budget}, total={max_tokens}"
        )

        # Step 3: Calculate per-type budgets
        type_budgets = self._calculate_type_budgets(
            optional,
            available_budget
        )

        # Step 4: Greedy selection by utility/token ratio
        selected = must_keep.copy()
        dropped = []

        # Sort by utility/token ratio (descending)
        optional_sorted = sorted(
            optional,
            key=lambda b: self._get_utility_ratio(b),
            reverse=True
        )

        for block in optional_sorted:
            block_type = block.type.value
            type_budget = type_budgets.get(block_type, 0)

            if type_budget >= block.tokens:
                selected.append(block)
                type_budgets[block_type] -= block.tokens
                block.metadata["selection_reason"] = "budget_selected"
            else:
                dropped.append(block)
                block.metadata["selection_reason"] = "budget_exceeded"

        # Step 5: Log statistics
        selected_tokens = sum(b.tokens for b in selected)
        logger.info(
            f"Budget selection: {len(selected)}/{len(blocks)} blocks, "
            f"{selected_tokens}/{max_tokens} tokens "
            f"({selected_tokens/max_tokens*100:.1f}%)"
        )

        return selected, dropped

    def _calculate_type_budgets(
        self,
        blocks: List[Block],
        total_budget: int
    ) -> Dict[str, int]:
        """
        Allocate budget across block types based on fractions.
        Adjust fractions based on actual block distribution.

        Args:
            blocks: Optional blocks
            total_budget: Available budget

        Returns:
            Dict mapping block type to budget
        """
        # Count blocks per type
        type_counts = {}
        for block in blocks:
            type_counts[block.type.value] = type_counts.get(block.type.value, 0) + 1

        # If no blocks of a type, reallocate its fraction
        fractions = self.config.per_type_fractions.copy()
        active_types = set(type_counts.keys())

        # Redistribute fractions from missing types
        missing_fraction = sum(
            frac for type_name, frac in fractions.items()
            if type_name not in active_types
        )

        if missing_fraction > 0 and active_types:
            # Distribute proportionally to active types
            for type_name in active_types:
                if type_name in fractions:
                    fractions[type_name] += missing_fraction / len(active_types)

        # Calculate budgets
        type_budgets = {
            type_name: int(total_budget * frac)
            for type_name, frac in fractions.items()
            if type_name in active_types
        }

        logger.debug(f"Type budgets: {type_budgets}")

        return type_budgets

    def _get_utility_ratio(self, block: Block) -> float:
        """Get utility/token ratio for greedy selection"""
        utility = block.metadata.get("utility_score", block.priority)
        if block.tokens == 0:
            return 0.0
        return utility / block.tokens
