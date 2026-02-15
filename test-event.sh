#!/bin/bash

# Test if the events endpoint is working

DASHBOARD_URL="https://token-optimizer-production.up.railway.app"
DASHBOARD_API_KEY="your-dashboard-api-key-here"  # Replace with actual key
USER_ID="your-user-id-here"  # Replace with your actual user ID

# Test event in the format the dashboard expects
curl -X POST "$DASHBOARD_URL/api/events" \
  -H "Content-Type: application/json" \
  -H "X-API-Key: $DASHBOARD_API_KEY" \
  -H "X-Source: token-optimizer-middleware" \
  -d '{
    "event_type": "optimization",
    "timestamp": "'$(date -u +"%Y-%m-%dT%H:%M:%SZ")'",
    "tenant_id": "'$USER_ID'",
    "project_id": "playground",
    "api_key_prefix": "tok_test",
    "model": "gpt-4o-mini",
    "endpoint": "/v1/chat",
    "stats": {
      "tokens_before": 100,
      "tokens_after": 50,
      "tokens_saved": 50,
      "compression_ratio": 0.5,
      "latency_ms": 123
    },
    "success": true
  }'
