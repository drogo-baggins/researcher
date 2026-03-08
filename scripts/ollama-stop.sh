#!/bin/bash

# Ollama Container Stop Script
# Stops and removes the Ollama container.
# Supports both Podman and Docker.
#
# Usage:
#   ./scripts/ollama-stop.sh           # stop and remove
#   ./scripts/ollama-stop.sh --keep    # stop only (don't remove)

set -euo pipefail

OLLAMA_CONTAINER="ollama"

KEEP=false
if [[ "${1:-}" == "--keep" ]]; then
    KEEP=true
fi

# ─── Runtime Detection ────────────────────────────────────────────────────────

detect_runtime() {
    if command -v podman &>/dev/null; then
        echo "podman"
    elif command -v docker &>/dev/null; then
        echo "docker"
    else
        echo ""
    fi
}

RUNTIME=$(detect_runtime)

if [[ -z "$RUNTIME" ]]; then
    echo "❌ podman も docker もインストールされていません"
    exit 1
fi

echo "🛑 Ollama 停止スクリプト (runtime: ${RUNTIME})"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"

# ─── Container Check ──────────────────────────────────────────────────────────

container_exists() {
    $RUNTIME ps -a --format '{{.Names}}' 2>/dev/null | grep -q "^${OLLAMA_CONTAINER}$"
}

container_running() {
    $RUNTIME ps --format '{{.Names}}' 2>/dev/null | grep -q "^${OLLAMA_CONTAINER}$"
}

if ! container_exists; then
    echo "ℹ️  Ollama コンテナは存在しません"
    exit 0
fi

# ─── Stop ─────────────────────────────────────────────────────────────────────

if container_running; then
    echo "⏹️  コンテナを停止中..."
    $RUNTIME stop "${OLLAMA_CONTAINER}"
    echo "✓ 停止完了"
else
    echo "ℹ️  コンテナは既に停止しています"
fi

# ─── Remove ───────────────────────────────────────────────────────────────────

if [[ "$KEEP" == "false" ]]; then
    echo "🗑️  コンテナを削除中..."
    $RUNTIME rm "${OLLAMA_CONTAINER}"
    echo "✓ 削除完了"
else
    echo "ℹ️  --keep が指定されたため、コンテナは保持されます"
    echo "  再起動: ${RUNTIME} start ${OLLAMA_CONTAINER}"
fi

echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "✓ 完了"
