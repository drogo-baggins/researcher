# researcher - Perplexity-style ローカル検索AI

**researcher** は、ローカル／クラウド LLM + Web検索 (SearXNG) + 自動検索判断 (Agent) + MCP統合を組み合わせた、Perplexity-like のオープンソースシステムです。

## 主要機能一覧

- ✅ **マルチプロバイダ LLM 対応**: Ollama (llama3, mistral 等) に加え、OpenAI 互換 API なら VeniceAI・Azure OpenAI・OpenRouter など任意のプロバイダを複数登録可能
- ✅ **自動Web検索**: 最新ニュース/統計/イベント/不明な事実を自動判定して検索
- ✅ **引用付き回答**: Perplexity風に信頼性スコア付き引用を自動生成
- ✅ **MCP統合**: ファイルシステム/カレンダー/Notes等のシステムツール活用
- ✅ **多言語対応**: 日本語/英語で自動判定ルール使い分け
- ✅ **WebUI メイン利用**: Streamlit ベースのブラウザUIで直感的に操作
- ✅ **セッション履歴管理**: 会話の保存・検索・再開・タグ付け

---

## 🚀 クイックスタート

### 前提条件

| 必須 | 任意 |
|------|------|
| Python 3.11+ | Ollama（ローカル LLM を使う場合） |
| Docker または Podman（SearXNG 用） | OpenAI 互換プロバイダの API キー |

### 初回セットアップ（1 回のみ）

```bash
cd researcher
./setup.sh
```

### 起動

```bash
./run.sh
```

ブラウザが自動的に `http://localhost:8501` を開き、WebUI が表示されます。

---

## 🌐 WebUI（メイン利用方法）

researcher のメインインタフェースは **Streamlit ブラウザ UI** です。

### 起動方法

```bash
# エントリポイント経由（推奨）
researcher-webui

# または直接 Streamlit で起動
streamlit run src/researcher/Home.py
```

### 画面構成

| ページ | 説明 |
|--------|------|
| **🏠 ホーム** | 接続状態の確認とナビゲーション |
| **💬 Chat** | LLM との対話・自動Web検索 |
| **📚 History** | 過去のセッション検索・再開・タグ管理 |
| **⚙️ Settings** | LLMプロバイダ・モデル・SearXNG・UI設定 |

### 基本的な使い方

1. ブラウザで `http://localhost:8501` を開く
2. **Settings** ページでモデルや検索設定を確認する
3. **Chat** ページで質問を入力する
   - 自動検索モードが有効な場合、最新情報が必要な質問は自動的に Web 検索が実行されます
   - 回答下部の引用リンクから情報源を確認できます
4. **History** ページで過去の会話を検索・再開できます

### セキュリティに関する注意事項 ⚠️

| 項目 | 詳細 |
|------|------|
| **ローカル実行** | `localhost:8501` にのみバインドされます（同一マシンからのアクセス想定） |
| **認証なし** | ユーザー認証機構がありません |
| **暗号化なし** | セッションデータは `~/.researcher/sessions.db` に平文で保存されます |

**推奨される運用環境**: 単一ユーザーによる個人マシン上での使用。  
リモートアクセスが必要な場合は SSH トンネル（`ssh -N -L 8501:localhost:8501 ...`）またはリバースプロキシ + HTTPS + 認証層の設置を強く推奨します。

詳細は [docs/security.md](docs/security.md) を参照してください。

---

## ⚙️ 設定（Settings ページ）

WebUI の **Settings（⚙️）** ページから各種設定を変更できます。設定は `~/.researcher/settings.json` に保存されます。

### LLM プロバイダ管理

OpenAI 互換の API エンドポイントを持つプロバイダを複数登録できます。

**Settings → LLM プロバイダ** セクションで「＋ 新しいプロバイダを追加」:

| フィールド | 例 | 説明 |
|-----------|-----|------|
| プロバイダ名 | `VeniceAI` | 識別用の任意の名前 |
| ベース URL | `https://api.venice.ai/api/v1` | OpenAI 互換エンドポイントのベース URL |
| API キー | `ven-xxxx` | プロバイダから発行された API キー |
| モデル一覧 | `llama-3.3-70b, mistral-31-24b` | カンマ区切りで使用するモデルを列挙 |

