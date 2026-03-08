#!/bin/bash

# Ollama Container Start Script
# Starts an Ollama container with host model directory mounted.
# Supports both Podman (preferred) and Docker.
#
# Usage:
#   ./scripts/ollama-start.sh          # from project root
#   ./scripts/ollama-start.sh --force   # recreate even if running

set -euo pipefail

OLLAMA_CONTAINER="ollama"
OLLAMA_PORT="11434:11434"
OLLAMA_IMAGE="docker.io/ollama/ollama"
MAX_WAIT=30

FORCE=false
if [[ "${1:-}" == "--force" ]]; then
    FORCE=true
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
    echo "   https://podman.io または https://docker.com からインストールしてください"
    exit 1
fi

echo "🦙 Ollama 起動スクリプト (runtime: ${RUNTIME})"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"

# ─── Model Directory Detection ────────────────────────────────────────────────

# Default model directory per platform
if [[ -n "${OLLAMA_MODELS:-}" ]]; then
    HOST_MODELS_DIR="$OLLAMA_MODELS"
elif [[ "$(uname -s)" == "Darwin" ]]; then
    HOST_MODELS_DIR="$HOME/.ollama/models"
else
    HOST_MODELS_DIR="$HOME/.ollama/models"
fi

if [[ ! -d "$HOST_MODELS_DIR" ]]; then
    echo "⚠️  モデルディレクトリが見つかりません: ${HOST_MODELS_DIR}"
    echo "   OLLAMA_MODELS 環境変数で明示指定できます"
    echo "   ディレクトリを作成して続行します..."
    mkdir -p "$HOST_MODELS_DIR"
fi

echo "✓ モデルディレクトリ: ${HOST_MODELS_DIR}"

# ─── Existing Container Handling ──────────────────────────────────────────────

container_exists() {
    $RUNTIME ps -a --format '{{.Names}}' 2>/dev/null | grep -q "^${OLLAMA_CONTAINER}$"
}

container_running() {
    $RUNTIME ps --format '{{.Names}}' 2>/dev/null | grep -q "^${OLLAMA_CONTAINER}$"
}

if container_running && [[ "$FORCE" == "false" ]]; then
    echo "✓ Ollama コンテナは既に起動中です"
    echo "  再作成するには: $0 --force"

    echo ""
    echo "📡 API 確認中..."
    if curl -sf "http://localhost:11434/api/tags" -o /dev/null 2>/dev/null; then
        echo "✓ Ollama API 正常動作中"
        exit 0
    else
        echo "⚠️  Ollama API が応答しません。--force で再作成を推奨します"
        exit 1
    fi
fi

# Stop and remove existing container (idempotent)
if container_exists; then
    echo ""
    echo "🧹 既存コンテナをクリーンアップ..."
    $RUNTIME stop "${OLLAMA_CONTAINER}" 2>/dev/null || true
    $RUNTIME rm "${OLLAMA_CONTAINER}" 2>/dev/null || true
    echo "✓ クリーンアップ完了"
fi

# ─── Start Container ──────────────────────────────────────────────────────────

echo ""
echo "🚀 Ollama コンテナを起動中..."

$RUNTIME run -d \
    --name "${OLLAMA_CONTAINER}" \
    -p "${OLLAMA_PORT}" \
    -v "${HOST_MODELS_DIR}:/root/.ollama/models" \
    "${OLLAMA_IMAGE}"

echo "✓ コンテナ作成完了"

# ─── Health Check ─────────────────────────────────────────────────────────────

echo ""
echo "⏳ 起動待機中..."

READY=false
for i in $(seq 1 $MAX_WAIT); do
    if curl -sf "http://localhost:11434/" -o /dev/null 2>/dev/null; then
        READY=true
        break
    fi
    printf "  待機中... (%d/%d)\r" "$i" "$MAX_WAIT"
    sleep 1
done

if [[ "$READY" == "false" ]]; then
    echo ""
    echo "❌ Ollama の起動がタイムアウトしました (${MAX_WAIT}秒)"
    echo ""
    echo "ログ:"
    $RUNTIME logs "${OLLAMA_CONTAINER}" 2>&1 | tail -20
    exit 1
fi

echo "✓ Ollama が応答しています"

# ─── API Verification ─────────────────────────────────────────────────────────

echo ""
echo "📡 API を検証中..."

RESPONSE=$(curl -sf "http://localhost:11434/api/tags" 2>/dev/null || true)

if echo "$RESPONSE" | grep -q '"models"'; then
    echo "✓ Ollama API 正常動作"
    echo ""
    echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
    echo "🎉 Ollama 起動完了"
    echo ""
    echo "  URL:    http://localhost:11434"
    echo "  API:    http://localhost:11434/api/tags"
    echo "  モデル: ${HOST_MODELS_DIR}"
    echo "  停止:   ./scripts/ollama-stop.sh"
else
    echo "⚠️  Ollama API が正常に応答していません"
    echo "  レスポンス: ${RESPONSE:0:200}"
    exit 1
fi
