# MCP セットアップガイド

## ⚠️ MCP と Streamlit WebUI を使用する場合の重要な注意

Streamlit WebUI を通じて MCP ツールを使用する場合、**LLM がユーザープロンプト経由でファイルシステムにアクセスできます**。以下のセキュリティ上の注意を十分に理解した上で使用してください：

### 重要なセキュリティ考慮事項

1. **ローカルホストのみで実行してください**
   - WebUI を `0.0.0.0` や `0.0.0.0:8501` でバインドしないでください
   - デフォルトの `localhost:8501` にバインドされていることを確認してください

2. **MCP ツールを通じたファイルアクセス**
   - MCP ツール（特にファイルシステムサーバー）を有効にしている場合、LLM はユーザーのプロンプトに基づいてファイルを読み取り・作成・削除できます
   - 信頼できないまたは悪意のある可能性のあるプロンプトを実行しないでください

3. **認証機構がない**
   - Streamlit WebUI には認証機構がありません
   - ローカルネットワークに接続されたマシンから誰でもアクセス可能です
   - 共有ネットワーク環境では SSH トンネルやリバースプロキシで保護してください

詳細は [🔒 セキュリティガイド](security.md) と [📘 Streamlit WebUI ガイド](streamlit-guide.md) をご覧ください。

---

## MCP概要
Model Context Protocol (MCP) は LLM にコンテキストを提供するためのクライアント・サーバーアーキテクチャです。クライアントが LLM からの要求を転送し、標準入出力（stdio）や HTTP を通じてローカルまたはリモート MCP サーバーと双方向通信します。研究者向けに用意されたサーバー（ファイルシステム、Apple Notes、Calendar）を通じて、MCP によってファイルやシステムデータを直接参照できます。

## 前提条件
- macOS または macOS 互換環境
- Python 3.11 以上
- Node.js（MCP サーバーは Node.js ベース）
- 必要な macOS 権限: Notes、Calendar、ファイルアクセス（MCP サーバーが対象リソースを操作するため）

## MCPサーバーのインストール手順
### ファイルシステムサーバー
```bash
npm install -g @modelcontextprotocol/server-filesystem
```
または
```bash
git clone https://github.com/model-context-protocol/server-filesystem && cd server-filesystem && npm install && npm run build
```

### Apple Notesサーバー（macOS 専用）
```bash
git clone https://github.com/Siddhant-K-code/mcp-apple-notes
cd mcp-apple-notes
npm install
npm run build
```

### Calendarサーバー（macOS 専用）
```bash
npm install -g mcp-ical
```
またはベースリポジトリから手動でビルドしてください。

## サーバー設定例
- ファイルシステム
  ```bash
  node /usr/local/lib/node_modules/@modelcontextprotocol/server-filesystem/build/index.js /Users/username/Documents
  ```
- Notes
  ```bash
  node /path/to/mcp-apple-notes/build/index.js
  ```
- Calendar
  ```bash
  node /usr/local/lib/node_modules/mcp-ical/index.js
  ```

各サーバーの設定ファイルは JSON や TOML で表現でき、`researcher` では `MCP_SERVERS_CONFIG` 環境変数や CLI 引数 `--mcp-config` で指定できます。

## 権限設定
1. 「システム設定」→「プライバシーとセキュリティ」→「ファイルとフォルダ」で対象ディレクトリへのアクセス許可を追加
2. 「ノート」および「カレンダー」セクションで「researcher」または Node.js プロセスを許可
3. MCP サーバーを初回起動すると追加の権限ダイアログが表示されるので、必ず許可する

---

## MCPサーバーのカスタマイズと拡張

### 新しいサーバーの追加手順

#### 1. サーバーのインストール
```bash
# npm経由
npm install -g @modelcontextprotocol/server-[name]

# またはgit経由
git clone https://github.com/model-context-protocol/server-[name]
cd server-[name]
npm install && npm run build
```

