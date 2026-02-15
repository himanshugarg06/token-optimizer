# Railway Deployment Checklist

**Your Railway Project:** `token-optimizer`

---

## ✅ What You Already Have

Based on your setup, you have:

1. ✅ **Railway Postgres with pgvector**
   - URL: `postgres://postgres:UF1hm28nKcTFXsZGpyKvSN7pqcnnlNp3@crossover.proxy.rlwy.net:16861/railway`
   - pgvector version: 0.8.1
   - Migrations: Applied ✅

2. ✅ **Railway Project**
   - Name: `token-optimizer`

---

## 🚀 What You Need to Deploy

### Step 1: Deploy Backend Service

**In Railway Dashboard:**

1. **Create new service in `token-optimizer` project**
   - Click "New" → "GitHub Repo"
   - Select: `token-optimizer-repo`
   - **Root directory**: `/backend` ⚠️ IMPORTANT

2. **Or via Railway CLI:**
   ```bash
   cd /Users/himanshu/workspace/token-optimizer-repo/backend
   railway link
   railway up
   ```

### Step 2: Add Redis Service

**In Railway Dashboard:**

1. Click "New" → "Database" → "Redis"
2. Railway auto-generates: `${{Redis.REDIS_URL}}`

### Step 3: Set Environment Variables

**In Backend Service → Variables:**

```env
# Core
MIDDLEWARE_API_KEY=<generate-secure-random-key>

# Infrastructure (REQUIRED)
REDIS_URL=${{Redis.REDIS_URL}}
SEMANTIC__POSTGRES_URL=${{Postgres.DATABASE_URL}}

# Features
SEMANTIC__ENABLED=true
COMPRESSION__ENABLED=false

# Semantic Config
SEMANTIC__EMBEDDING_MODEL=BAAI/bge-base-en-v1.5
SEMANTIC__EMBEDDING_DIM=768
SEMANTIC__EMBEDDING_DEVICE=cpu
SEMANTIC__VECTOR_TOPK=30
SEMANTIC__MMR_LAMBDA=0.7

# Budget Allocation
BUDGET__PER_TYPE_FRACTIONS__DOC=0.4
BUDGET__PER_TYPE_FRACTIONS__ASSISTANT=0.3
BUDGET__PER_TYPE_FRACTIONS__TOOL=0.2
BUDGET__PER_TYPE_FRACTIONS__USER=0.1

# Optimization
MAX_INPUT_TOKENS=8000
KEEP_LAST_N_TURNS=4
SAFETY_MARGIN_TOKENS=300

# Observability
LOG_LEVEL=INFO

# Optional: LLM Provider API Keys (for /v1/chat endpoint)
# OPENAI_API_KEY=sk-...
# ANTHROPIC_API_KEY=sk-ant-...

# Optional: Dashboard
DASHBOARD_ENABLED=false
MOCK_DASHBOARD=false
```

**To generate secure API key:**
```bash
openssl rand -hex 32
```

### Step 4: Verify Deployment

**After deployment completes:**

1. **Check health endpoint:**
   ```bash
   curl https://your-app.railway.app/v1/health
   ```

   **Expected response:**
   ```json
   {
     "status": "healthy",
     "redis": "connected",
     "postgres": "connected",
     "semantic_available": true,
     "compression_available": false,
     "timestamp": "2026-02-15T12:00:00.000000Z"
   }
   ```

2. **Test optimization:**
   ```bash
   curl -X POST https://your-app.railway.app/v1/optimize \
     -H "X-API-Key: your-middleware-api-key" \
     -H "Content-Type: application/json" \
     -d '{
       "messages": [
         {"role": "user", "content": "Hello, test message"}
       ],
       "model": "gpt-4"
     }'
   ```

   **Expected response:**
   ```json
   {
     "optimized_messages": [...],
     "stats": {
       "tokens_before": 23,
       "tokens_after": 23,
       "route": "heuristic",
       "latency_ms": 45,
       "cache_hit": false
     }
   }
   ```

---

## 📋 Current Status vs. Codebase

### ✅ What's Already Synced

- ✅ Database schema (migrations applied)
- ✅ pgvector extension (v0.8.1)
- ✅ Semantic retrieval code (BAAI/bge-base-en-v1.5)
- ✅ Compression code (with extractive fallback)
- ✅ Enhanced heuristics (tool minimization, log trimming, TOON)
- ✅ Budget allocation (greedy knapsack)
- ✅ Pipeline (class-based architecture)

### ⚠️ What Needs to be Deployed

1. **Backend Service** (not deployed yet)
   - Need to push code to Railway
   - Configure environment variables
   - Connect to Redis + Postgres

2. **Redis Service** (if not already added)
   - Add Redis database in Railway
   - Connect to backend via `REDIS_URL`

### ❌ Optional Features (Can Add Later)

- **LLMLingua-2 Compression**: Uncomment in `requirements.txt` line 24
  - First deploy will be slower (~10s) as it downloads model (~500MB)
  - Improves compression from ~50% to ~60-70%

