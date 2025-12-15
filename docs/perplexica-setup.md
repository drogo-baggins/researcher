# Perplexica Setup for researcher

## Prerequisites

- **Docker** and **Docker Compose** installed and available in your `PATH`.
- **Git** to clone the Perplexica repository.
- **Ollama** installed locally (see [https://ollama.com/](https://ollama.com/)) and any models you plan to use (e.g. `llama3`, `nomic-embed-text`).
- **SearXNG** either running locally or via Docker (Perplexica ships with a bundled instance).

## Clone and prepare Perplexica

```bash
git clone https://github.com/ItzCrazyKns/Perplexica.git
cd Perplexica
cp sample.config.toml config.toml
```

### Configure `config.toml`

- In the `[ollama]` section, point to your Ollama API. On macOS running Ollama locally, use `http://host.docker.internal:11434`. On Linux, use the machine's IP or `http://localhost:11434` if Ollama is exposed directly.
- Ensure the `[searxng]` section points to the same SearXNG backend you are running (`http://localhost:8888` by default).
- Set `embedding_model = "nomic-embed-text"` (or another Ollama embedding model you pulled) so Perplexica can rank search results.

## Pull required Ollama models

```bash
ollama pull llama3:latest
ollama pull nomic-embed-text:latest
```

## Start Perplexica with Docker Compose

```bash
docker compose up -d
```

Perplexica exposes a Web UI at `http://localhost:3000`. Open it in your browser and verify that the Ollama connection is green and that search sources are available.

## Troubleshooting

- **Ollama API unreachable**: On macOS the Docker container must access the host via `host.docker.internal`. Ensure `OLLAMA` URL uses that host and port `11434`.
- **SearXNG JSON disabled**: Confirm the JSON formatter is enabled inside the embedded SearXNG (or your custom instance) so Perplexica can parse results.
- **Logs**: `docker compose logs -f` shows both Perplexica and SearXNG logs for debugging.

## CLI/WebUI同期検証の詳細手順

### 検証目的
Perplexica WebUI と researcher CLI が同じバックエンドを共有し、同等の結果を生成することを確認します。

### ステップ1: 環境準備
```bash
# ターミナル1: Ollamaサーバー起動
ollama serve

# ターミナル2: SearXNG起動
docker run -d --name searxng -p 8888:8080 searxng/searxng

# ターミナル3: Perplexica起動
cd Perplexica
docker compose up -d

# ターミナル4: researcher CLI起動
cd researcher
source venv/bin/activate
researcher --auto-search-default --stream
```

### ステップ2: 同一クエリの実行

**WebUIでテスト**:
1. `http://localhost:3000` をブラウザで開く
2. テストクエリを入力: "What is the latest on Ukraine?"
3. 結果をメモ: 検索キーワード、取得URL、回答内容

**CLIでテスト**:
```bash
You: What is the latest on Ukraine?
[自動検索実行]
[結果表示]
```

### ステップ3: 結果比較

以下の項目を確認:

| 項目 | WebUI | CLI | 一致 |
|------|-------|-----|------|
| 検索キーワード | ... | ... | ✓/✗ |
| 取得URL重複 | ... | ... | ✓/✗ |
| 回答の一貫性 | ... | ... | ✓/✗ |
| 信頼性スコア範囲 | 0.8-0.95 | 0.8-0.95 | ✓/✗ |
| クロール内容の一致 | ... | ... | ✓/✗ |
| 画像表示（WebUIのみ） | ✓ 表示される | ✗ 表示されない | - |

**期待値**:
- 検索キーワードがほぼ同一
- 取得URLの50%以上が重複
- 回答の主要内容が一致
- 信頼性スコアが同程度
- クロール内容の主要段落や要約が類似（WebUI と CLI で同じ URL から抽出）
- 画像表示は WebUI で確認可能（CLI では URL のみ表示）

### トラブルシューティング: WebUIで検索されるがCLIで検索されない

**原因1: Agent言語設定**
```bash
# researcher CLIで日本語クエリを使用している場合
# agent.pyのSYSTEM_PROMPT_JAが使用されているか確認

researcher --auto-search-default --stream
You: 最新のAI規制動向は？
[Agent分析]
```

**原因2: SearXNG接続確認**
```bash
# CLIで明示的にSearXNG URLを指定
researcher --auto-search-default --searxng-url http://localhost:8888 --stream
```

**原因3: 埋め込みモデル確認**
```bash
# nomic-embed-textが初期化されているか確認
researcher --auto-search-default --embedding-model nomic-embed-text --stream
```

## Sharing Ollama and SearXNG with researcher CLI

Both Perplexica and the `researcher` CLI can point at the same Ollama/SearXNG backends by aligning their configuration (CLI: `--model`, `--searxng-url`, env vars; Perplexica: `config.toml`). Run `researcher` with the same URLs you configure in Perplexica to keep the environments synchronized.

## Perplexica WebUI の GUI 機能

Perplexica WebUI と researcher CLI は同じバックエンド（Ollama/SearXNG）を共有しますが、UI体験が異なります。WebUI の主要な GUI 機能は以下の通りです：

### スタイル付きテキスト
- **Markdown レンダリング**: 回答内のテキストが太字、リスト、コードブロック等のスタイルで自動整形されます
- **CLI との違い**: researcher CLI はプレーンテキストで出力されるため、複雑な構造を認識しにくい場合があります
- **用途**: 技術ドキュメント、コード例を含む回答の読みやすさが重要な場合は WebUI を推奨

### 画像表示
- **検索結果に画像を含む**: 「Transformer architecture diagram」などの画像検索クエリで、WebUI はサムネイルを直接表示
- **クリック機能**: サムネイルをクリックして拡大表示、高解像度版へのアクセスが可能
- **CLI との違い**: researcher CLI は画像 URL のみ出力し、実際の画像表示はできません

### インタラクティブ引用
- **クリック可能な引用**: WebUI の引用リンクをクリックすると、元の URL が新しいタブで開きます
- **ホバープレビュー**: 引用の上にマウスを置くと、URL の簡潔な説明が表示
- **ツールチップ表示**: 信頼性スコアと出版日時がツールチップで表示

### リアルタイムストリーミング
- **プログレッシブ表示**: CLI と同様にストリーミング出力で、回答が段階的に表示
- **視覚的フィードバック**: 検索中と LLM 生成中のスピナーアニメーション表示

## Crawler 設定の共有

Perplexica と researcher は、Web クローリング時の設定を揃えることで、同等の結果を得られます。

### `config.toml` での Crawler 設定サンプル

Perplexica の `config.toml` に以下を追加します：

```toml
[crawler]
timeout = 10          # researcher WebCrawler の timeout と同じ（秒）
max_content_length = 1000  # researcher の max_chars に相当（文字数）
user_agent = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.36"
```

### 設定の詳細

- **`timeout`**: クロール時のソケットタイムアウト。researcher の `WebCrawler(timeout=10)` と一致させます
- **`max_content_length`**: 取得する HTML/テキストの最大サイズ。researcher の `max_chars=1000` に対応
- **`user_agent`**: クロール時に使用する User-Agent ヘッダー。ブロック回避と正確な DOM 取得のため、一般的なブラウザ User-Agent を使用

### HTML パーサーの統一

researcher の `WebCrawler` は BeautifulSoup を使用し、lxml パーサーで HTML を解析しています。Perplexica が同じ lxml パーサーを使用する場合、抽出結果がより一致します。

### 検証手順

1. **researcher の設定を確認**:
   ```bash
   grep -A5 "class WebCrawler" src/researcher/web_crawler.py | head -10
   # timeout=10, max_chars=1000 の設定を確認
   ```

2. **Perplexica の `config.toml` に上記設定を追加**:
   ```bash
   cd Perplexica
   cat >> config.toml << 'EOF'
   [crawler]
   timeout = 10
   max_content_length = 1000
   EOF
   ```

3. **同じクエリで検証**:
   - CLI で実行: `researcher --auto-search-default --stream`
   - WebUI で実行: `http://localhost:3000` をブラウザで開く
   - 同じクエリを入力して、取得される URL と引用内容を比較