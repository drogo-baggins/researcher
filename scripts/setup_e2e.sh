#!/bin/bash
# Playwright E2Eテスト環境セットアップ

set -e

echo "🎭 Playwright E2Eテスト環境をセットアップ中..."

# 仮想環境の有効化確認
if [ -z "$VIRTUAL_ENV" ]; then
    echo "⚠️  仮想環境が有効化されていません。'source venv/bin/activate' を実行してください。"
    exit 1
fi

# Playwright依存関係のインストール
echo "📦 Playwright依存関係をインストール中..."
pip install -e ".[dev]"

# Playwrightブラウザのインストール
echo "🌐 Playwrightブラウザをインストール中..."
playwright install chromium

echo "✅ Playwright E2Eテスト環境のセットアップ完了！"
echo ""
echo "【テスト実行方法】"
echo "  pytest -m e2e                    # E2Eテストのみ実行"
echo "  pytest -m e2e --headed           # ブラウザを表示して実行"
echo "  pytest -m e2e --slowmo=1000      # スローモーション実行（デバッグ用）"
