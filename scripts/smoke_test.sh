#!/bin/bash
# GhostPost Phase 0 — Smoke Test
set -uo pipefail

PASS=0
FAIL=0
SKIP=0

check() {
    local name="$1"
    local result="$2"
    if [ "$result" -eq 0 ]; then
        echo "  [PASS] $name"
        ((PASS++))
    else
        echo "  [FAIL] $name"
        ((FAIL++))
    fi
}

skip() {
    echo "  [SKIP] $1 — $2"
    ((SKIP++))
}

echo "=== GhostPost Smoke Test ==="
echo ""

# Swap
if swapon --show 2>/dev/null | grep -q 'swapfile'; then
    check "Swap active" 0
else
    skip "Swap" "run: sudo bash scripts/setup_sudo.sh"
fi

# PostgreSQL
docker exec docker-db-1 psql -U ghostpost -d ghostpost -c "SELECT 1" > /dev/null 2>&1
check "PostgreSQL ghostpost DB" $?

# Redis
docker exec docker-redis-1 redis-cli PING > /dev/null 2>&1
check "Redis PING" $?

# FastAPI health
HEALTH=$(curl -sf http://127.0.0.1:8000/api/health 2>/dev/null)
if echo "$HEALTH" | grep -q '"status":"ok"'; then
    check "FastAPI /api/health" 0
else
    check "FastAPI /api/health" 1
fi

# CLI
/home/athena/ghostpost/.venv/bin/ghostpost --version > /dev/null 2>&1
check "ghostpost --version" $?

# Frontend build
if [ -f /home/athena/ghostpost/frontend/dist/index.html ]; then
    check "Frontend built (dist/index.html)" 0
else
    check "Frontend built (dist/index.html)" 1
fi

# PM2
pm2 describe ghostpost-api > /dev/null 2>&1
check "PM2 ghostpost-api" $?

# Caddy
if grep -q 'ghostpost.work' /etc/caddy/Caddyfile 2>/dev/null; then
    check "Caddy config" 0
else
    skip "Caddy config" "run: sudo bash scripts/setup_sudo.sh"
fi

echo ""
echo "=== Results: $PASS passed, $FAIL failed, $SKIP skipped ==="
