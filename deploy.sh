#!/bin/bash
set -e

# ヘルプメッセージ
if [ "$1" = "-h" ] || [ "$1" = "--help" ]; then
  echo "使用法: ./deploy.sh [OPTIONS]"
  echo ""
  echo "オプション:"
  echo "  --init      設定ファイルも含めて初回デプロイ"
  echo "  --restart   デプロイ後にWebUIプロセスを自動再起動"
  echo "  -h, --help  このヘルプメッセージを表示"
  echo ""
  echo "例:"
  echo "  ./deploy.sh              # 通常のデプロイ"
  echo "  ./deploy.sh --init       # 初回デプロイ（設定ファイル含む）"
  echo "  ./deploy.sh --restart    # デプロイ後にWebUI再起動"
  echo "  ./deploy.sh --init --restart  # 初回デプロイ＋WebUI再起動"
  exit 0
fi

# production.yamlの存在確認
if [ ! -f ~/.researcher/production.yaml ]; then
  echo "❌ エラー: ~/.researcher/production.yaml が見つかりません" >&2
  echo "このファイルを作成して、以下の形式で path を指定してください:" >&2
  echo "  path: /Users/furuta/production/researcher" >&2
  exit 1
fi

# production.yamlからpathを読み取る
DEST=$(grep '^path:' ~/.researcher/production.yaml | sed 's/path: *//' | xargs)

# DESTが空でないか確認
if [ -z "$DEST" ]; then
  echo "❌ エラー: ~/.researcher/production.yaml に path フィールドが見つかりません" >&2
  echo "以下の形式で path を指定してください:" >&2
  echo "  path: /Users/furuta/production/researcher" >&2
  exit 1
fi

# デプロイ先ディレクトリを作成
mkdir -p "$DEST"

# コアファイルをコピー
echo "コピー中: $DEST"
cp -r src "$DEST/"
cp pyproject.toml setup.sh run.sh pytest.ini README.md "$DEST/"
[ -d docs ] && cp -r docs "$DEST/"

# --initオプションがあれば設定ファイルもコピー
if [ "$1" = "--init" ]; then
  echo "設定ファイルもコピー中..."
  cp searxng_settings.yml setenv.sh mcp_config.sample.* fix_searxng.sh "$DEST/" 2>/dev/null || true
fi

# 実行権限を設定
chmod +x "$DEST/setup.sh" "$DEST/run.sh" 2>/dev/null || true

# --restartオプションがあればWebUIプロセスを再起動
if [ "$1" = "--restart" ] || [ "$2" = "--restart" ]; then
  echo "WebUIプロセスを再起動中..."
  
  # 既存のWebUIプロセスを探して停止
  WEBUI_PID=$(ps aux | grep "streamlit run.*researcher.*webui.py" | grep -v grep | awk '{print $2}')
  
  if [ -n "$WEBUI_PID" ]; then
    echo "  既存のプロセス (PID: $WEBUI_PID) を停止中..."
    kill $WEBUI_PID 2>/dev/null || true
    sleep 2
    
    # プロセスが完全に停止するまで待機
    for i in {1..5}; do
      if ! ps -p $WEBUI_PID > /dev/null 2>&1; then
        break
      fi
      sleep 1
    done
    
    # まだ実行中なら強制終了
    if ps -p $WEBUI_PID > /dev/null 2>&1; then
      echo "  強制終了中..."
      kill -9 $WEBUI_PID 2>/dev/null || true
      sleep 1
    fi
    
    echo "  プロセスを停止しました"
  else
    echo "  実行中のWebUIプロセスが見つかりません"
  fi
  
  # WebUIを再起動
  echo "  WebUIを起動中..."
  cd "$DEST"
  nohup ./run.sh --ui > /dev/null 2>&1 &
  sleep 3
  
  NEW_PID=$(ps aux | grep "streamlit run.*researcher.*webui.py" | grep -v grep | awk '{print $2}')
  if [ -n "$NEW_PID" ]; then
    echo "  ✅ WebUI起動完了 (PID: $NEW_PID)"
  else
    echo "  ⚠️  WebUIの起動に失敗した可能性があります"
  fi
fi

echo "✅ デプロイ完了: $DEST"
