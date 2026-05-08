# Context Market v2 — Scripts

## Quick Commands

```bash
# 1. First time setup (installs everything)
./scripts/setup.sh

# 2. Start everything
./scripts/run.sh all

# 3. Check status
./scripts/run.sh status

# 4. Stop everything
./scripts/run.sh stop
```

## Available Scripts

### `setup.sh` — Requirements & Setup
Installs Python venv, dependencies, database, checks env vars.

```bash
./scripts/setup.sh          # Dev mode (default)
./scripts/setup.sh --prod   # Production mode
```

**What it does:**
- Checks Python 3.12+
- Creates virtual environment
- Installs all Python packages
- Creates `.env` from `.env.example`
- Verifies required env vars
- Sets up PostgreSQL database + pgvector
- Runs migrations
- Checks contract deployment status

### `run.sh` — Service Management
Start/stop/check backend, scheduler, and frontend.

```bash
./scripts/run.sh backend    # Start FastAPI on :8000
./scripts/run.sh scheduler  # Start settlement scheduler
./scripts/run.sh frontend   # Start Next.js on :3000
./scripts/run.sh all        # Start everything
./scripts/run.sh status     # Check what's running
./scripts/run.sh stop       # Stop all services
./scripts/run.sh test       # Run pytest
```

### `deploy.py` — Contract Deployment
Deploy escrow contract to Base.

```bash
cd contracts

# Deploy to Sepolia (testnet)
export PLATFORM_WALLET=0x...
export ESCROW_PRIVATE_KEY=0x...
python deploy.py --testnet

# Deploy to mainnet (production)
python deploy.py

# Verify on Basescan
python deploy.py --testnet --verify --api-key YOUR_BASESCAN_KEY
```

## Environment Variables

Copy `.env.example` → `.env` and fill in:

| Variable | Required | Description |
|----------|----------|-------------|
| `DATABASE_URL` | ✅ | PostgreSQL connection string |
| `OPENAI_API_KEY` | ❌ | For LLM synthesis (fallback to Anthropic or extractive) |
| `ANTHROPIC_API_KEY` | ❌ | Claude fallback for synthesis |
| `ESCROW_CONTRACT_ADDRESS` | ⚠️ | Deployed contract address (required for payments) |
| `PLATFORM_WALLET` | ✅ | Platform wallet address (receives 10% fee) |
| `ESCROW_PRIVATE_KEY` | ⚠️ | Platform private key (required for settlement) |
| `BASE_RPC` | ❌ | Base mainnet RPC (default: https://mainnet.base.org) |
| `BASE_SEPOLIA_RPC` | ❌ | Base testnet RPC (default: https://sepolia.base.org) |
| `LOG_DIR` | ❌ | Log directory (default: workspace path) |

## First-Time Setup Checklist

```bash
# 1. Clone / navigate to project
cd innovations/context-market-v2

# 2. Run setup
./scripts/setup.sh

# 3. Edit .env
nano backend/.env

# 4. Deploy contract (if not already deployed)
cd contracts
export PLATFORM_WALLET=0xYOUR_ADDRESS
export ESCROW_PRIVATE_KEY=0xYOUR_KEY
python deploy.py --testnet

# 5. Update .env with contract address
# ESCROW_CONTRACT_ADDRESS=0x...

# 6. Start services
./scripts/run.sh all

# 7. Test
./scripts/run.sh test
```

## Troubleshooting

**"Database connection failed"**
```bash
# Ensure PostgreSQL is running
sudo service postgresql start  # Linux
brew services start postgresql  # macOS

# Create database manually
psql -U postgres -c "CREATE DATABASE contextmarket;"
```

**"pgvector extension not found"**
```bash
# Install pgvector
# macOS: brew install pgvector
# Linux: see https://github.com/pgvector/pgvector#installation
# Then: psql -d contextmarket -c "CREATE EXTENSION vector;"
```

**"Contract deployment fails"**
- Ensure wallet has Sepolia ETH (from Base faucet)
- Check `BASE_SEPOLIA_RPC` is accessible
- Verify `PLATFORM_WALLET` and `ESCROW_PRIVATE_KEY` are set

**"Backend won't start"**
```bash
cd backend
source venv/bin/activate
uvicorn app.main:app --reload --log-level debug
```