登録後、**LLM モデル設定** のセレクトボックスに `プロバイダ名::モデル名` 形式（例: `VeniceAI::llama-3.3-70b`）で表示されます。

#### 対応プロバイダの例

| プロバイダ | ベース URL |
|-----------|-----------|
| VeniceAI | `https://api.venice.ai/api/v1` |
| OpenRouter | `https://openrouter.ai/api/v1` |
| Azure OpenAI | `https://<resource>.openai.azure.com/openai/deployments/<deployment>` |
| Ollama (ローカル) | *プロバイダ登録不要・自動検出* |

### LLM モデル設定

| 設定項目 | 説明 |
|---------|------|
| 検索語生成モデル | Web検索クエリの生成に使用するモデル（軽量モデル推奨） |
| 回答生成モデル | ユーザーへの最終回答を生成するモデル |
| 品質検証モデル | 回答の自己評価に使用するモデル（軽量モデル推奨） |

### SearXNG 検索設定

| 設定項目 | 説明 |
|---------|------|
| 検索エンジン | `general` / `news` / `science` など |
| 言語 | 検索言語（`ja` / `en` など） |
| セーフサーチ | `off` / `moderate` / `strict` |

---

## 🐋 SearXNG セットアップ

SearXNG はプライバシーを重視したオープンソースのメタ検索エンジンです。Docker または Podman で手軽に起動できます。

### Docker を使う場合

```bash
# 起動
docker run -d \
  --name searxng \
  -p 8888:8080 \
  -v $(pwd)/searxng_settings.yml:/etc/searxng/settings.yml:ro \
  searxng/searxng

# 動作確認
curl "http://localhost:8888/search?q=test&format=json"
```

`docker compose` を使う場合:

```yaml
# docker-compose.yml
services:
  searxng:
    image: searxng/searxng
    ports:
      - "8888:8080"
    volumes:
      - ./searxng_settings.yml:/etc/searxng/settings.yml:ro
    restart: unless-stopped
```

```bash
docker compose up -d
```

### Podman を使う場合

Podman は Docker 互換のデーモンレスコンテナランタイムです。`docker` コマンドをそのまま `podman` に読み替えて使用できます。

```bash
# 起動
podman run -d \
  --name searxng \
  -p 8888:8080 \
  -v $(pwd)/searxng_settings.yml:/etc/searxng/settings.yml:ro \
  docker.io/searxng/searxng

# 動作確認
curl "http://localhost:8888/search?q=test&format=json"
```

`podman-compose` を使う場合:

```bash
pip install podman-compose   # 未インストールの場合
podman-compose up -d
```

**自動起動（systemd ユーザーサービス）**:

```bash
# コンテナ起動後、systemd サービスを生成
podman generate systemd --name searxng --new --files
mkdir -p ~/.config/systemd/user
mv container-searxng.service ~/.config/systemd/user/
systemctl --user enable --now container-searxng.service
```

**Windows で Podman Desktop を使う場合**:  
Podman Desktop の GUI から「New Container」→ `docker.io/searxng/searxng` を指定し、ポートを `8888:8080` に設定して起動するだけです。

### JSON API の有効化について

本リポジトリに同梱の `searxng_settings.yml` には JSON API が有効化済みのため、上記コマンドでそのままマウントすれば追加設定は不要です。

独自の設定ファイルを使う場合は `search.formats` に `json` を追加してください:

```yaml
search:
  formats:
    - html
    - json   # ← 追加
```

---

## 💻 CLI（コマンドラインインタフェース）

CLIはスクリプト連携や自動化など特定の用途に利用できます。通常は WebUI の使用を推奨します。

### 基本的な起動

```bash
researcher --model llama3.3 --auto-search-default --stream
```

OpenAI 互換プロバイダのモデルを使う場合:

```bash
researcher --model "VeniceAI::llama-3.3-70b" --auto-search-default --stream
```

### CLI フラグリファレンス

