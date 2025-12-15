#!/bin/bash

# Fix SearXNG 403 Forbidden Error
# This script resolves SearXNG JSON API access issues

set -e

SEARXNG_CONTAINER="searxng"
SEARXNG_PORT="8888:8080"
SEARXNG_IMAGE="searxng/searxng"

echo "🔧 SearXNG 403エラー修正スクリプト"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"

# Step 1: Check Docker
echo ""
echo "1️⃣  Docker の確認中..."
if ! command -v docker &> /dev/null; then
    echo "❌ Docker がインストールされていません"
    echo "   https://docker.com からインストールしてください"
    exit 1
fi
echo "✅ Docker インストール済み"

# Step 2: Stop and remove existing container
echo ""
echo "2️⃣  既存の SearXNG コンテナをクリーンアップ..."
if docker ps -a --format '{{.Names}}' | grep -q "^${SEARXNG_CONTAINER}$"; then
    echo "   既存コンテナを停止..."
    docker stop "${SEARXNG_CONTAINER}" 2>/dev/null || true
    echo "   既存コンテナを削除..."
    docker rm "${SEARXNG_CONTAINER}" 2>/dev/null || true
    echo "✅ クリーンアップ完了"
else
    echo "   (既存コンテナなし)"
fi

# Step 3: Start SearXNG with settings mount
echo ""
echo "3️⃣  SearXNG コンテナを起動..."

SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
SETTINGS_FILE="${SCRIPT_DIR}/searxng_settings.yml"

# Check if custom settings file exists
if [ -f "$SETTINGS_FILE" ]; then
    echo "   カスタム設定ファイルを使用します"
    docker run -d \
        --name "${SEARXNG_CONTAINER}" \
        -p "${SEARXNG_PORT}" \
        -v "${SETTINGS_FILE}:/etc/searxng/settings.yml" \
        "${SEARXNG_IMAGE}"
else
    echo "   デフォルト設定で起動します"
    docker run -d \
        --name "${SEARXNG_CONTAINER}" \
        -p "${SEARXNG_PORT}" \
        "${SEARXNG_IMAGE}"
fi

echo "✅ コンテナ起動中..."

# Step 4: Wait for container to be ready
echo ""
echo "4️⃣  SearXNG の起動待機中..."
MAX_RETRY=30
RETRY=0

while [ $RETRY -lt $MAX_RETRY ]; do
    if curl -s "http://localhost:8888/" > /dev/null 2>&1; then
        echo "✅ SearXNG が応答しています"
        break
    fi
    echo "   待機中... ($((RETRY+1))/$MAX_RETRY)"
    sleep 1
    ((RETRY++))
done

if [ $RETRY -eq $MAX_RETRY ]; then
    echo "❌ SearXNG の起動タイムアウト"
    docker logs "${SEARXNG_CONTAINER}" | tail -20
    exit 1
fi

# Step 5: Test JSON API
echo ""
echo "5️⃣  JSON API をテスト中..."
sleep 2

RESPONSE=$(curl -s "http://localhost:8888/search?q=test&format=json" | head -c 100)

if echo "$RESPONSE" | grep -q "{"; then
    echo "✅ JSON API が正常に動作しています"
    echo "   レスポンス例:"
    curl -s "http://localhost:8888/search?q=test&format=json" | jq '.query' 2>/dev/null || echo "   (JSON形式で返却中...)"
    echo ""
    echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
    echo "🎉 修正完了！SearXNG は正常に動作しています"
    echo ""
    echo "再度実行してください:"
    echo "  ./run.sh"
else
    echo "⚠️  JSON API がまだ 403 を返しています"
    echo "   レスポンス:"
    echo "$RESPONSE" | head -5
    echo ""
    echo "代替方法:"
    echo "  1) 数秒待機してから再度試す"
    echo "  2) Docker Compose を使用する"
    echo "  3) Perplexica WebUI を使用する"
    exit 1
fi
