import pytest

from app.core.pipeline import optimize as optimize_pipeline


@pytest.mark.asyncio
async def test_fallback_to_original_when_no_savings():
    # Constraint extraction can increase tokens; require at least 1 token saved
    # and verify we fall back to the original messages.
    messages = [
        {"role": "system", "content": "You MUST respond in JSON format. NEVER include personal information."},
        {"role": "user", "content": "Process data"},
    ]

    config = {
        "max_input_tokens": 8000,
        "keep_last_n_turns": 1,
        "safety_margin_tokens": 300,
        "min_tokens_saved": 1,
        "min_savings_ratio": 0.0,
    }

    optimized_messages, result = await optimize_pipeline(
        messages=messages,
        config=config,
        cache_manager=None,
        tools=None,
        rag_context=None,
        tool_outputs=None,
        model="gpt-4o-mini",
    )

    assert optimized_messages == messages
    assert result["stats"]["tokens_saved"] == 0
    assert result["stats"]["fallback_used"] is True
    assert "original" in result["stats"]["route"]

