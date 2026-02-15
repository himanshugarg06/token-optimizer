# Token Optimizer Middleware - Troubleshooting Guide

**Last Updated**: February 15, 2026

This document covers common issues, errors, and their solutions for the Token Optimizer Middleware.

---

## 🔧 Quick Diagnostics

### Check Service Health
```bash
curl http://localhost:8000/v1/health | jq '.'
```

**Expected output**:
```json
{
  "status": "healthy",
  "redis": "connected",
  "postgres": null,
  "dashboard": "configured",
  "timestamp": "2026-02-15T10:30:00Z"
}
```

### Check Docker Containers
```bash
docker ps | grep -E "(redis|postgres|optimizer)"
```

**Expected**: 3 containers running

### View Logs
```bash
# Token optimizer service
docker logs token_optimizer-token-optimizer-1 --follow

# Redis
docker logs token_optimizer-redis-1 --follow

# All services
docker-compose logs --follow
```

---

## 🐛 Common Issues & Solutions

### Issue 1: "Connection refused" on port 8000

**Symptoms**:
```bash
$ curl http://localhost:8000/v1/health
curl: (7) Failed to connect to localhost port 8000 after 0 ms: Connection refused
```

**Causes**:
1. Docker Desktop not running
2. Containers not started
3. Service crashed

**Solutions**:

```bash
# 1. Check if Docker Desktop is running
open -a Docker  # macOS
# Wait for Docker Desktop to fully start

# 2. Start containers
cd /Users/himanshu/workspace/token-optimizer-repo/backend
docker-compose up -d

# 3. Check if containers are running
docker ps

# 4. Check service logs for errors
docker logs token_optimizer-token-optimizer-1

# 5. Rebuild if needed
docker-compose up --build -d
```

---

### Issue 2: "Counters can only be incremented by non-negative amounts"

**Symptoms**:
```json
{
  "detail": "Optimization failed: Counters can only be incremented by non-negative amounts."
}
```

**Error in logs**:
```python
ValueError: Counters can only be incremented by non-negative amounts.
  File "/app/app/observability/metrics.py", line 85, in record_optimization
    tokens_before_total.inc(tokens_before)
```

**Cause**:
Prometheus counters require non-negative values. Edge cases in optimization or cache retrieval can produce:
- `None` values
- Negative token_saved values
- String values from JSON deserialization

**Solution**: ✅ **FIXED in latest code**

File: `app/observability/metrics.py` (lines 78-89)
```python
# Record token metrics (ensure they are integers)
try:
    tokens_before = int(stats.get("tokens_before", 0)) if stats.get("tokens_before") is not None else 0
    tokens_after = int(stats.get("tokens_after", 0)) if stats.get("tokens_after") is not None else 0
    tokens_saved = int(stats.get("tokens_saved", 0)) if stats.get("tokens_saved") is not None else 0
except (ValueError, TypeError):
    tokens_before = 0
    tokens_after = 0
    tokens_saved = 0

# Only increment with non-negative values (Prometheus requirement)
if tokens_before > 0:
    tokens_before_total.inc(tokens_before)
if tokens_after > 0:
    tokens_after_total.inc(tokens_after)
if tokens_saved > 0:
    tokens_saved_total.inc(tokens_saved)
```

**If you still see this error**:
```bash
# 1. Pull latest code
git pull origin main

# 2. Restart service
docker restart token_optimizer-token-optimizer-1

# 3. Clear cache (may have bad cached data)
docker exec token_optimizer-redis-1 redis-cli FLUSHALL
```

---

### Issue 3: Performance test timing errors

**Symptoms**:
```bash
$ bash tests/performance_test.sh
-bash: ((: 1739619945N - 1739619945N: value too great for base (error token is "N - 1739619945N")
```

**Cause**:
macOS `date` command doesn't support nanoseconds (`%N` flag). Script was using:
```bash
start=$(date +%s%N)  # Returns "1739619945N" instead of nanoseconds
```

**Solution**: ✅ **FIXED in latest code**

