#!/bin/bash

# SearXNG Container Start Script
# Starts a SearXNG container with JSON API enabled via volume-mounted settings.
# Supports both Podman (preferred) and Docker.
#
# Usage:
#   ./scripts/searxng-start.sh          # from project root
#   ./scripts/searxng-start.sh --force   # recreate even if running

set -euo pipefail

SEARXNG_CONTAINER="searxng"
SEARXNG_PORT="8888:8080"
SEARXNG_IMAGE="docker.io/searxng/searxng"
MAX_WAIT=30

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"
SETTINGS_FILE="${PROJECT_ROOT}/searxng_settings.yml"

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

echo "🐋 SearXNG 起動スクリプト (runtime: ${RUNTIME})"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"

# ─── Settings File Check ──────────────────────────────────────────────────────

if [[ ! -f "$SETTINGS_FILE" ]]; then
    echo "❌ 設定ファイルが見つかりません: ${SETTINGS_FILE}"
    echo "   プロジェクトルートから実行してください"
    exit 1
fi

echo "✓ 設定ファイル: ${SETTINGS_FILE}"

# ─── Existing Container Handling ──────────────────────────────────────────────

container_exists() {
    $RUNTIME ps -a --format '{{.Names}}' 2>/dev/null | grep -q "^${SEARXNG_CONTAINER}$"
}

container_running() {
    $RUNTIME ps --format '{{.Names}}' 2>/dev/null | grep -q "^${SEARXNG_CONTAINER}$"
}

if container_running && [[ "$FORCE" == "false" ]]; then
    echo "✓ SearXNG コンテナは既に起動中です"
    echo "  再作成するには: $0 --force"

    # Even if running, verify JSON API works
    echo ""
    echo "📡 JSON API 確認中..."
    if curl -sf "http://localhost:8888/search?q=test&format=json" -o /dev/null 2>/dev/null; then
        echo "✓ JSON API 正常動作中"
        exit 0
    else
        echo "⚠️  JSON API が応答しません。--force で再作成を推奨します"
        exit 1
    fi
fi

# Stop and remove existing container (idempotent)
if container_exists; then
    echo ""
    echo "🧹 既存コンテナをクリーンアップ..."
    $RUNTIME stop "${SEARXNG_CONTAINER}" 2>/dev/null || true
    $RUNTIME rm "${SEARXNG_CONTAINER}" 2>/dev/null || true
    echo "✓ クリーンアップ完了"
fi

# ─── Start Container ──────────────────────────────────────────────────────────

echo ""
echo "🚀 SearXNG コンテナを起動中..."

$RUNTIME run -d \
    --name "${SEARXNG_CONTAINER}" \
    -p "${SEARXNG_PORT}" \
    -v "${SETTINGS_FILE}:/etc/searxng/settings.yml:ro" \
    "${SEARXNG_IMAGE}"

echo "✓ コンテナ作成完了"

# ─── Health Check ─────────────────────────────────────────────────────────────

echo ""
echo "⏳ 起動待機中..."

READY=false
for i in $(seq 1 $MAX_WAIT); do
    if curl -sf "http://localhost:8888/" -o /dev/null 2>/dev/null; then
        READY=true
        break
    fi
    printf "  待機中... (%d/%d)\r" "$i" "$MAX_WAIT"
    sleep 1
done

if [[ "$READY" == "false" ]]; then
    echo ""
    echo "❌ SearXNG の起動がタイムアウトしました (${MAX_WAIT}秒)"
    echo ""
    echo "ログ:"
    $RUNTIME logs "${SEARXNG_CONTAINER}" 2>&1 | tail -20
    exit 1
fi

echo "✓ SearXNG が応答しています"

# ─── JSON API Verification ────────────────────────────────────────────────────

echo ""
echo "📡 JSON API を検証中..."
sleep 2

RESPONSE=$(curl -sf "http://localhost:8888/search?q=test&format=json" 2>/dev/null || true)

if echo "$RESPONSE" | grep -q '"results"'; then
    echo "✓ JSON API 正常動作"
    echo ""
    echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
    echo "🎉 SearXNG 起動完了"
    echo ""
    echo "  URL:      http://localhost:8888"
    echo "  JSON API: http://localhost:8888/search?q=test&format=json"
    echo "  停止:     ./scripts/searxng-stop.sh"
else
    echo "⚠️  JSON API が正常に応答していません"
    echo "  レスポンス: ${RESPONSE:0:200}"
    echo ""
    echo "  設定ファイルの search.formats に json が含まれているか確認してください"
    exit 1
fi