#### 2. 起動コマンドの確認
```bash
# サーバー起動テスト
node /path/to/server/index.js [args]
```

#### 3. mcp_config.jsonへの追加
```json
{
  "new_server": {
    "command": "node",
    "args": ["/usr/local/lib/node_modules/@modelcontextprotocol/server-name/build/index.js"],
    "enabled": true
  }
}
```

#### 4. researcher起動時にテスト
```bash
researcher --enable-mcp --mcp-config mcp_config.json --stream
```

#### 5. /mcp-toolsで確認
```bash
You: /mcp-tools
[利用可能なツール一覧に new_server が表示される]
```

---

### 実践例: Slackサーバー追加

```json
{
  "slack": {
    "command": "node",
    "args": ["/usr/local/lib/node_modules/mcp-slack/index.js"],
    "env": {
      "SLACK_TOKEN": "xoxb-your-token-here"
    },
    "enabled": true
  }
}
```

**使用例**:
```bash
researcher --enable-mcp --mcp-config mcp_config.json --stream

You: /mcp slack.list_channels '{}'
[Slackチャンネル一覧が表示される]

You: /mcp slack.post_message '{"channel": "general", "text": "Hello from researcher!"}'
[メッセージがSlackに投稿される]
```

---

### 設定編集ユースケース

#### ケース1: ファイルシステムのルートを変更

デフォルトではホームディレクトリがルートですが、別のディレクトリに限定できます：

```json
{
  "filesystem": {
    "command": "node",
    "args": [
      "/usr/local/lib/node_modules/@modelcontextprotocol/server-filesystem/build/index.js",
      "/Users/username/Projects"
    ],
    "enabled": true
  }
}
```

実行:
```bash
researcher --enable-mcp --mcp-config mcp_config.json --stream

You: /mcp filesystem.list_directory '{"path": "."}'
[/Users/username/Projects のみアクセス可能]
```

#### ケース2: Notesサーバーを一時的に無効化

本番環境ではNotesへのアクセスを制限したい場合：

```json
{
  "notes": {
    "command": "node",
    "args": ["/path/to/mcp-apple-notes/build/index.js"],
    "enabled": false
  },
  "filesystem": {
    "enabled": true
  }
}
```

#### ケース3: 複数Calendarアカウント対応（環境変数で切り替え）

仕事用と個人用のカレンダーを使い分ける場合：

```bash
# .bashrc に設定
export CALENDAR_ACCOUNT=work

# researcher起動
researcher --enable-mcp --stream

# またはCLI引数で環境変数を設定
CALENDAR_ACCOUNT=personal researcher --enable-mcp --stream
```

対応する設定:
```json
{
  "calendar": {
    "command": "node",
    "args": ["/usr/local/lib/node_modules/mcp-ical/index.js"],
    "env": {
      "CALENDAR_ACCOUNT": "${CALENDAR_ACCOUNT:work}"
    },
    "enabled": true
  }
}
```

---

### デバッグTips

#### サーバーログの確認
```bash
# サーバーを手動起動してログを確認
node /path/to/server/build/index.js > server.log 2>&1

# ログを監視
tail -f server.log
```

#### --mcp-configでJSON文字列を直接渡す
```bash
researcher --mcp-config '{"filesystem": {"command": "node", "args": [...], "enabled": true}}' --stream
```

#### 権限エラーの詳細診断
```bash
# MCPサーバーのプロセスを確認
ps aux | grep mcp

# ファイルアクセス権限を確認
ls -la /Users/username/Documents

# macOS権限ログを確認
log show --predicate 'eventMessage contains[cd] "researcher"' --level debug
```

## 参考
- [Model Context Protocol](https://modelcontextprotocol.com)
- [MCP Apple Notes サーバー](https://github.com/Siddhant-K-code/mcp-apple-notes)

## サンプル設定
- `mcp_config.sample.json`: CLIや環境変数で使える JSON フォーマットの設定
- `mcp_config.sample.toml`: コメント付きで各フィールドの意味を記載したサンプル