File: `tests/performance_test.sh` (lines 33-40, 135, 152, 164, 179)

Changed from:
```bash
start=$(date +%s%N)
end=$(date +%s%N)
elapsed=$(( (end - start) / 1000000 ))
```

To:
```bash
start=$(python3 -c "import time; print(int(time.time() * 1000))")
end=$(python3 -c "import time; print(int(time.time() * 1000))")
elapsed=$((end - start))
```

**If you still see this error**:
```bash
# Update the script
cd /Users/himanshu/workspace/token-optimizer-repo/backend
git pull origin main

# Or manually fix by replacing all date +%s%N with Python timing
```

---

### Issue 4: Redis connection failed

**Symptoms**:
```json
{
  "status": "degraded",
  "redis": "disconnected"
}
```

**Logs**:
```
WARNING - Redis cache unavailable: Connection refused
```

**Causes**:
1. Redis container not running
2. Redis port conflict (6379 already in use)
3. Network issue between containers

**Solutions**:

```bash
# 1. Check if Redis container is running
docker ps | grep redis

# 2. Start Redis if not running
docker-compose up -d redis

# 3. Check Redis logs
docker logs token_optimizer-redis-1

# 4. Test Redis connection manually
docker exec token_optimizer-redis-1 redis-cli ping
# Expected: PONG

# 5. Check if port 6379 is available
lsof -i :6379

# 6. If port conflict, update docker-compose.yml to use different port:
# redis:
#   ports:
#     - "6380:6379"
# Then update REDIS_URL in .env

# 7. Restart all services
docker-compose down
docker-compose up -d
```

---

### Issue 5: Dashboard client errors (non-critical)

**Symptoms**:
```
WARNING - Dashboard fetch failed: Connection refused
```

**Cause**:
Dashboard service not available (external or mock not running)

**Impact**:
⚠️ **Non-critical** - Service continues to work, just can't fetch user preferences or emit events

**Solution**:

```bash
# Option 1: Use mock dashboard (default)
# In .env:
MOCK_DASHBOARD=true
DASHBOARD_ENABLED=true

# Option 2: Disable dashboard integration
# In .env:
DASHBOARD_ENABLED=false

# Option 3: Point to external dashboard
# In .env:
DASHBOARD_BASE_URL=https://your-dashboard.com
DASHBOARD_API_KEY=your-api-key
MOCK_DASHBOARD=false

# Restart service after changing .env
docker restart token_optimizer-token-optimizer-1
```

---

### Issue 6: "Module not found" errors

**Symptoms**:
```python
ModuleNotFoundError: No module named 'fastapi'
```

**Cause**:
Dependencies not installed in container

**Solutions**:

```bash
# 1. Rebuild containers with dependencies
cd /Users/himanshu/workspace/token-optimizer-repo/backend
docker-compose up --build

# 2. Check requirements.txt exists and is complete
cat requirements.txt

# 3. If adding new dependencies, rebuild:
echo "new-package==1.0.0" >> requirements.txt
docker-compose up --build

# 4. Clear Docker cache if persistent issues
docker-compose down
docker system prune -f
docker-compose up --build
```

---

### Issue 7: Cache returning stale data

**Symptoms**:
- Optimization not reflecting recent changes
- Old token counts appearing
- Cache hit on modified prompts

**Cause**:
Redis cache TTL hasn't expired (default 10 minutes)

**Solutions**:

```bash
# 1. Clear all cache (recommended for testing)
docker exec token_optimizer-redis-1 redis-cli FLUSHALL

# 2. Clear specific key
docker exec token_optimizer-redis-1 redis-cli DEL "opt:cache:abc123"

# 3. View all cache keys
docker exec token_optimizer-redis-1 redis-cli KEYS "opt:cache:*"

# 4. Check TTL of a key
docker exec token_optimizer-redis-1 redis-cli TTL "opt:cache:abc123"

# 5. Reduce cache TTL in code (app/optimizers/cache.py)
# Change: ttl: int = 600  # to shorter time for testing
```

