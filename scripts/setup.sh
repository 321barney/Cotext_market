#!/usr/bin/env bash
# Context Market v2 — Setup & Requirements Script
# Usage: ./setup.sh [--dev|--prod|--test]

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"
BACKEND_DIR="$PROJECT_ROOT/backend"
CONTRACTS_DIR="$PROJECT_ROOT/contracts"
MODE="${1:-dev}"

echo "╔══════════════════════════════════════════════════════════════╗"
echo "║     Context Market v2 — Setup & Requirements Installer       ║"
echo "║                        Mode: $MODE                           ║"
echo "╚══════════════════════════════════════════════════════════════╝"
echo

# ─── Colors ───
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

log_info() { echo -e "${BLUE}[INFO]${NC} $1"; }
log_ok()   { echo -e "${GREEN}[OK]${NC} $1"; }
log_warn() { echo -e "${YELLOW}[WARN]${NC} $1"; }
log_err()  { echo -e "${RED}[ERROR]${NC} $1"; }

# ─── 1. Python Check ───
echo "▸ Checking Python..."
PYTHON_CMD=""
for cmd in python3.12 python3 python; do
    if command -v "$cmd" &>/dev/null; then
        PYTHON_CMD="$cmd"
        break
    fi
done

if [[ -z "$PYTHON_CMD" ]]; then
    log_err "Python not found. Install Python 3.12+"
    exit 1
fi

PY_VERSION=$($PYTHON_CMD --version 2>&1 | cut -d' ' -f2 | cut -d'.' -f1,2)
PY_MAJOR=$(echo "$PY_VERSION" | cut -d'.' -f1)
PY_MINOR=$(echo "$PY_VERSION" | cut -d'.' -f2)

if [[ "$PY_MAJOR" -lt 3 ]] || ([[ "$PY_MAJOR" -eq 3 ]] && [[ "$PY_MINOR" -lt 12 ]]); then
    log_warn "Python $PY_VERSION detected. 3.12+ recommended."
    read -p "Continue anyway? (y/n) " -n 1 -r
    echo
    [[ ! $REPLY =~ ^[Yy]$ ]] && exit 1
else
    log_ok "Python $PY_VERSION"
fi

# ─── 2. Node.js Check (for frontend) ───
echo "▸ Checking Node.js..."
if command -v node &>/dev/null; then
    NODE_VERSION=$(node --version | cut -d'v' -f2)
    log_ok "Node.js $NODE_VERSION"
else
    log_warn "Node.js not found. Frontend build skipped."
fi

# ─── 3. PostgreSQL Check ───
echo "▸ Checking PostgreSQL..."
if command -v psql &>/dev/null; then
    PSQL_VERSION=$(psql --version | head -1 | awk '{print $3}')
    log_ok "PostgreSQL client $PSQL_VERSION"
else
    log_warn "psql not found. You'll need PostgreSQL 14+ with pgvector extension."
fi

# ─── 4. Create Virtual Environment ───
echo "▸ Setting up Python virtual environment..."
cd "$BACKEND_DIR"

if [[ ! -d "venv" ]]; then
    $PYTHON_CMD -m venv venv
    log_ok "Created venv/"
else
    log_info "venv/ already exists"
fi

source venv/bin/activate

# ─── 5. Install Dependencies ───
echo "▸ Installing Python dependencies..."
pip install --upgrade pip -q

pip install -q \
    fastapi uvicorn[standard] \
    pydantic pydantic-settings \
    asyncpg pgvector \
    sentence-transformers torch \
    web3 \
    openai anthropic \
    httpx \
    python-dotenv

log_ok "Python packages installed"

# ─── 6. Environment File ───
echo "▸ Checking environment configuration..."
if [[ ! -f ".env" ]]; then
    if [[ -f ".env.example" ]]; then
        cp .env.example .env
        log_warn ".env created from .env.example — EDIT IT BEFORE RUNNING"
    else
        log_err ".env.example not found"
        exit 1
    fi
else
    log_info ".env already exists"
fi

# ─── 7. Verify Required Env Vars ───
echo "▸ Verifying environment variables..."
source .env 2>/dev/null || true

REQUIRED_VARS=("DATABASE_URL")
OPTIONAL_VARS=("OPENAI_API_KEY" "ANTHROPIC_API_KEY" "ESCROW_CONTRACT_ADDRESS" "PLATFORM_WALLET" "ESCROW_PRIVATE_KEY")

MISSING_REQUIRED=0
for var in "${REQUIRED_VARS[@]}"; do
    val="${!var:-}"
    if [[ -z "$val" ]] || [[ "$val" == "0x..." ]] || [[ "$val" == "sk-..." ]]; then
        log_err "$var is not set (check .env)"
        MISSING_REQUIRED=1
    else
        log_ok "$var is set"
    fi
done

