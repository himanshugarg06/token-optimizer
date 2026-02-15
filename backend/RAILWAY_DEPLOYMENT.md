# Railway Deployment Guide with External Postgres

This guide shows how to deploy Token Optimizer to Railway using your existing Postgres instance.

## Prerequisites

✅ Railway account
✅ Postgres instance (Railway, AWS RDS, Neon, etc.)
✅ Postgres with pgvector extension support

---

## Step 1: Set Up Postgres Instance

### 1.1 Enable pgvector Extension

Connect to your Postgres instance and run:

```sql
CREATE EXTENSION IF NOT EXISTS vector;

-- Verify
SELECT extversion FROM pg_extension WHERE extname = 'vector';
```

**Connection methods:**

**If using Railway Postgres:**
```bash
# Via Railway CLI
railway connect postgres

# Then paste the CREATE EXTENSION command
```

**If using psql:**
```bash
psql "your-connection-string" -c "CREATE EXTENSION IF NOT EXISTS vector;"
```

**If using pgAdmin/DBeaver/etc:**
- Connect to your database
- Open SQL query window
- Run the CREATE EXTENSION command

### 1.2 Test Connection Locally

Before deploying, test that your Postgres works:

```bash
# Set environment variable
export SEMANTIC__POSTGRES_URL="postgresql://user:password@host:port/database"

# Run test script
python test_postgres.py
```

**Expected output:**
```
✅ Connection successful!
✓ PostgreSQL version: PostgreSQL 16.x
✅ pgvector extension is installed!
✓ pgvector version: 0.5.1
⚠ No migrations table found (will be created on first run)
✅ All checks passed! Database is ready.
```

### 1.3 Run Migrations Locally (Optional)

Test migrations before deploying:

```bash
export SEMANTIC__ENABLED=true
export SEMANTIC__POSTGRES_URL="your-connection-string"

python run_migrations.py
```

**Expected output:**
```
✅ Migrations completed successfully!
```

---

## Step 2: Deploy to Railway

### 2.1 Create Railway Project

```bash
# Install Railway CLI
npm install -g @railway/cli

# Login
railway login

# Create project
cd /path/to/token-optimizer-repo/backend
railway init
```