---

### Issue 8: Performance test cache mismatches

**Symptoms**:
```
Cache expectation mismatch!
Tests passed: 4
Tests failed: 1
```

**Cause**:
Cache from previous test run still active

**Solutions**:

```bash
# 1. Always clear cache before performance tests
docker exec token_optimizer-redis-1 redis-cli FLUSHALL
bash tests/performance_test.sh

# 2. Make sure script doesn't exit on first failure
# Check that tests/performance_test.sh doesn't have "set -e"
head -10 tests/performance_test.sh
# Should NOT see: set -e

# 3. Add cache clear to test script
# At top of tests/performance_test.sh, add:
# docker exec token_optimizer-redis-1 redis-cli FLUSHALL 2>/dev/null || true
```

---

### Issue 9: Port 8000 already in use

**Symptoms**:
```
Error: Bind for 0.0.0.0:8000 failed: port is already allocated
```

**Cause**:
Another service using port 8000 (possibly the original token_optimizer at `/Users/himanshu/workspace/token_optimizer`)

**Solutions**:

```bash
# 1. Check what's using port 8000
lsof -i :8000

# 2. Kill the process using port 8000
kill -9 $(lsof -t -i:8000)

# 3. Or change port in docker-compose.yml
# Edit backend/docker-compose.yml:
# token-optimizer:
#   ports:
#     - "8001:8000"  # Changed from 8000:8000

# Then update BASE_URL in tests
# tests/performance_test.sh:
# BASE_URL="http://localhost:8001"

# 4. Stop old token_optimizer if running
cd /Users/himanshu/workspace/token_optimizer
docker-compose down

# 5. Start backend service
cd /Users/himanshu/workspace/token-optimizer-repo/backend
docker-compose up -d
```

---

### Issue 10: Git "Symbol not found: _curl_global_trace"

**Symptoms**:
```
dyld[12345]: symbol not found in flat namespace '_curl_global_trace'
```

**Cause**:
Git HTTPS clone issue on macOS

**Solution**:

```bash
# Use SSH instead of HTTPS for git operations
git remote set-url origin git@github.com:himanshugarg06/token-optimizer.git
git pull
git push
```

---

## 🧪 Testing & Debugging

### Manual API Testing

```bash
# 1. Health check
curl http://localhost:8000/v1/health | jq '.'

# 2. Simple optimization
curl -X POST http://localhost:8000/v1/optimize \
  -H "X-API-Key: dev-key-12345" \
  -H "Content-Type: application/json" \
  -d '{
    "messages": [
      {"role": "system", "content": "You are helpful."},
      {"role": "user", "content": "Hi"}
    ],
    "model": "gpt-4"
  }' | jq '.'

# 3. Test with longer prompt
curl -X POST http://localhost:8000/v1/optimize \
  -H "X-API-Key: dev-key-12345" \
  -H "Content-Type: application/json" \
  -d '{
    "messages": [
      {"role": "system", "content": "You are helpful."},
      {"role": "user", "content": "Hello"},
      {"role": "assistant", "content": "Sure, I can help."},
      {"role": "user", "content": "Hello"},
      {"role": "assistant", "content": "Of course!"},
      {"role": "user", "content": "What is Python?"}
    ],
    "model": "gpt-4"
  }' | jq '.stats'

# 4. Check metrics
curl http://localhost:8000/v1/metrics

# 5. Test with wrong API key (should fail)
curl -X POST http://localhost:8000/v1/optimize \
  -H "X-API-Key: wrong-key" \
  -H "Content-Type: application/json" \
  -d '{"messages":[],"model":"gpt-4"}'
# Expected: 401 Unauthorized
```

### Check Redis Cache

```bash
# View all cache keys
docker exec token_optimizer-redis-1 redis-cli KEYS "*"

# View specific cache entry
docker exec token_optimizer-redis-1 redis-cli GET "opt:cache:abc123"

# Monitor Redis in real-time
docker exec -it token_optimizer-redis-1 redis-cli MONITOR

# Check Redis memory usage
docker exec token_optimizer-redis-1 redis-cli INFO memory
```

