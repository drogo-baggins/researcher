#!/bin/bash

# ==============================================================================
# researcher - 初期セットアップスクリプト
# 初回のみ実行してください。以降は `./run.sh` で起動するだけです。
# ==============================================================================

set -e  # エラーで停止

echo "🚀 researcher セットアップを開始します..."
echo ""

# =============================================================================
# 1. Python環境のセットアップ
# =============================================================================

echo "📦 Python環境をセットアップ中..."

if [ ! -d "venv" ]; then
    echo "  仮想環境を作成中..."
    python3 -m venv venv
fi

# 仮想環境を有効化
source venv/bin/activate

echo "  依存パッケージをインストール中..."
pip install -e . > /dev/null 2>&1

echo "  ✓ Python環境準備完了"
echo ""

# =============================================================================
# 2. Ollamaモデルのセットアップ
# =============================================================================

echo "🤖 Ollamaモデルをセットアップ中..."

# モデルの確認
ollama_models=$(ollama list 2>/dev/null || echo "")

# デフォルトモデル (gpt-oss:20b) の確認
if ! echo "$ollama_models" | grep -q "gpt-oss:20b"; then
    echo "  gpt-oss:20b をインストール中（初回のみ、5-10分かかります）..."
    ollama pull gpt-oss:20b
else
    echo "  ✓ gpt-oss:20b はインストール済み"
fi

# 埋め込みモデル (nomic-embed-text) の確認
if ! echo "$ollama_models" | grep -q "nomic-embed-text"; then
    echo "  nomic-embed-text をインストール中（初回のみ、2-3分かかります）..."
    ollama pull nomic-embed-text
else
    echo "  ✓ nomic-embed-text はインストール済み"
fi

echo "  ✓ Ollamaモデル準備完了"
echo ""

# =============================================================================
# 3. SearXNGコンテナのセットアップ
# =============================================================================

echo "🔍 SearXNGをセットアップ中..."

if ! docker ps | grep -q searxng; then
    echo "  SearXNGコンテナを起動中..."
    docker run -d \
        --name searxng \
        -p 8888:8080 \
        -e SEARXNG_SECRET=your-random-secret \
        searxng/searxng > /dev/null 2>&1
    
    # 起動待機
    sleep 3
    echo "  ✓ SearXNGコンテナ起動完了"
else
    echo "  ✓ SearXNGはインストール済み"
fi

echo ""

# =============================================================================
# 4. 動作確認
# =============================================================================

echo "✅ セットアップ完了！"
echo ""
echo "【次のステップ】"
echo ""
echo "以下のコマンドで researcher を起動してください:"
echo ""
echo "  ./run.sh"
echo ""
echo "または、カスタムオプション付きで起動:"
echo ""
echo "  source venv/bin/activate"
echo "  researcher --auto-search-default --stream"
echo ""
