# researcher - Perplexity-style ローカル検索AI

**researcher** は、ローカル LLM (Ollama) + Web検索 (SearXNG) + 自動検索判断 (Agent) + MCP統合を組み合わせた、Perplexity-like のオープンソースシステムです。

## 主要機能一覧

- ✅ **ローカルLLM対話**: Ollama(llama3, mixtral等)で高速・プライベート対話
- ✅ **自動Web検索**: 最新ニュース/統計/イベント/不明な事実を自動判定して検索
- ✅ **引用付き回答**: Perplexity風に信頼性スコア付き引用を自動生成
- ✅ **MCP統合**: ファイルシステム/カレンダー/Notes等のシステムツール活用
- ✅ **多言語対応**: 日本語/英語で自動判定ルール使い分け
- ✅ **ワンコマンド起動**: `./run.sh` で自動初期化

---

## 🚀 クイックスタート（コマンド1つで起動）

### 前提条件
- Python 3.11+
- Ollama: [ollama.com](https://ollama.com) からインストール
- Docker（SearXNG使用時、オプション）

### 初回セットアップ（1回だけ実行）
```bash
cd researcher

# 初回セットアップ（Ollama/SearXNG自動初期化）
./setup.sh
```

### 毎回の起動（以降はこれだけ）
```bash
./run.sh
```

その後、CLIが起動したら:
```
researcher CLI (Ollama)
/exit で終了, /clear で履歴クリア, /history で履歴表示, /search <query> でSearXNG検索
自動検索モード: 有効（最新情報が必要な質問を自動検知）
You: 最新のAIニュースは？
[検索実行中...]

最新のAIニュースには以下のようなものがあります...

## 参照
[1] AI News Daily - ainewsdaily.com (信頼性: 0.92)
[2] TechCrunch AI - techcrunch.com/ai (信頼性: 0.89)
```

---

## 🎨 Streamlit WebUI（開発中）

researcher は将来的に **Streamlit ベースの WebUI** を提供予定です。以下の機能を実装予定：

- 📊 **インタラクティブなチャットインターフェース**: ブラウザベースの対話型UI
- 💾 **セッション履歴管理**: 過去の会話を保存・検索・再開
- 🔄 **動的モデル切り替え**: UIからOllamaモデルをリアルタイム変更
- 🌐 **多言語対応**: セッションごとに日本語/英語を設定
- 📈 **引用の可視化**: 信頼性スコア付き引用をグラフィカルに表示

現在はCLI版をご利用ください。WebUI実装の進捗は今後のリリースでお知らせします。

---

## 📖 ハンズオンガイド：5つのユースケース

### ユースケース 1: 政治・社会ニュース調査

**シナリオ**: 最新の政治支持率動向を調べたい

```bash
./run.sh --auto-search-default
```

```
You: 政党支持率の動向を教えてください
[検索結果: 政党支持率の動向を教えてください]
1. www.jiji.com - https://www.jiji.com/jc/tokushu?id=seitou_shijiritsu&g=pol [1]
   時事ドットコムニュース · 各政党の支持率推移を時事通信の世論調査に基づき...
2. news.web.nhk - https://news.web.nhk/senkyo/shijiritsu/ [2]
   NHKが毎月行っている世論調査のうち、内閣支持率については...

直近の調査によると、各政党の支持率は以下の通りです...

## 参照
[1] www.jiji.com (信頼性: 0.50)
[2] news.web.nhk (信頼性: 0.50)
```

### ユースケース 2: 技術トレンド調査

**シナリオ**: 最新のPython 3.14の新機能を知りたい

```bash
./run.sh --model mixtral --stream
```

```
You: Python 3.14の新機能は？
[自動検索で最新情報を取得...]

Python 3.14 は 2025年10月に予定されており、以下の新機能が含まれます...

## 参照
[1] Python Official Blog
[2] PEP Documents
```

### ユースケース 3: ローカルファイル分析（MCP有効時）

**シナリオ**: プロジェクトのファイルをAIが読んで分析

```bash
./run.sh --enable-mcp
```

```
You: このプロジェクトのREADMEの内容を要約して
[MCP FileSystemで /path/to/README.md を読み込み...]

このプロジェクトは以下の機能を提供しています：
1. ローカルLLM対話
2. 自動Web検索
3. 引用付き回答生成
...
```

### ユースケース 4: 多ターン調査・深掘り

**シナリオ**: 段階的に情報を掘り下げる

```bash
./run.sh --auto-search-default
```

```
You: 生成AI規制の動向は？
[検索で最新規制情報を取得...]

EU: DMA/AI Act施行（2024年〜）
US: Executive Order等で規制方向性を検討中
JP: 政府がAI戦略を推進中

You: 日本の規制は具体的にどのようなものですか？
[追加検索で日本の具体的な規制情報を取得...]

日本では以下の施策が進行中です：
- AI安全研究所の設置
- 倫理ガイドラインの策定
...
```

### ユースケース 5: コード質問とベストプラクティス

**シナリオ**: 最新のコーディング手法を学ぶ

```bash
./run.sh
```

```
You: 2025年のPythonのテストのベストプラクティスは？
[最新のテスティング情報を自動検索...]

現在のベストプラクティスは以下の通りです：

1. **Type Hints の活用**: より厳密な型チェック
2. **pytest の最新機能**: Async Test対応の拡充
3. **Property-Based Testing**: hypothesis库の活用
...

## 参照
[1] pytest Documentation 2025
[2] PEP 484+ Type Hints Guide
```



---

## ⚙️ CLI フラグリファレンス

| フラグ | 説明 | デフォルト | 例 |
|--------|------|-----------|-----|
| `--model` | 使用するLLMモデル名 | 環境変数`OLLAMA_MODEL` / `gpt-oss:20b` | `--model mixtral` |
| `--stream` | ストリーミング出力 | OFF | `--stream` |
| `--no-stream` | ストリーミング出力を無効化（出力を一度に返す） | ON | `--no-stream` |
| `--auto-search` | 手動でQueryAgent検索を有効化 | OFF | `--auto-search` |
| `--auto-search-default` | デフォルトで自動検索を有効 | 環境変数`AUTO_SEARCH_DEFAULT` | `--auto-search-default` |
| `--no-auto-search` | 自動検索を無効化（`--auto-search-default`と併用） | OFF | `--no-auto-search` |
| `--searxng-url` | SearXNGサーバーのURL | `http://localhost:8888` | `--searxng-url http://searxng:8888` |
| `--embedding-model` | 埋め込みモデル名 | `nomic-embed-text-v2-moe` | `--embedding-model nomic-embed-text` |
| `--relevance-threshold` | 再ランク時の関連性閾値 | 0.5（run.sh と一致） | `--relevance-threshold 0.3` |
| `--agent-language` | QueryAgent の言語（ja/en） | ja (環境変数`AGENT_LANGUAGE`) | `--agent-language en` |
| `--enable-mcp` | MCP機能を有効化 | OFF | `--enable-mcp` |
| `--mcp-config` | MCPサーバー設定 | デフォルト設定 | `--mcp-config ./mcp-config.json` |

### 使用例

```bash
# 日本語でAuto-Search有効
./run.sh --auto-search-default --stream

# 英語でAuto-Search、MCPも有効
./run.sh --auto-search-default --agent-language en --enable-mcp

# SearXNGカスタムURL
./run.sh --searxng-url http://my-searxng.local:8888

# テストモード（Non-Streaming）
./run.sh --model mistral --no-auto-search
```

---

## 🔧 環境変数設定

`.zshrc` または `.bashrc` に追加:

```bash
# Ollama設定
export OLLAMA_MODEL=mixtral              # デフォルトモデル
export OLLAMA_URL=http://localhost:11434 # Ollamaサーバー

# SearXNG設定
export SEARXNG_URL=http://localhost:8888 # SearXNGサーバー


# Agent設定
export AGENT_LANGUAGE=en                  # QueryAgent言語（ja/en）
export AUTO_SEARCH_DEFAULT=true           # デフォルトで自動検索を有効

# Embedding設定
export EMBEDDING_MODEL=nomic-embed-text-v2-moe
export RELEVANCE_THRESHOLD=0.5            # デフォルト値（run.sh と一致）。0.0 で全結果返却、値を上げると精度優先

# MCP設定
export MCP_CONFIG=/path/to/mcp-config.json
```

反映:
```bash
source ~/.zshrc
```

---

## 📋 実行中のコマンド（REPL）

| コマンド | 説明 | 例 |
|---------|------|-----|
| `/search <query>` | 手動で検索を実行 | `/search Python 3.14 new features` |
| `/blacklist [show\|add\|clear]` | ドメインブラックリスト管理 | `/blacklist add wsj.com` |
| `/history` | 会話履歴を表示 | `/history` |
| `/clear` | 履歴をクリア | `/clear` |
| `/status` | Ollama/SearXNG接続状態を確認 | `/status` |
| `/exit` | CLIを終了 | `/exit` |

---

## 🚨 トラブルシューティング

### Ollamaサーバーが起動しない
```bash
# 確認
which ollama

# インストール（未インストール時）
curl -fsSL https://ollama.ai/install.sh | sh

# 手動起動
ollama serve
```

### モデルが見つからないエラー
```bash
# インストール済みモデル確認
ollama list

# モデルをダウンロード（所要時間: 数分〜数十分）
ollama pull gpt-oss:20b              # メインモデル
ollama pull nomic-embed-text-v2-moe  # 埋め込みモデル
ollama pull mixtral                   # 代替モデル
```

### SearXNG JSON API エラー (403)
**症状**: `[検索結果は見つかりませんでした。]` と表示される

**原因**: SearXNGのJSON APIが無効な場合、自動的にHTML解析にフォールバック

**解決策**:
```bash
# SearXNG が起動しているか確認
docker ps | grep searxng

# 起動していない場合は再起動
docker run -d -p 8888:8080 --name searxng searxng/searxng

# キャッシュをクリア
cd researcher
find . -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null
```

### ポート競合エラー
```bash
# 使用中のポート確認
lsof -i :8888   # SearXNG
lsof -i :11434  # Ollama

# プロセス終了
kill -9 <PID>

# または Ollama/SearXNG を明示的に再起動
./setup.sh
```

### MCP 接続エラー
**症状**: `[WARN] すべてのMCPサーバーへの接続に失敗しました`

**原因**: MCPサーバー設定が正しくない、またはNode.jsモジュールが見つからない

**解決策**:
```bash
# MCPの詳細ドキュメントを参照
cat docs/mcp-setup.md
```

### ペイウォール・アクセス制限ドメインの対策

**症状**: 特定のドメイン（例: wsj.com, nytimes.com）からの情報取得に失敗し、ハルシネーションが発生する

**原因**: ペイウォールや認証が必要なサイトはクロールできず、LLMが古い知識で回答してしまう

**解決策**:

1. **自動ブラックリスト**: 失敗したドメインは自動的にブラックリストに追加され、次回以降スキップされます
   ```bash
   ./run.sh --auto-search-default
   You: 最新の経済ニュースは？
   [検索実行中...クロール失敗時は自動的にブラックリストに追加されます]
   ```
   失敗したドメインはログに記録され、ブラックリストファイル（`~/.researcher/blacklist.json`）に自動保存されます。次回検索時から該当ドメインはスキップされます。

2. **手動ブラックリスト追加**: 問題のあるドメインを事前に追加
   ```bash
   You: /blacklist add wsj.com
   [ブラックリストに追加: wsj.com]
   
   You: /blacklist add https://nytimes.com/news
   [ブラックリストに追加: nytimes.com]
   ```
   URL形式での指定も対応しており、自動的にドメイン部分を抽出して追加されます。

3. **ブラックリスト確認**:
   ```bash
   You: /blacklist show
   [ブラックリストドメイン]
     - nytimes.com
     - wsj.com
   ```

4. **ブラックリストクリア**（誤追加時）:
   ```bash
   You: /blacklist clear
   ブラックリストをクリアしますか？ (yes/no): yes
   [ブラックリストをクリアしました]
   ```

**ヒント**: ブラックリストは `~/.researcher/blacklist.json` に保存され、再起動後も保持されます。

---

## 📚 詳細ドキュメント

より詳しい情報は以下をご覧ください：

- **[MCP 統合ガイド](docs/mcp-setup.md)** - MCPサーバーの設定と使用方法

---

## 🔌 WebCrawler RAG統合

researcher は検索結果のコンテンツをLLMに提供するための **WebCrawler RAG層** を備えています。デフォルトでは `WebCrawler` クラスがHTMLコンテンツを抽出します。

### WebCrawler インターフェース

カスタムWebクローラーを実装する場合は、以下のインターフェースに従ってください：

```python
class CustomWebCrawler:
    def crawl_results(
        self, results: List[Dict[str, Any]], max_urls: int = 3
    ) -> Dict[str, Any]:
        """
        検索結果から上位N個のURLをクロールし、コンテンツとメタデータを抽出します。
        
        このメソッドの戻り値は ChatManager の retry ロジックで使用されるため、
        必ず以下の構造を返す必要があります。
        
        Args:
            results: 検索結果のリスト（各要素は "url" キーを持つ辞書）
            max_urls: クロール対象の最大URL数
            
        Returns:
            {
                "content": Dict[str, str],           # URL -> 抽出されたテキストコンテンツ
                "failed_domains": Set[str],          # クロール失敗したドメイン
                "success_rate": float,               # 成功率 (0.0-1.0)
                "total_attempts": int,               # 試行総数
                "successful_crawls": int             # 成功したクロール数
            }
            
        ChatManager は success_rate < 0.5 の場合、Agent を使用して
        alternate query を生成し、失敗したドメインを避けて再検索を試みます。
        custom implementation でも、これらのフィールドを意味のある値で
        埋めることで retry ロジックが機能します。
        """
        pass
    
    def format_crawled_content(self, crawled_content: Dict[str, str]) -> str:
        """
        クロール結果をLLMコンテキストに注入可能な形式にフォーマットします。
        
        Args:
            crawled_content: crawl_results() の戻り値の "content" フィールド
            
        Returns:
            ユーザーメッセージに追記可能な単一の文字列
        """
        pass
```

### 使用例

CLIで `ChatManager` に WebCrawler インスタンスを渡すと、自動的に検索結果から上位3つのURLをクロールし、抽出したコンテンツをLLMに提供します。
失敗率が高い場合（success_rate < 0.5）、Agent が新しいクエリを生成して再検索を試みます：

```python
from researcher.web_crawler import WebCrawler
from researcher.chat_manager import ChatManager

crawler = WebCrawler(timeout=10)
chat = ChatManager(..., web_crawler=crawler, agent=agent)  # agent が retry 時に使用されます
```

---

## 📊 システムアーキテクチャ

```
┌─────────────────────────────────────────┐
│            ./run.sh                     │ ← これだけ実行！
└──────────────┬──────────────────────────┘
               │
        ┌──────┴──────────────────────────┐
        │                                 │
        ▼                                 ▼
┌──────────────────┐            ┌──────────────────┐
│ Ollama起動確認   │            │ SearXNG起動確認  │
│ :11434           │            │ :8888            │
└──────────────────┘            └──────────────────┘
        │                                 │
        └──────────┬──────────────────────┘
                   │
                   ▼
         ┌─────────────────────┐
         │   researcher CLI    │
         └──────────┬──────────┘
                    │
        ┌───────────┼───────────┐
        │           │           │
        ▼           ▼           ▼
  ┌──────────┐ ┌──────────┐ ┌──────────┐
  │QueryAgent│ │ SearXNG  │ │MCP Tools │
  │ 検索判定 │ │ Web検索  │ │統合連携  │
  └──────────┘ └──────────┘ └──────────┘
        │           │           │
        └───────────┼───────────┘
                    │
                    ▼
         ┌─────────────────────┐
         │  LLM + 引用生成     │
         │  (ChatManager)      │
         └─────────────────────┘
```
---

## 🧪 テスト実行例

### テスト 1: 基本的な質問
```bash
./run.sh

You: こんにちは
こんにちは。お手伝いできることはありますか？

You: /exit
```

### テスト 2: 自動検索が動作するか確認
```bash
./run.sh --auto-search-default

You: 2025年のノーベル賞受賞者は？
[検索結果が自動で取得される...]

You: /exit
```

### テスト 3: 英語モード
```bash
./run.sh --agent-language en

You: What are the latest AI trends?
[English query analysis...]

You: /exit
```

---

## ✨ パフォーマンス最適化

### 高速化設定
```bash
# GPU加速を使用（NVIDIA CUDAが必要）
CUDA_VISIBLE_DEVICES=0 ./run.sh

# 小さいモデルを使用
./run.sh --model mistral  # より軽量
```

### メモリ節約設定
```bash
# ストリーミングなしで実行（出力を一度に返す）
./run.sh --no-stream

# または --stream フラグなしで実行
./run.sh --model mistral --auto-search-default
```

---

## 🤝 コントリビューション

Issues・PRを歓迎します！

開発環境セットアップ:
```bash
python -m venv venv
source venv/bin/activate
pip install -e .
pytest
```

---

## 📄 ライセンス

MIT License

---

## 🙋 FAQ

**Q: オフラインで使用できますか？**
A: はい。Ollamaとモデルをダウンロード済みであれば、インターネット接続なしで動作します。SearXNG検索機能は使用できません。

**Q: プライバシーは保護されていますか？**
A: はい。すべてのデータはローカルマシンで処理され、外部のクラウドサービスに送信されません。

**Q: GPU を使用できますか？**
A: Ollama が NVIDIA CUDA をサポートしている場合、自動的に GPU加速が有効になります。

**Q: カスタムモデルを使用できますか？**
A: はい。`ollama pull <model-name>` でインストール後、`--model` フラグで指定できます。