- **Dashboard Integration**: If you have an analytics dashboard
  - Set `DASHBOARD_ENABLED=true`
  - Set `DASHBOARD_BASE_URL` and `DASHBOARD_API_KEY`

- **LLM Provider Keys**: Only needed for `/v1/chat` endpoint
  - Most users don't need this (they use `/v1/optimize` and forward themselves)

---

## 🔧 Troubleshooting

### Issue: "Module not found" errors

**Cause**: Missing dependencies

**Fix**: Ensure `requirements.txt` is complete
```bash
cat requirements.txt
```

Should include:
- fastapi, uvicorn
- redis, psycopg2-binary, pgvector
- sentence-transformers, numpy
- pydantic, structlog

### Issue: "Connection refused" to Postgres

**Cause**: Wrong connection string format

**Fix**: Railway uses `${{Postgres.DATABASE_URL}}` variable reference
```env
SEMANTIC__POSTGRES_URL=${{Postgres.DATABASE_URL}}
```

NOT the hardcoded string.

### Issue: "semantic_available: false"

**Cause**: Embedding model download timeout or memory limit

**Fix**:
1. Check Railway logs: `railway logs`
2. Increase memory limit if needed (Railway settings)
3. First request may be slow (~10s) as model downloads

### Issue: "compression_available: false"

**Expected**: LLMLingua is optional and commented out

**To enable**: Uncomment line 24 in `requirements.txt`:
```python
llmlingua==0.2.2
```

Then redeploy:
```bash
git add requirements.txt
git commit -m "Enable LLMLingua compression"
git push
```

---

## 📊 Expected Performance (After Deployment)

### Token Reduction
- **Heuristics only**: 45-54% reduction
- **Heuristics + Semantic**: 55-65% reduction
- **Heuristics + Semantic + Compression**: 60-75% reduction

### Latency
- **Heuristics only**: <200ms
- **With semantic retrieval**: ~1-2s (first request: ~5s for model load)
- **With compression**: +500ms (if LLMLingua enabled)

### Cache Hit Speedup
- **Cache hit**: ~14.5x faster (29ms → 2ms)
- **Cache TTL**: 10 minutes

### Accuracy
- **Faithfulness score**: ≥0.85 (compression rejected if lower)
- **Must-keep blocks**: Always preserved (100%)
- **Constraint preservation**: Always preserved (MUST/NEVER/ALWAYS)

---

## 🎯 Quick Commands Reference

### Railway CLI

```bash
# Install Railway CLI
npm install -g @railway/cli

# Login
railway login

# Link to project
railway link

# Deploy
railway up

# View logs
railway logs

# View environment variables
railway vars

# Set variable
railway vars set MIDDLEWARE_API_KEY=<value>

# Open dashboard
railway open
```

### Testing Locally Before Deploy

```bash
# Start local stack
docker-compose up -d

# Check health
curl http://localhost:8000/v1/health | jq

# Test optimization
curl -X POST http://localhost:8000/v1/optimize \
  -H "X-API-Key: dev-key-12345" \
  -H "Content-Type: application/json" \
  -d '{"messages": [{"role": "user", "content": "Hi"}], "model": "gpt-4"}'

# View metrics
curl http://localhost:8000/v1/metrics

# View logs
docker logs backend_token-optimizer_1 -f
```

---

## 💰 Cost Estimate

### Railway Resources

**Recommended Plan: Pro ($20/month)**
- 8GB RAM (needed for embedding model)
- 4 vCPU
- Unlimited projects
- 500GB egress

**Services:**
1. Backend (FastAPI): Uses Pro plan resources
2. Redis: Included
3. Postgres with pgvector: Already provisioned ✅

**Total: $20/month**

### ROI Example

For 1M requests/month with 500 tokens avg:

**Without optimizer:**
- Input tokens: 500M
- Cost (GPT-4 input): $15,000/month

**With optimizer (55% reduction):**
- Input tokens: 225M
- Cost: $6,750/month
- **Savings: $8,250/month**

**Net savings: $8,230/month** (after Railway cost)

**ROI: 411x** 🚀

---

## ✅ Final Checklist

Before going to production:

- [ ] Backend service deployed on Railway
- [ ] Redis service added and connected
- [ ] Postgres URL configured with `${{Postgres.DATABASE_URL}}`
- [ ] `MIDDLEWARE_API_KEY` set to secure random string
- [ ] Health check returns `"status": "healthy"`
- [ ] Test `/v1/optimize` endpoint works
- [ ] Metrics endpoint accessible
- [ ] Logs show "semantic_available: true"
- [ ] Migrations completed successfully
- [ ] (Optional) LLMLingua enabled if needed
- [ ] (Optional) Dashboard integration configured

---

## 📚 Documentation

- **Full Deployment Guide**: [RAILWAY_DEPLOYMENT.md](RAILWAY_DEPLOYMENT.md)
- **System Status**: [SYSTEM_STATUS.md](SYSTEM_STATUS.md)
- **API Documentation**: [README.md](README.md)
- **Troubleshooting**: [TROUBLESHOOTING.md](TROUBLESHOOTING.md)

---

**Questions?** Check the docs above or Railway logs: `railway logs`
