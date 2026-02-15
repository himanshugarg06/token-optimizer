#!/bin/bash

# Performance Test Suite for Token Optimizer Middleware
# Tests: Cache performance, load testing, different prompt sizes

BASE_URL="http://localhost:8000"
API_KEY="dev-key-12345"

echo "🧪 Token Optimizer Performance Test Suite"
echo "=========================================="
echo ""

# Colors
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m' # No Color

# Test counter
PASS=0
FAIL=0

# Function to make API call and measure time
test_optimize() {
    local name=$1
    local payload=$2
    local expected_cache=$3

    echo -n "Testing: $name ... "

    start=$(python3 -c "import time; print(int(time.time() * 1000))")
    response=$(curl -s -X POST "$BASE_URL/v1/optimize" \
        -H "X-API-Key: $API_KEY" \
        -H "Content-Type: application/json" \
        -d "$payload")
    end=$(python3 -c "import time; print(int(time.time() * 1000))")

    elapsed=$((end - start))

    latency=$(echo "$response" | jq -r '.stats.latency_ms')
    cache_hit=$(echo "$response" | jq -r '.stats.cache_hit')
    tokens_before=$(echo "$response" | jq -r '.stats.tokens_before')
    tokens_after=$(echo "$response" | jq -r '.stats.tokens_after')
    tokens_saved=$(echo "$response" | jq -r '.stats.tokens_saved')

    echo -e "${GREEN}✓${NC}"
    echo "  Total time: ${elapsed}ms"
    echo "  Internal latency: ${latency}ms"
    echo "  Cache hit: $cache_hit (expected: $expected_cache)"
    echo "  Tokens: $tokens_before → $tokens_after (saved: $tokens_saved)"
    echo ""

    if [[ "$cache_hit" == "$expected_cache" ]]; then
        ((PASS++))
    else
        ((FAIL++))
        echo -e "  ${RED}Cache expectation mismatch!${NC}"
    fi
}

# Test 1: Small prompt (baseline)
echo "📊 Test 1: Small Prompt (Baseline)"
echo "-----------------------------------"
test_optimize "Small prompt (first call)" '{
  "messages": [
    {"role": "system", "content": "You are helpful."},
    {"role": "user", "content": "Hi"}
  ],
  "model": "gpt-4"
}' "false"

# Test 2: Cache hit on same prompt
echo "📊 Test 2: Cache Performance"
echo "-----------------------------"
test_optimize "Small prompt (cached)" '{
  "messages": [
    {"role": "system", "content": "You are helpful."},
    {"role": "user", "content": "Hi"}
  ],
  "model": "gpt-4"
}' "true"

# Test 3: Medium prompt with repetition
echo "📊 Test 3: Medium Prompt with Optimization"
echo "-------------------------------------------"
test_optimize "Medium prompt with duplicates" '{
  "messages": [
    {"role": "system", "content": "You are a helpful assistant. You are friendly."},
    {"role": "user", "content": "Hello there!"},
    {"role": "assistant", "content": "Sure, I can help with that!"},
    {"role": "user", "content": "Hello there!"},
    {"role": "assistant", "content": "Of course!"},
    {"role": "user", "content": "What is Python?"}
  ],
  "model": "gpt-4"
}' "false"

# Test 4: Large prompt
echo "📊 Test 4: Large Prompt"
echo "-----------------------"
test_optimize "Large prompt (200+ tokens)" '{
  "messages": [
    {"role": "system", "content": "You are a helpful AI assistant specialized in programming. You provide clear, concise answers. You always include examples. You explain complex concepts simply."},
    {"role": "user", "content": "Question 1"},
    {"role": "assistant", "content": "Sure, I can help you with that! Of course! Let me explain..."},
    {"role": "user", "content": "Question 2"},
    {"role": "assistant", "content": "Sure, I can help you with that! Of course! Let me explain..."},
    {"role": "user", "content": "Question 3"},
    {"role": "assistant", "content": "Sure, I can help you with that! Of course! Let me explain..."},
    {"role": "user", "content": "Question 4"},
    {"role": "assistant", "content": "Sure, I can help you with that! Of course! Let me explain..."},
    {"role": "user", "content": "Explain machine learning in detail"}
  ],
  "model": "gpt-4"
}' "false"

