## 1. ファイル・ディレクトリの整理

- [x] 1.1 ルートのテストファイルを`tests/`に移動
  - [x] `test_regression_tag_bug.py` → `tests/test_regression_tag_bug.py`
  - [x] `test_tag_fix.py` → `tests/test_tag_fix.py`
  - [x] `test_settings_flow.py` → `tests/test_settings_flow.py`
  - [x] `test_settings_page.py` → `tests/test_settings_page.py`
  - [x] `test_settings_reinitialization.py` → `tests/test_settings_reinitialization.py`
  - [x] `test_settings_integration.py` → `tests/test_settings_integration.py`

- [x] 1.2 バックアップファイルを削除
  - [x] `src/researcher/pages/_2_📚_History.py.backup`を削除
  - [x] `tests/test_session_manager.py.backup`を削除

- [x] 1.3 `migrate_db.py`を`scripts/`に移動
  - [x] `migrate_db.py` → `scripts/migrate_db.py`
  - [x] 関連ドキュメント・スクリプトでのパス参照を更新

## 2. ハードコード修正（重要）：すべての具体的なモデル名を削除

- [x] 2.1 `src/researcher/pages/shared_utils.py`の修正
  - [x] Line 158: 初期化時のモデル決定ロジックを修正
  - [x] Line 210: 同様に修正
  - [x] Line 226-228: デフォルト値を削除
  - [x] Line 404, 410: セッション読み込み時のモデル決定ロジックを修正

- [x] 2.2 `src/researcher/cli.py`の修正
  - [x] Line 122: helpテキストから具体的なモデル名を削除
  - [x] Line 187: デフォルト値を修正

- [x] 2.3 `src/researcher/config.py`の修正
  - [x] docstringから具体的なモデル名の例をすべて削除

- [x] 2.4 `src/researcher/utils/page_utils.py`の修正
  - [x] `shared_utils.py`と同様のロジックがあれば修正

- [x] 2.5 テストファイルの修正
  - [x] `tests/e2e/conftest.py`: テストデータから具体的なモデル名を削除
  - [x] `tests/test_session_manager.py`: テストデータから具体的なモデル名を削除
  - [x] `tests/test_config.py`: テストデータから具体的なモデル名を削除
  - [x] `tests/test_webui.py`: テストデータから具体的なモデル名を削除
  - [x] `tests/test_migrate_db.py`: テストデータから具体的なモデル名を削除
  - [x] `tests/test_chat_manager.py`: テストデータから具体的なモデル名を削除
  - [x] その他のテストファイル: すべての具体的なモデル名を削除

## 3. 検証

- [x] 3.1 移動したテストファイルが正常に実行できることを確認
  - [x] `pytest tests/test_regression_tag_bug.py`
  - [x] `pytest tests/test_tag_fix.py`
  - [x] `pytest tests/test_settings_*.py`

- [x] 3.2 既存のテストスイートが全て通過することを確認
  - [x] `pytest tests/` (e2eを除く)

- [x] 3.3 `migrate_db.py`が新しい場所から実行できることを確認
  - [x] `python scripts/migrate_db.py --show-version`

- [ ] 3.4 ハードコード修正後の動作確認
  - [ ] WebUIが正常に起動すること
  - [ ] 設定で選択したモデルが実際に使用されること
  - [ ] セッション読み込み時に設定値が尊重されること
  - [ ] コード内に具体的なモデル名が残っていないことを確認

## 4. UI検証（必須・完了）

**✅ COMPLETED: 全ページがエラーなく動作することを確認しました。**

- [x] 4.1 E2Eテストの実行
  - [x] Playwrightテストを実行して全てのページが動作することを確認
  - [x] HomeページのE2Eテスト実行（エラーなし）
  - [x] Settingsページのモデル設定UI確認（エラーなし）
  - [x] Chatページで設定したモデルが使用されることを確認（エラーなし）
  - [x] Historyページの動作確認（エラーなし、非推奨警告のみ）

- [x] 4.2 手動UIテスト
  - [x] WebUIを起動（`venv/bin/streamlit run src/researcher/Home.py`）
  - [x] Settingsページで空のモデル設定時の挙動確認
  - [x] 各ページでエラーが発生しないことを確認
  - [x] モデル未設定時の適切なエラーメッセージ表示確認

- [x] 4.3 検出問題の修正
  - [x] `st.session_state.settings`未初期化エラーの修正
  - [x] `initialize_session_chat()`に`load_settings()`呼び出しを追加
  - [x] Settings UIでモデルが空の場合の対応（既に対応済み）
  - [x] すべてのUI問題を解決

- [x] 4.4 修正後の再テスト
  - [x] 全ページ（Home, Settings, Chat, History）のスクリーンショット撮影
  - [x] Streamlit例外エラー: 0件
  - [x] テスト結果: 全ページ正常動作

**検証完了日時:** 2025-12-30 17:10  
**スクリーンショット:** `/tmp/home_fixed.png`, `/tmp/settings_page.png`, `/tmp/chat_page.png`, `/tmp/history_page.png`  
**修正ファイル:** `src/researcher/utils/page_utils.py` (settings初期化を追加)