for var in "${OPTIONAL_VARS[@]}"; do
    val="${!var:-}"
    if [[ -z "$val" ]] || [[ "$val" == "0x..." ]] || [[ "$val" == "sk-..." ]]; then
        log_warn "$var is not set — some features will be degraded"
    else
        log_ok "$var is set"
    fi
done

if [[ $MISSING_REQUIRED -eq 1 ]]; then
    log_err "Required variables missing. Edit .env and re-run."
    exit 1
fi

# ─── 8. Database Setup ───
echo "▸ Setting up database..."
DB_URL="${DATABASE_URL:-postgresql://postgres:postgres@localhost:5432/contextmarket}"

# Extract DB name
DB_NAME=$(echo "$DB_URL" | sed -n 's/.*\/\([^?]*\).*/\1/p')
DB_HOST=$(echo "$DB_URL" | sed -n 's/.*@\([^:]*\).*/\1/p')
DB_USER=$(echo "$DB_URL" | sed -n 's/postgresql:\/\/\([^:]*\).*/\1/p')

log_info "Target DB: $DB_NAME on $DB_HOST"

# Check if database exists
if ! psql "$DB_URL" -c "SELECT 1" &>/dev/null; then
    log_warn "Database '$DB_NAME' not accessible. Creating..."
    # Try to create via postgres db
    if psql "postgresql://$DB_USER@$DB_HOST/postgres" -c "CREATE DATABASE $DB_NAME" 2>/dev/null; then
        log_ok "Created database $DB_NAME"
    else
        log_err "Could not create database. Ensure PostgreSQL is running and credentials are correct."
        exit 1
    fi
else
    log_ok "Database '$DB_NAME' is accessible"
fi

# Enable pgvector
if psql "$DB_URL" -c "CREATE EXTENSION IF NOT EXISTS vector;" 2>/dev/null; then
    log_ok "pgvector extension ready"
else
    log_warn "pgvector extension failed — may need: CREATE EXTENSION vector; manually"
fi

# Run migrations
if [[ -f "migrations/001_init.sql" ]]; then
    log_info "Running migration 001_init.sql..."
    psql "$DB_URL" -f migrations/001_init.sql
    log_ok "Migration complete"
else
    log_err "Migration file not found"
    exit 1
fi

# ─── 9. Contract Check ───
echo "▸ Checking smart contract..."
cd "$CONTRACTS_DIR"

if [[ -z "${ESCROW_CONTRACT_ADDRESS:-}" ]] || [[ "$ESCROW_CONTRACT_ADDRESS" == "0x..." ]]; then
    log_warn "ESCROW_CONTRACT_ADDRESS not set"
    echo
    echo "  To deploy to Base Sepolia:"
    echo "    export BASE_SEPOLIA_RPC=https://sepolia.base.org"
    echo "    export PRIVATE_KEY=your_deployer_key"
    echo "    python deploy.py --network sepolia"
    echo
    echo "  Then update .env with the deployed address."
else
    log_ok "Contract address configured: ${ESCROW_CONTRACT_ADDRESS:0:10}..."
fi

# ─── 10. Directory Structure ───
echo "▸ Ensuring directory structure..."
mkdir -p "$PROJECT_ROOT/logs/settlements"
mkdir -p "$PROJECT_ROOT/logs/disputes"
log_ok "Log directories ready"

# ─── 11. Frontend Setup (if Node available) ───
if command -v npm &>/dev/null && [[ -d "$PROJECT_ROOT/frontend" ]]; then
    echo "▸ Setting up frontend..."
    cd "$PROJECT_ROOT/frontend"
    if [[ ! -d "node_modules" ]]; then
        npm install
        log_ok "Frontend dependencies installed"
    else
        log_info "node_modules/ already exists"
    fi
fi

# ─── 12. Final Status ───
echo
echo "╔══════════════════════════════════════════════════════════════╗"
echo "║                    SETUP COMPLETE                            ║"
echo "╚══════════════════════════════════════════════════════════════╝"
echo

if [[ $MISSING_REQUIRED -eq 0 ]]; then
    echo -e "${GREEN}✓ All required components are ready${NC}"
    echo
    echo "  Start backend:  cd backend && source venv/bin/activate && uvicorn app.main:app --reload"
    echo "  Run scheduler:  cd backend && source venv/bin/activate && python -m app.scheduler --loop"
    echo "  Run tests:      cd backend && source venv/bin/activate && pytest tests/"
    echo
    if [[ -z "${ESCROW_CONTRACT_ADDRESS:-}" ]] || [[ "$ESCROW_CONTRACT_ADDRESS" == "0x..." ]]; then
        echo -e "${YELLOW}⚠ Deploy contract before launching:${NC}"
        echo "     cd contracts && python deploy.py --network sepolia"
        echo "     # Then update ESCROW_CONTRACT_ADDRESS in .env"
    fi
else
    echo -e "${RED}✗ Some required components are missing${NC}"
    echo "  Edit .env and re-run: ./scripts/setup.sh"
fi

echo
log_info "Need help? Check: $PROJECT_ROOT/README.md"