| フラグ | 説明 | デフォルト |
|--------|------|-----------|
| `--model` | 使用するモデル（`モデル名` または `プロバイダ名::モデル名`） | settings.json の値 |
| `--stream` | ストリーミング出力を有効化 | OFF |
| `--no-stream` | ストリーミング出力を無効化 | — |
| `--auto-search-default` | デフォルトで自動検索を有効 | OFF |
| `--no-auto-search` | 自動検索を無効化 | — |
| `--searxng-url` | SearXNG サーバーの URL | `http://localhost:8888` |
| `--embedding-model` | 埋め込みモデル名 | settings.json の値 |
| `--relevance-threshold` | 再ランク時の関連性閾値 | `0.5` |
| `--agent-language` | QueryAgent の言語（`ja` / `en`） | `ja` |
| `--enable-mcp` | MCP 機能を有効化 | OFF |
| `--mcp-config` | MCP サーバー設定ファイルのパス | デフォルト設定 |

### REPL コマンド（CLI 実行中）

| コマンド | 説明 |
|---------|------|
| `/search <query>` | 手動で検索を実行 |
| `/blacklist [show\|add\|clear]` | ドメインブラックリスト管理 |
| `/history` | 会話履歴を表示 |
| `/clear` | 履歴をクリア |
| `/status` | Ollama / SearXNG の接続状態を確認 |
| `/last_eval` | 最後の回答の自己評価スコアを表示 |
| `/feedback [thumbs_up\|thumbs_down\|stats]` | フィードバック送信・統計表示 |
| `/exit` | CLI を終了 |

---

## 🔧 環境変数

`.zshrc` または `.bashrc` に追加することで CLI / WebUI 両方に適用されます。Settings ページでの設定が優先されます。

```bash
# Ollama
export OLLAMA_MODEL=llama3.3
export OLLAMA_URL=http://localhost:11434

# SearXNG
export SEARXNG_URL=http://localhost:8888

# Agent
export AGENT_LANGUAGE=ja               # QueryAgent 言語（ja/en）
export AUTO_SEARCH_DEFAULT=true        # デフォルトで自動検索を有効

# Embedding
export EMBEDDING_MODEL=nomic-embed-text-v2-moe
export RELEVANCE_THRESHOLD=0.5

# MCP
export MCP_CONFIG=/path/to/mcp-config.json
```

---

## 🚨 トラブルシューティング

### Ollama が起動しない

```bash
# インストール確認
which ollama

# インストール（未インストールの場合）
curl -fsSL https://ollama.ai/install.sh | sh

# 手動起動
ollama serve
```

### モデルが見つからないエラー

```bash
# インストール済みモデル確認
ollama list

# モデルをダウンロード
ollama pull llama3.3
ollama pull nomic-embed-text-v2-moe  # 埋め込みモデル
```

### SearXNG JSON API エラー（403 / 空の検索結果）

**症状**: `[検索結果は見つかりませんでした]` と表示される

**確認・対処**:

```bash
# Docker の場合
docker ps | grep searxng      # 起動確認
docker restart searxng        # 再起動

# Podman の場合
podman ps | grep searxng
podman restart searxng

# JSON API の疎通確認
curl "http://localhost:8888/search?q=test&format=json"
```

応答が `{"results": []}` 以外のエラーになる場合、`searxng_settings.yml` の `search.formats` に `json` が含まれているか確認し、コンテナを再作成してください。

### OpenAI 互換プロバイダ接続エラー

**症状**: Settings ページでプロバイダ保存時に接続エラーが表示される

**確認事項**:
- ベース URL が `/v1` で終わっているか（例: `https://api.venice.ai/api/v1`）
- API キーが有効か
- 設定したモデル名がプロバイダで有効か

### ペイウォール・アクセス制限ドメインの対策

失敗したドメインは自動的にブラックリストに追加され、次回以降スキップされます。CLI では `/blacklist` コマンドで管理できます。ブラックリストは `~/.researcher/blacklist.json` に保存されます。

### ポート競合

```bash
# Windows
netstat -ano | findstr :8888
netstat -ano | findstr :11434

# macOS / Linux
lsof -i :8888
lsof -i :11434
```

### MCP 接続エラー

```bash
cat docs/mcp-setup.md
```

---

## 📊 システムアーキテクチャ