### Performance Profiling

```bash
# 1. Run performance tests
bash tests/performance_test.sh

# 2. Watch metrics in real-time
watch -n 1 'curl -s http://localhost:8000/v1/metrics | grep -E "(requests|tokens|cache)"'

# 3. Load test with Apache Bench
ab -n 100 -c 10 \
  -H "X-API-Key: dev-key-12345" \
  -H "Content-Type: application/json" \
  -p test_payload.json \
  http://localhost:8000/v1/optimize

# 4. Monitor container resources
docker stats token_optimizer-token-optimizer-1
```

---

## 🔍 Debugging Tips

### Enable Debug Logging

Edit `.env`:
```bash
LOG_LEVEL=DEBUG  # Change from INFO
```

Restart service:
```bash
docker restart token_optimizer-token-optimizer-1
docker logs token_optimizer-token-optimizer-1 --follow
```

### Interactive Python Debugging

```bash
# Enter running container
docker exec -it token_optimizer-token-optimizer-1 /bin/bash

# Run Python interactively
python3

# Test imports
>>> from app.core.utils import count_tokens
>>> count_tokens("Hello world", "gpt-4")
2

# Test pipeline
>>> from app.core.pipeline import optimize
>>> import asyncio
>>> asyncio.run(optimize([{"role": "user", "content": "Hi"}], {}, None))
```

### Database Inspection

```bash
# Connect to PostgreSQL
docker exec -it token_optimizer-postgres-1 psql -U postgres -d optimizer

# List tables
\dt

# Query blocks (if semantic retrieval is enabled)
SELECT COUNT(*) FROM blocks;

# Exit
\q
```

---

## 📞 Getting Help

### Check Documentation
1. [README.md](README.md) - Quick start and API reference
2. [IMPLEMENTATION_STATUS.md](IMPLEMENTATION_STATUS.md) - Feature status
3. [PERFORMANCE_RESULTS.md](PERFORMANCE_RESULTS.md) - Test results
4. [claude.md](claude.md) - Original implementation guide

### Useful Commands Cheat Sheet
```bash
# Start everything
docker-compose up -d

# Stop everything
docker-compose down

# Restart service only
docker restart token_optimizer-token-optimizer-1

# View logs
docker logs token_optimizer-token-optimizer-1 --follow

# Clear cache
docker exec token_optimizer-redis-1 redis-cli FLUSHALL

# Run tests
bash tests/performance_test.sh

# Health check
curl http://localhost:8000/v1/health

# View metrics
curl http://localhost:8000/v1/metrics

# Rebuild from scratch
docker-compose down
docker-compose up --build
```

---

## 🆘 Emergency Recovery

If everything is broken:

```bash
# 1. Stop all containers
cd /Users/himanshu/workspace/token-optimizer-repo/backend
docker-compose down

# 2. Clean up Docker
docker system prune -f
docker volume prune -f

# 3. Rebuild from scratch
docker-compose up --build -d

# 4. Wait for services to start (30 seconds)
sleep 30

# 5. Verify health
curl http://localhost:8000/v1/health

# 6. Clear cache
docker exec token_optimizer-redis-1 redis-cli FLUSHALL

# 7. Run tests
bash tests/performance_test.sh
```

If still broken, check:
- Docker Desktop is running
- Port 8000 is not in use by another service
- `.env` file exists and has correct values
- No syntax errors in Python files (run: `python3 -m py_compile app/**/*.py`)

---

**Last Resort**:
```bash
# Delete everything and re-clone
cd /Users/himanshu/workspace
rm -rf token-optimizer-repo
git clone git@github.com:himanshugarg06/token-optimizer.git token-optimizer-repo
cd token-optimizer-repo/backend
cp .env.example .env
docker-compose up --build -d
```

---

**Need more help?** Check the logs carefully - they usually contain the exact error and line number.
