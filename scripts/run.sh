#!/usr/bin/env bash
# Context Market v2 — Quick Start Script
# Usage: ./run.sh [backend|scheduler|frontend|all]

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"
BACKEND_DIR="$PROJECT_ROOT/backend"

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

log() { echo -e "${BLUE}[run]${NC} $1"; }
ok() { echo -e "${GREEN}[ok]${NC} $1"; }
warn() { echo -e "${YELLOW}[warn]${NC} $1"; }
err() { echo -e "${RED}[err]${NC} $1"; }

CMD="${1:-all}"

check_venv() {
    if [[ ! -d "$BACKEND_DIR/venv" ]]; then
        err "Virtual environment not found. Run ./setup.sh first"
        exit 1
    fi
    source "$BACKEND_DIR/venv/bin/activate"
}

start_backend() {
    log "Starting backend server..."
    check_venv
    cd "$BACKEND_DIR"
    
    # Check .env
    if [[ ! -f ".env" ]]; then
        err ".env not found. Run ./setup.sh first"
        exit 1
    fi
    
    # Check if already running
    if pgrep -f "uvicorn app.main:app" >/dev/null; then
        warn "Backend already running"
        return
    fi
    
    export PYTHONPATH="$BACKEND_DIR"
    uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload &
    sleep 2
    
    if pgrep -f "uvicorn app.main:app" >/dev/null; then
        ok "Backend running at http://localhost:8000"
        ok "API docs at http://localhost:8000/docs"
    else
        err "Backend failed to start"
        exit 1
    fi
}

start_scheduler() {
    log "Starting settlement scheduler..."
    check_venv
    cd "$BACKEND_DIR"
    
    if pgrep -f "python -m app.scheduler --loop" >/dev/null; then
        warn "Scheduler already running"
        return
    fi
    
    export PYTHONPATH="$BACKEND_DIR"
    python -m app.scheduler --loop &
    sleep 1
    
    if pgrep -f "python -m app.scheduler --loop" >/dev/null; then
        ok "Scheduler running (settles every hour)"
    else
        err "Scheduler failed to start"
        exit 1
    fi
}

start_frontend() {
    if [[ ! -d "$PROJECT_ROOT/frontend" ]]; then
        warn "Frontend directory not found"
        return
    fi
    
    log "Starting frontend..."
    cd "$PROJECT_ROOT/frontend"
    
    if [[ ! -d "node_modules" ]]; then
        err "node_modules not found. Run npm install first"
        exit 1
    fi
    
    if pgrep -f "next dev" >/dev/null; then
        warn "Frontend already running"
        return
    fi
    
    npm run dev &
    sleep 3
    
    if pgrep -f "next dev" >/dev/null; then
        ok "Frontend running at http://localhost:3000"
    else
        err "Frontend failed to start"
        exit 1
    fi
}

status() {
    echo "=== Context Market Status ==="
    
    if pgrep -f "uvicorn app.main:app" >/dev/null; then
        ok "Backend: RUNNING"
    else
        warn "Backend: STOPPED"
    fi
    
    if pgrep -f "python -m app.scheduler --loop" >/dev/null; then
        ok "Scheduler: RUNNING"
    else
        warn "Scheduler: STOPPED"
    fi
    
    if pgrep -f "next dev" >/dev/null; then
        ok "Frontend: RUNNING"
    else
        warn "Frontend: STOPPED"
    fi
    
    echo
    echo "API:      http://localhost:8000"
    echo "Docs:     http://localhost:8000/docs"
    echo "Frontend: http://localhost:3000"
}

stop_all() {
    log "Stopping all services..."
    pkill -f "uvicorn app.main:app" 2>/dev/null || true
    pkill -f "python -m app.scheduler --loop" 2>/dev/null || true
    pkill -f "next dev" 2>/dev/null || true
    ok "All services stopped"
}

test_api() {
    log "Running API tests..."
    check_venv
    cd "$BACKEND_DIR"
    
    if [[ -d "tests" ]]; then
        pytest tests/ -v
        ok "Tests complete"
    else
        warn "No tests/ directory found"
    fi
}

case "$CMD" in
    backend)
        start_backend
        ;;
    scheduler)
        start_scheduler
        ;;
    frontend)
        start_frontend
        ;;
    all)
        start_backend
        start_scheduler
        start_frontend
        echo
        ok "Context Market v2 is running!"
        status
        ;;
    status)
        status
        ;;
    stop)
        stop_all
        ;;
    test)
        test_api
        ;;
    *)
        echo "Usage: ./run.sh [backend|scheduler|frontend|all|status|stop|test]"
        echo
        echo "Commands:"
        echo "  backend   — Start FastAPI server"
        echo "  scheduler — Start settlement scheduler"
        echo "  frontend  — Start Next.js dev server"
        echo "  all       — Start everything"
        echo "  status    — Check running services"
        echo "  stop      — Stop all services"
        echo "  test      — Run API tests"
        exit 1
        ;;
esac
