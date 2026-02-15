# Railway Environment Variables

Set these in Railway Dashboard for your backend service:

## Required Variables

```env
# Core Authentication
MIDDLEWARE_API_KEY=<generate-with: openssl rand -hex 32>

# Infrastructure
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
SEMANTIC__SIMILARITY_THRESHOLD=0.3

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

# Dashboard (optional - set to false if not using)
DASHBOARD_ENABLED=false
MOCK_DASHBOARD=false
```

## Optional Variables (for /v1/chat endpoint)

```env
OPENAI_API_KEY=sk-...
ANTHROPIC_API_KEY=sk-ant-...
```

## Generate Secure API Key

```bash
openssl rand -hex 32
```

## Setup Steps

1. **Add Redis Service** (if not already added):
   - Railway Dashboard → New → Database → Redis

2. **Configure Backend Service**:
   - Copy all variables above to Railway → Backend Service → Variables
   - Replace `<generate-with...>` with actual generated key

3. **Deploy**:
   - Railway will auto-deploy on git push
   - Or manual deploy: `railway up`
