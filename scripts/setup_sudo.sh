#!/bin/bash
# Run with: sudo bash scripts/setup_sudo.sh
# This script handles all Phase 0 tasks requiring root access.

set -euo pipefail

echo "=== GhostPost Phase 0 — Sudo Setup ==="

# 1. Swap (2GB)
if swapon --show | grep -q '/swapfile'; then
    echo "[SKIP] Swap already active"
else
    echo "[SETUP] Creating 2GB swap..."
    fallocate -l 2G /swapfile
    chmod 600 /swapfile
    mkswap /swapfile
    swapon /swapfile
    if ! grep -q '/swapfile' /etc/fstab; then
        echo '/swapfile none swap sw 0 0' >> /etc/fstab
    fi
    echo "[OK] Swap enabled"
fi

# 2. Caddy config for ghostpost.work
CADDYFILE="/etc/caddy/Caddyfile"
if grep -q 'ghostpost.work' "$CADDYFILE"; then
    echo "[SKIP] ghostpost.work already in Caddyfile"
else
    echo "[SETUP] Adding ghostpost.work to Caddyfile..."
    cat >> "$CADDYFILE" << 'CADDY'

ghostpost.work {
	handle /api/* {
		reverse_proxy localhost:8000
	}
	handle /ws {
		reverse_proxy localhost:8000
	}
	handle {
		root * /home/athena/ghostpost/frontend/dist
		try_files {path} /index.html
		file_server
	}
	encode gzip
}
CADDY
    echo "[OK] Caddyfile updated"
    echo "[RELOAD] Reloading Caddy..."
    systemctl reload caddy
    echo "[OK] Caddy reloaded"
fi

echo ""
echo "=== Done! ==="
echo "Don't forget: DNS A record for ghostpost.work → 162.55.214.52"