# Test 5: Constraint extraction
echo "📊 Test 5: Constraint Extraction"
echo "---------------------------------"
test_optimize "Constraints (MUST/NEVER)" '{
  "messages": [
    {"role": "system", "content": "You MUST respond in JSON format. NEVER include personal information. ALWAYS validate input."},
    {"role": "user", "content": "Process data"}
  ],
  "model": "gpt-4"
}' "false"

# Test 6: Concurrent requests (load test)
echo "📊 Test 6: Concurrent Load Test"
echo "--------------------------------"
echo "Sending 10 concurrent requests..."

start_concurrent=$(python3 -c "import time; print(int(time.time() * 1000))")

for i in {1..10}; do
    (curl -s -X POST "$BASE_URL/v1/optimize" \
        -H "X-API-Key: $API_KEY" \
        -H "Content-Type: application/json" \
        -d '{
          "messages": [
            {"role": "system", "content": "You are helpful."},
            {"role": "user", "content": "Request '$i'"}
          ],
          "model": "gpt-4"
        }' > /dev/null) &
done

wait

end_concurrent=$(python3 -c "import time; print(int(time.time() * 1000))")
elapsed_concurrent=$((end_concurrent - start_concurrent))

echo -e "${GREEN}✓${NC} Completed 10 concurrent requests in ${elapsed_concurrent}ms"
echo "  Average: $((elapsed_concurrent / 10))ms per request"
echo ""

# Test 7: Sequential requests (throughput)
echo "📊 Test 7: Sequential Throughput"
echo "---------------------------------"
echo "Sending 20 sequential requests..."

start_seq=$(python3 -c "import time; print(int(time.time() * 1000))")

for i in {1..20}; do
    curl -s -X POST "$BASE_URL/v1/optimize" \
        -H "X-API-Key: $API_KEY" \
        -H "Content-Type: application/json" \
        -d '{
          "messages": [
            {"role": "system", "content": "You are helpful."},
            {"role": "user", "content": "Request number '$i'"}
          ],
          "model": "gpt-4"
        }' > /dev/null
done

end_seq=$(python3 -c "import time; print(int(time.time() * 1000))")
elapsed_seq=$((end_seq - start_seq))

echo -e "${GREEN}✓${NC} Completed 20 sequential requests in ${elapsed_seq}ms"
echo "  Average: $((elapsed_seq / 20))ms per request"
echo "  Throughput: $((20000 / elapsed_seq)) requests/second"
echo ""

# Test 8: Memory efficiency test
echo "📊 Test 8: Memory Efficiency"
echo "-----------------------------"
echo "Testing with very large prompt (1000+ tokens)..."

large_content=$(python3 -c "print('This is a very long message. ' * 200)")

response=$(curl -s -X POST "$BASE_URL/v1/optimize" \
    -H "X-API-Key: $API_KEY" \
    -H "Content-Type: application/json" \
    -d '{
      "messages": [
        {"role": "system", "content": "System prompt"},
        {"role": "user", "content": "'"$large_content"'"}
      ],
      "model": "gpt-4"
    }')

latency=$(echo "$response" | jq -r '.stats.latency_ms')
tokens_before=$(echo "$response" | jq -r '.stats.tokens_before')
tokens_after=$(echo "$response" | jq -r '.stats.tokens_after')

echo -e "${GREEN}✓${NC} Large prompt processed"
echo "  Latency: ${latency}ms"
echo "  Tokens: $tokens_before → $tokens_after"
echo ""

# Summary
echo "=========================================="
echo "📈 Performance Test Summary"
echo "=========================================="
echo ""
echo "Tests passed: $PASS"
echo "Tests failed: $FAIL"
echo ""

# Get current metrics
echo "🔍 Current Prometheus Metrics:"
echo "------------------------------"
curl -s "$BASE_URL/v1/metrics" | grep -E "(requests_total|tokens_saved|cache_hits)" | head -10

echo ""
echo "✅ Performance testing complete!"
