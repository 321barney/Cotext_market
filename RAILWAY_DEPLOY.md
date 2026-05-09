# Railway Deployment Guide

## 1. Create Project
- Go to railway.app
- New Project → Deploy from GitHub repo

## 2. Add PostgreSQL
- New → Database → Add PostgreSQL
- This creates DATABASE_URL automatically

## 3. Add Redis (optional, for caching)
- New → Database → Add Redis

## 4. Environment Variables
Add these in Railway Dashboard → Variables:

| Variable | Value | Source |
|----------|-------|--------|
| DATABASE_URL | (auto from PostgreSQL) | Railway |
| BASE_RPC | https://mainnet.base.org | Public RPC |
| ESCROW_CONTRACT_ADDRESS | (deploy contract first) | Your deploy |
| PLATFORM_WALLET | (your platform wallet) | Your wallet |
| ESCROW_PRIVATE_KEY | (platform private key) | Your key |
| OPENAI_API_KEY | (your OpenAI key) | OpenAI |
| ANTHROPIC_API_KEY | (your Anthropic key) | Anthropic |
| DEBUG | false | Fixed |
| LOG_DIR | /tmp/logs | Fixed |
| SECRET_KEY | (generate random) | `openssl rand -hex 32` |
| ALLOWED_ORIGINS | * | Allow all for agent access |

## 5. Deploy
- Railway auto-deploys on push to main
- Health check at /health

## 6. Run Migrations
After first deploy, run:
```
railway run -- python -c "import asyncio; from app.database import db; asyncio.run(db.connect()); asyncio.run(db.execute(open('migrations/001_init.sql').read()))"
```

## 7. Scale
- Add more instances in Railway dashboard
- Scheduler runs as separate worker service