Or use the Railway dashboard:
1. Go to [railway.app](https://railway.app)
2. Click "New Project"
3. Select "Deploy from GitHub repo"
4. Choose your repository

### 2.2 Add Redis Service

In Railway dashboard:
1. Click "New" → "Database" → "Redis"
2. Railway auto-generates: `${{Redis.REDIS_URL}}`

### 2.3 Configure Backend Service

**Set root directory**: `/backend`

**Set environment variables:**

```env
# Core
MIDDLEWARE_API_KEY=<generate-secure-random-key>

# LLM Providers (optional)
OPENAI_API_KEY=<your-openai-key>
ANTHROPIC_API_KEY=<your-anthropic-key>

# Infrastructure
REDIS_URL=${{Redis.REDIS_URL}}

# YOUR POSTGRES INSTANCE
SEMANTIC__POSTGRES_URL=postgresql://user:password@your-host:5432/database
SEMANTIC__ENABLED=true

# Features
COMPRESSION__ENABLED=false
DASHBOARD_ENABLED=false
MOCK_DASHBOARD=false

# Optimization
MAX_INPUT_TOKENS=8000
KEEP_LAST_N_TURNS=4
SAFETY_MARGIN_TOKENS=300

# Budget Allocation
BUDGET__PER_TYPE_FRACTIONS__DOC=0.4
BUDGET__PER_TYPE_FRACTIONS__ASSISTANT=0.3
BUDGET__PER_TYPE_FRACTIONS__TOOL=0.2
BUDGET__PER_TYPE_FRACTIONS__USER=0.1

# Semantic Retrieval
SEMANTIC__EMBEDDING_MODEL=BAAI/bge-base-en-v1.5
SEMANTIC__EMBEDDING_DEVICE=cpu
SEMANTIC__VECTOR_TOPK=30
SEMANTIC__MMR_LAMBDA=0.7

# Logging
LOG_LEVEL=INFO
```

### 2.4 Deploy

**Via CLI:**
```bash
railway up
```

**Via Dashboard:**
- Push to GitHub
- Railway auto-deploys on push

### 2.5 Monitor Deployment

Watch logs in Railway dashboard:

**Look for these success indicators:**
```
✓ Running database migrations...
✓ Migration 001_semantic_retrieval applied successfully
✓ Database migrations completed successfully
✓ Redis: connected
✓ Semantic retrieval: enabled
✓ Application startup complete
```

---

## Step 3: Verify Deployment

### 3.1 Check Health Endpoint

```bash
# Replace with your Railway URL
curl https://your-app.railway.app/v1/health | jq
```

**Expected response:**
```json
{
  "status": "healthy",
  "redis": "connected",
  "postgres": "connected",
  "semantic_available": true,
  "compression_available": false,
  "dashboard": null,
  "timestamp": "2026-02-15T12:00:00.000000Z"
}
```

### 3.2 Test Optimization

```bash
curl -X POST https://your-app.railway.app/v1/optimize \
  -H "X-API-Key: your-middleware-api-key" \
  -H "Content-Type: application/json" \
  -d '{
    "messages": [
      {"role": "user", "content": "Hello, test message"}
    ],
    "model": "gpt-4"
  }' | jq
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

### 3.3 Check Metrics

```bash
curl https://your-app.railway.app/v1/metrics | grep token_optimizer
```

---

## Step 4: Enable LLMLingua Compression (Optional)

For better compression, enable LLMLingua-2:

### 4.1 Update requirements.txt

Uncomment line 24:
```python
# Before
# llmlingua==0.2.2

# After
llmlingua==0.2.2
```

### 4.2 Update Environment

```env
COMPRESSION__ENABLED=true
COMPRESSION__RATIO=0.5
COMPRESSION__FAITHFULNESS_THRESHOLD=0.85
```

### 4.3 Redeploy

```bash
git add requirements.txt
git commit -m "Enable LLMLingua compression"
git push

# Or via Railway CLI
railway up
```

**Note**: First request will be slower (~10s) as LLMLingua downloads (~500MB). Subsequent requests are fast.

---

## Connection String Formats

### Railway Postgres
```
postgresql://postgres:password@postgres.railway.internal:5432/railway
```

### AWS RDS
```
postgresql://username:password@instance.region.rds.amazonaws.com:5432/dbname
```

### Neon.tech
```
postgresql://user:password@ep-xxx.neon.tech/neondb
```

### Google Cloud SQL
```
postgresql://user:password@/database?host=/cloudsql/project:region:instance
```

### Azure Database
```
postgresql://user@server:password@server.postgres.database.azure.com:5432/database
```

---

## Troubleshooting

### Issue: "extension 'vector' does not exist"

**Solution**: Install pgvector extension
```sql
CREATE EXTENSION IF NOT EXISTS vector;
```

If you don't have permission, contact your DB admin or use a provider with native pgvector support (Neon, Supabase).

### Issue: "could not connect to server"

**Checklist:**
- ✓ Connection string is correct
- ✓ Database exists
- ✓ Username and password are correct
- ✓ Firewall/security group allows Railway's IPs
- ✓ SSL mode is correct (try adding `?sslmode=require`)

**Test connection:**
```bash
psql "your-connection-string" -c "SELECT 1;"
```

### Issue: "semantic_available: false"

**Check logs** for embedding model loading:
```
Loading embedding model: BAAI/bge-base-en-v1.5
```

**Common causes:**
- Not enough memory (need 2GB+ for model)
- First request timeout (model downloads ~400MB)
- Set longer timeout in Railway settings

### Issue: "Migration failed"

**Run migrations manually:**
```bash
railway run python run_migrations.py
```

**Check migration status:**
```sql
SELECT * FROM schema_migrations ORDER BY applied_at;
```

### Issue: High latency on first request

**Expected behavior**: First request loads models (~5-10s)

**Workaround**: Add health check warmup
```bash
# After deploy, trigger model load
curl https://your-app.railway.app/v1/health
```

---

## Cost Estimation

### Railway
- **Backend** (Pro plan): $20/month
- **Redis**: Included in plan
- **Total**: **$20/month**

### External Postgres
- **Railway Postgres**: $10/month
- **Neon.tech**: Free tier (3GB), then $19/month
- **AWS RDS**: ~$15-30/month (db.t3.micro)
- **Supabase**: Free tier (500MB), then $25/month

**Total estimated cost**: $20-50/month depending on Postgres choice

---

## Security Best Practices

### 1. API Key
```bash
# Generate strong key
openssl rand -hex 32

# Set as MIDDLEWARE_API_KEY
```

### 2. Database Credentials
- Use strong password (Railway auto-generates)
- Enable SSL: `?sslmode=require`
- Rotate credentials periodically

### 3. Network Security
- Use Railway's private networking for Redis
- Restrict Postgres to Railway's IP range if possible
- Enable TLS for all connections

### 4. Secrets Management
- Never commit `.env` to git
- Use Railway's environment variables UI
- Use separate keys for dev/staging/prod

---

## Monitoring & Observability

### Railway Dashboard
- View logs: `railway logs`
- View metrics: CPU, Memory, Network
- Set up alerts for errors

### Application Metrics
```bash
# Prometheus metrics
curl https://your-app.railway.app/v1/metrics

# Key metrics to monitor:
# - token_optimizer_requests_total
# - token_optimizer_tokens_saved_total
# - token_optimizer_cache_hits_total
# - token_optimizer_latency_seconds
```

### Database Monitoring
```sql
-- Check table sizes
SELECT
    schemaname,
    tablename,
    pg_size_pretty(pg_total_relation_size(schemaname||'.'||tablename)) AS size
FROM pg_tables
WHERE schemaname = 'public'
ORDER BY pg_total_relation_size(schemaname||'.'||tablename) DESC;

-- Check block count
SELECT COUNT(*) FROM blocks;

-- Check migration status
SELECT * FROM schema_migrations;
```

---

## Next Steps

✅ Your Token Optimizer is deployed!

**Recommended:**
1. Test with real traffic
2. Monitor latency and token savings
3. Enable LLMLingua compression for better results
4. Implement Phase 7: Ingestion API for RAG documents
5. Set up monitoring alerts
6. Configure auto-scaling if needed

**Documentation:**
- [SYSTEM_STATUS.md](SYSTEM_STATUS.md) - Full system overview
- [README.md](../README.md) - API documentation
- [CLAUDE.md](CLAUDE.md) - Implementation guide

**Support:**
- Issues: https://github.com/yourorg/token-optimizer/issues
- Health check: https://your-app.railway.app/v1/health
- Metrics: https://your-app.railway.app/v1/metrics
