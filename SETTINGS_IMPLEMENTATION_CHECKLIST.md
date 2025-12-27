# Settings機能 実装完了チェックリスト

## ✅ 実装完了項目

### 1. 基本機能
- [x] `config.py`に設定管理機能実装
  - [x] `SETTINGS_FILE_PATH` 定義
  - [x] `DEFAULT_SETTINGS` 定義（6項目）
  - [x] `load_settings()` 実装
  - [x] `save_settings()` 実装（アトミック書き込み）

### 2. Settings画面（3_⚙️_Settings.py）
- [x] ページ構造実装
  - [x] ページ設定（タイトル、アイコン）
  - [x] サイドバー（ナビゲーションリンク）
  - [x] メインエントリーポイント（`main()` 関数）

- [x] LLMモデル設定セクション
  - [x] モデル一覧取得（`OllamaClient.list_models()`）
  - [x] 検索語生成モデル選択（selectbox）
  - [x] 回答生成モデル選択（selectbox）
  - [x] 品質検証モデル選択（selectbox）
  - [x] モデル存在確認と警告表示
  - [x] 後方互換性（既存モデル名を選択可能に）

- [x] SearXNG設定セクション
  - [x] 検索エンジン選択（general/news/science/images/カスタム）
  - [x] カスタムエンジン名入力（text_input）
  - [x] 言語選択（ja/en）
  - [x] セーフサーチ選択（off/moderate/on）
  - [x] 空エンジン名検証

- [x] 保存・リセット機能
  - [x] 保存ボタン（💾 設定を保存）
  - [x] リセットボタン（🔄 デフォルトに戻す）
  - [x] 成功/失敗メッセージ表示
  - [x] `st.session_state.settings` 即時更新
  - [x] `st.rerun()` でページリロード

- [x] UI/UX
  - [x] 現在の設定値表示（st.info）
  - [x] ヘルプテキスト（help パラメータ）
  - [x] ページ説明（Markdown）

### 3. 設定の適用（shared_utils.py）
- [x] 設定ロード（`initialize_session_chat()`）
- [x] 3つのOllamaClientインスタンス作成
  - [x] 検索語生成用（search_model）
  - [x] 回答生成用（response_model）
  - [x] 埋め込み用（embedding_model）
- [x] ChatManager作成時に設定適用
  - [x] `evaluation_model` パラメータ
  - [x] `searxng_engine` パラメータ
  - [x] `searxng_lang` パラメータ
  - [x] `searxng_safesearch` パラメータ

### 4. ChatManagerでの設定利用
- [x] コンストラクタに3つのSearXNGパラメータ追加
- [x] `search()` メソッドでパラメータ注入
  - [x] メイン検索ループ
  - [x] クロール失敗時の再検索
- [x] ユーザー指定kwargsが優先される仕組み

### 5. ナビゲーション
- [x] Home.pyにSettingsリンク追加
  - [x] 使い方セクションに説明追加
  - [x] 3カラムレイアウトでボタン追加

### 6. テスト
- [x] 設定ファイル機能テスト（test_config.py）
  - [x] load_settings テスト（7件）
  - [x] save_settings テスト（3件）
- [x] ChatManager SearXNGパラメータテスト（test_chat_manager.py）
  - [x] 基本パラメータ注入テスト
  - [x] ユーザーkwargs優先テスト
  - [x] パラメータNullテスト
  - [x] クロール失敗時の再検索テスト
- [x] Settings画面ロジックテスト（test_settings_page.py）
  - [x] 8つのロジックテスト
- [x] 統合フローテスト（test_settings_flow.py）
  - [x] 8ステップの統合テスト

### 7. エラーハンドリング
- [x] 設定ファイル不在時のデフォルト値返却
- [x] JSON解析エラー時のデフォルト値返却
- [x] 部分設定時のデフォルト値マージ
- [x] モデル不在時の警告表示（保存は可能）
- [x] SearXNG接続失敗時の警告表示
- [x] 設定保存失敗時のエラー表示
- [x] カスタムエンジン名空欄時の警告

## 📊 テスト結果サマリー

| テストカテゴリ | 件数 | 結果 |
|-------------|------|------|
| 設定管理（config.py） | 23 | ✅ 全て成功 |
| ChatManager SearXNG | 4 | ✅ 全て成功 |
| Settings画面ロジック | 8 | ✅ 全て成功 |
| 統合フロー | 8 | ✅ 全て成功 |
| **合計** | **43** | **✅ 100%成功** |

## 🔍 実装箇所マップ

### 設定の流れ
```
Settings画面
    ↓ (ユーザー変更 + 保存)
config.py (save_settings)
    ↓ (書き込み)
~/.researcher/settings.json
    ↓ (読み込み)
config.py (load_settings)
    ↓ (初期化時)
shared_utils.py (initialize_session_chat)
    ↓ (設定適用)
ChatManager + Agent
    ↓ (検索実行)
SearXNG (設定パラメータ使用)
```

### ファイル一覧
| ファイル | 行数 | 役割 |
|---------|------|------|
| `src/researcher/config.py` | 492→577 | 設定管理（+85行） |
| `src/researcher/chat_manager.py` | 898→928 | SearXNGパラメータ注入（+30行） |
| `src/researcher/pages/shared_utils.py` | 486→503 | 設定ロードと適用（+17行） |
| `src/researcher/pages/3_⚙️_Settings.py` | 314 | Settings画面（新規） |
| `src/researcher/Home.py` | 54→62 | ナビゲーションリンク（+8行） |
| `tests/test_config.py` | 255→386 | 設定管理テスト（+131行） |
| `tests/test_chat_manager.py` | 1374→1445 | SearXNGテスト（+71行） |

## 🎯 設定項目一覧

| カテゴリ | 設定キー | デフォルト値 | 用途 |
|---------|---------|------------|------|
| LLM | `search_model` | `llama3.2` | Web検索キーワード生成 |
| LLM | `response_model` | `llama3` | ユーザー回答生成 |
| LLM | `eval_model` | `llama3.2:3b` | 回答品質評価 |
| SearXNG | `searxng_engine` | `general` | 検索エンジンカテゴリ |
| SearXNG | `searxng_lang` | `ja` | 検索結果言語 |
| SearXNG | `searxng_safesearch` | `off` | セーフサーチレベル |

## 📝 使用方法

### 設定の変更
1. Home画面から「⚙️ 設定」をクリック
2. LLMモデルまたはSearXNG設定を変更
3. 「💾 設定を保存」をクリック
4. 成功メッセージを確認

### 設定のリセット
1. Settings画面で「🔄 デフォルトに戻す」をクリック
2. 全ての設定がデフォルト値に戻る

### 設定の反映
- Chat画面に移動すると、新しい設定が自動的に適用される
- 既存のChatセッション継続中は古い設定が使われる（次回初期化時に反映）

## 🔧 トラブルシューティング

| 問題 | 対処法 |
|------|-------|
| モデル一覧が表示されない | Ollamaサーバーが起動しているか確認 |
| 設定が保存されない | `~/.researcher/` ディレクトリの書き込み権限確認 |
| 設定が反映されない | Chat画面を再読み込み（F5）または新規セッション開始 |
| カスタムエンジン名が保存できない | エンジン名が空欄でないか確認 |

## ✨ 次フェーズの拡張案

- [ ] より多くのSearXNGエンジンオプション
- [ ] モデルパラメータ詳細設定（temperature, top_p等）
- [ ] プリセット機能（設定の保存/読み込み）
- [ ] 設定インポート/エクスポート機能
- [ ] 設定履歴管理
- [ ] モデル自動ダウンロード機能
