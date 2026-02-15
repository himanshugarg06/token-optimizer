#!/usr/bin/env python3
"""End-to-end test of the Token Optimizer."""

import requests
import json

BASE_URL = "http://localhost:8000"

def test_health():
    """Test health endpoint."""
    print("=" * 80)
    print("TEST 1: Health Check")
    print("=" * 80)

    response = requests.get(f"{BASE_URL}/v1/health")
    health = response.json()

    print(f"Status: {health['status']}")
    print(f"Redis: {health['redis']}")
    print(f"Postgres: {health['postgres']}")
    print(f"Semantic Available: {health['semantic_available']}")
    print(f"Compression Available: {health['compression_available']}")
    print()

def test_simple_optimization():
    """Test basic optimization (heuristics only)."""
    print("=" * 80)
    print("TEST 2: Simple Optimization (Heuristics Only)")
    print("=" * 80)

    payload = {
        "messages": [
            {"role": "system", "content": "You are a helpful assistant."},
            {"role": "user", "content": "Hello"},
            {"role": "assistant", "content": "Hi! How can I help you today?"},
            {"role": "user", "content": "What's 2+2?"}
        ],
        "model": "gpt-4",
        "max_tokens": 8000
    }

    response = requests.post(
        f"{BASE_URL}/v1/optimize",
        json=payload,
        headers={"X-API-Key": "dev-key-12345"}
    )

    result = response.json()
    stats = result["stats"]

    print(f"Tokens Before: {stats['tokens_before']}")
    print(f"Tokens After: {stats['tokens_after']}")
    print(f"Tokens Saved: {stats['tokens_saved']}")
    print(f"Compression Ratio: {stats['compression_ratio']:.1%}")
    print(f"Route: {stats['route']}")
    print(f"Latency: {stats['latency_ms']}ms")
    print(f"Cache Hit: {stats['cache_hit']}")
    print()

    return result

def test_complex_optimization():
    """Test optimization with large context (triggers semantic)."""
    print("=" * 80)
    print("TEST 3: Complex Optimization (Should Trigger Semantic)")
    print("=" * 80)

    # Create a long conversation that exceeds budget
    messages = [
        {"role": "system", "content": "You are a helpful coding assistant."},
    ]

    # Add many user/assistant turns with RAG-like content
    for i in range(20):
        messages.append({
            "role": "user",
            "content": f"Question {i}: Can you explain concept number {i}?"
        })
        messages.append({
            "role": "assistant",
            "content": f"Sure! Here's a detailed explanation of concept {i}. " +
                      "This is a very long explanation with lots of details. " * 20
        })

    # Add some RAG documents
    rag_docs = [
        {
            "content": f"Documentation entry {i}: " + "Very detailed documentation text. " * 50,
            "metadata": {"source": f"doc_{i}", "type": "doc"}
        }
        for i in range(10)
    ]

    # Final user question
    messages.append({
        "role": "user",
        "content": "Based on all the previous context, summarize concept 5 for me."
    })

    payload = {
        "messages": messages,
        "rag_context": rag_docs,
        "model": "gpt-4",
        "max_tokens": 2000  # Low budget to force semantic retrieval
    }

    response = requests.post(
        f"{BASE_URL}/v1/optimize",
        json=payload,
        headers={"X-API-Key": "dev-key-12345"}
    )

    result = response.json()
    stats = result["stats"]

    print(f"Tokens Before: {stats['tokens_before']}")
    print(f"Tokens After: {stats['tokens_after']}")
    print(f"Tokens Saved: {stats['tokens_saved']}")
    print(f"Compression Ratio: {stats['compression_ratio']:.1%}")
    print(f"Route: {stats['route']}")
    print(f"Latency: {stats['latency_ms']}ms")
    print(f"Cache Hit: {stats['cache_hit']}")
    print(f"\nSelected Blocks: {len(result['selected_blocks'])}")
    print(f"Dropped Blocks: {len(result['dropped_blocks'])}")

    # Show route breakdown
    print(f"\nRoute Analysis:")
    route_stages = stats['route'].split('+')
    for stage in route_stages:
        print(f"  - {stage}")

    print(f"\nStage Timings:")
    for stage, timing in result['debug']['stage_timings_ms'].items():
        print(f"  {stage}: {timing}ms")

    print()
    return result

def test_cache():
    """Test caching behavior."""
    print("=" * 80)
    print("TEST 4: Cache Behavior")
    print("=" * 80)

    payload = {
        "messages": [
            {"role": "user", "content": "Test cache message"}
        ],
        "model": "gpt-4"
    }

    # First request - cache miss
    print("First request (cache miss):")
    response1 = requests.post(
        f"{BASE_URL}/v1/optimize",
        json=payload,
        headers={"X-API-Key": "dev-key-12345"}
    )
    result1 = response1.json()
    print(f"  Cache Hit: {result1['stats']['cache_hit']}")
    print(f"  Latency: {result1['stats']['latency_ms']}ms")

    # Second request - cache hit
    print("\nSecond request (cache hit):")
    response2 = requests.post(
        f"{BASE_URL}/v1/optimize",
        json=payload,
        headers={"X-API-Key": "dev-key-12345"}
    )
    result2 = response2.json()
    print(f"  Cache Hit: {result2['stats']['cache_hit']}")
    print(f"  Latency: {result2['stats']['latency_ms']}ms")
    print(f"  Speedup: {result1['stats']['latency_ms'] / result2['stats']['latency_ms']:.1f}x")
    print()

def test_metrics():
    """Test metrics endpoint."""
    print("=" * 80)
    print("TEST 5: Metrics")
    print("=" * 80)

    response = requests.get(f"{BASE_URL}/v1/metrics")
    metrics = response.text

    # Parse and show key metrics
    lines = metrics.split('\n')
    for line in lines:
        if 'token_optimizer' in line and not line.startswith('#'):
            print(line)

    print()

if __name__ == "__main__":
    print("\n" + "=" * 80)
    print(" TOKEN OPTIMIZER E2E TEST SUITE")
    print("=" * 80 + "\n")

    try:
        test_health()
        test_simple_optimization()
        test_complex_optimization()
        test_cache()
        test_metrics()

        print("=" * 80)
        print("✅ ALL TESTS COMPLETED")
        print("=" * 80)

    except Exception as e:
        print(f"\n❌ TEST FAILED: {e}")
        import traceback
        traceback.print_exc()