```
                    ブラウザ (http://localhost:8501)
                           │
                    ┌──────┴──────────────┐
                    │  Streamlit WebUI    │  ← メインインタフェース
                    │  Home / Chat /      │
                    │  History / Settings │
                    └──────────┬──────────┘
                               │
                    ┌──────────┴──────────┐
                    │    ChatManager      │
                    └──┬──────────────────┘
                       │
        ┌──────────────┼───────────────────┐
        │              │                   │
        ▼              ▼                   ▼
┌─────────────┐ ┌────────────┐   ┌──────────────────┐
│ QueryAgent  │ │  SearXNG   │   │   LLM Client     │
│  検索判定   │ │  Web検索   │   │  Ollama /        │
└─────────────┘ └────────────┘   │  OpenAI互換API   │
        │              │          └──────────────────┘
        │      ┌───────┴──────┐
        │      │  WebCrawler  │
        │      │  RAG 層      │
        │      └──────────────┘
        │              │
        └──────────────┘
                 │
        ┌────────┴────────┐
        │  CitationManager│
        │  引用・評価生成  │
        └─────────────────┘
```

---

## 🔌 WebCrawler カスタマイズ

カスタム Web クローラーを実装する場合は、以下のインターフェースに従ってください:

```python
class CustomWebCrawler:
    def crawl_results(
        self, results: list[dict], max_urls: int = 3
    ) -> dict:
        """
        Returns:
            {
                "content": dict[str, str],   # URL -> 抽出テキスト
                "failed_domains": set[str],  # 失敗ドメイン
                "success_rate": float,       # 成功率 0.0-1.0
                "total_attempts": int,
                "successful_crawls": int,
            }
        """
        ...

    def format_crawled_content(self, crawled_content: dict[str, str]) -> str:
        """クロール結果を LLM コンテキスト注入可能な文字列に変換"""
        ...
```

`success_rate < 0.5` の場合、Agent が自動的に代替クエリを生成して再検索を試みます。

---

## 🧪 開発・テスト

```bash
# 仮想環境セットアップ
python -m venv venv
source venv/bin/activate          # Windows: .\venv\Scripts\Activate.ps1
pip install -r requirements.txt
pip install -r requirements-dev.txt

# テスト実行
pytest tests/ -q --ignore=tests/e2e

# E2E テスト（Streamlit が起動している状態で）
pytest tests/e2e/
```

---

## 📚 詳細ドキュメント

| ドキュメント | 内容 |
|-------------|------|
| [docs/streamlit-guide.md](docs/streamlit-guide.md) | WebUI の各部分・トラブルシューティング |
| [docs/security.md](docs/security.md) | セキュリティ設定・推奨運用方法 |
| [docs/mcp-setup.md](docs/mcp-setup.md) | MCP サーバーの設定と使用方法 |
| [docs/architecture.md](docs/architecture.md) | システムアーキテクチャの詳細 |

---

## 🤝 コントリビューション

Issues・PR を歓迎します！

---

## 📄 ライセンス

MIT License

---

## 🙋 FAQ

**Q: オフラインで使用できますか？**  
A: はい。Ollama とモデルをダウンロード済みであれば、インターネット接続なしで動作します（SearXNG 検索機能は除く）。

**Q: プライバシーは保護されていますか？**  
A: Ollama 使用時はすべてのデータがローカルマシンで処理されます。OpenAI 互換プロバイダを使用する場合、プロンプトはそのプロバイダのサーバーに送信されます。

**Q: GPU を使用できますか？**  
A: Ollama が NVIDIA CUDA をサポートしている場合、自動的に GPU 加速が有効になります。

**Q: OpenAI (api.openai.com) は使えますか？**  
A: 現時点では OpenAI のチャット補完 API と互換性のある任意のエンドポイントを登録できます。Settings ページでベース URL を `https://api.openai.com/v1`、API キーを設定してください。

**Q: Docker の代わりに Podman を使えますか？**  
A: はい。SearXNG の起動コマンドの `docker` を `podman` に読み替えるだけで動作します。詳細は [SearXNG セットアップ](#-searxng-セットアップ) セクションを参照してください。