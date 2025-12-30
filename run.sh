#!/bin/bash

# ==============================================================================
# researcher - 起動スクリプト
# これだけで Ollama + SearXNG + researcher が起動します
# ==============================================================================

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

# ==============================================================================
# 1. 環境確認と初期化
# ==============================================================================

echo "🚀 researcher を起動中..."
echo ""

# Pythonバージョン確認
PYTHON_VERSION=$(python3 --version 2>&1 | awk '{print $2}')
echo "✓ Python $PYTHON_VERSION"

# 仮想環境がなければ作成
if [ ! -d "venv" ]; then
    echo "⚠️  仮想環境がありません。作成中..."
    python3 -m venv venv
    source venv/bin/activate
    pip install -e . > /dev/null 2>&1
    echo "✓ 仮想環境を作成しました"
else
    source venv/bin/activate
fi

echo ""

# ==============================================================================
# 2. Ollamaサーバーの起動確認
# ==============================================================================

echo "🤖 Ollamaの起動確認中..."

if ! pgrep -f "ollama serve" > /dev/null; then
    echo "  Ollamaサーバーを起動中..."
    
    # バックグラウンドで Ollama を起動
    OLLAMA_LOGDIR="${SCRIPT_DIR}/logs"
    mkdir -p "$OLLAMA_LOGDIR"
    nohup ollama serve > "$OLLAMA_LOGDIR/ollama.log" 2>&1 &
    
    # Ollama起動待機（最大30秒）
    for i in {1..30}; do
        if curl -s http://localhost:11434/api/tags > /dev/null 2>&1; then
            echo "  ✓ Ollamaサーバー起動完了"
            break
        fi
        sleep 1
    done
else
    echo "  ✓ Ollamaサーバーは既に起動しています"
fi

echo ""

# ==============================================================================
# 3. SearXNGコンテナの起動確認
# ==============================================================================

echo "🔍 SearXNGの起動確認中..."

if ! docker ps | grep -q searxng; then
    echo "  SearXNGコンテナを起動中..."
    docker run -d \
        --name searxng \
        -p 8888:8080 \
        -e SEARXNG_SECRET=your-random-secret \
        searxng/searxng > /dev/null 2>&1
    
    # SearXNG起動待機（最大30秒）
    for i in {1..30}; do
        if curl -s "http://localhost:8888/search?q=test&format=json" > /dev/null 2>&1; then
            echo "  ✓ SearXNGコンテナ起動完了"
            break
        fi
        sleep 1
    done
else
    echo "  ✓ SearXNGコンテナは既に起動しています"
fi

echo ""

# ==============================================================================
# 4. 環境変数の設定
# ==============================================================================

echo "⚙️  環境変数を設定中..."

# デフォルト環境変数を設定（OLLAMA_MODELは設定ファイルから取得）
if [ -z "$OLLAMA_MODEL" ]; then
    echo "  • OLLAMA_MODEL: (設定ファイルから取得)"
else
    export OLLAMA_MODEL
    echo "  • OLLAMA_MODEL=$OLLAMA_MODEL"
fi
export EMBEDDING_MODEL=${EMBEDDING_MODEL:-nomic-embed-text-v2-moe}
export SEARXNG_URL=${SEARXNG_URL:-http://localhost:8888}
export RELEVANCE_THRESHOLD=${RELEVANCE_THRESHOLD:-0.5}
echo "  • EMBEDDING_MODEL=$EMBEDDING_MODEL"
echo "  • SEARXNG_URL=$SEARXNG_URL"

echo ""

# ==============================================================================
# 5. researcher CLIの起動
# ==============================================================================

echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "researcher を起動します"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""

# CLI引数がない場合はデフォルト設定を使用
if [ $# -eq 0 ]; then
    researcher --model "$OLLAMA_MODEL" --auto-search-default --stream
else
    researcher "$@"
fi
