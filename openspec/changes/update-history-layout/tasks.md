# Implementation Tasks

## 1. Filter Refactoring
- [x] 1.1 Rename `render_unified_filters()` to `render_horizontal_filters()`
- [x] 1.2 Refactor filter layout to use `st.columns([4, 1, 2, 2, 3])`
- [x] 1.3 Add `st.checkbox("日付で絞り込む")` for date filter toggle
- [x] 1.4 Implement conditional display of date inputs based on checkbox state
- [x] 1.5 Remove subheader "🔍 フィルタ" for compactness
- [x] 1.6 Ensure function returns same tuple: `(search_query, date_from_str, date_to_str, selected_tags)`

## 2. Session List Compaction
- [x] 2.1 Rename `render_session_selector()` to `render_compact_session_list()`
- [x] 2.2 Add height constraint to session list (max 200px)
- [x] 2.3 Implement using `st.container()` with custom CSS or `st.dataframe()` with height parameter
- [x] 2.4 Keep session count display at top
- [x] 2.5 Ensure function returns same type: `Optional[int]`

## 3. Layout Restructuring
- [x] 3.1 Remove `col_filter, col_content = st.columns([1, 2])` from main()
- [x] 3.2 Remove `with col_filter:` and `with col_content:` blocks
- [x] 3.3 Implement vertical 3-row layout:
  - Row 1: Filters (full width)
  - Row 2: Session list (full width, compact)
  - Row 3: Session details (full width)
- [x] 3.4 Add `st.divider()` between rows for visual separation
- [x] 3.5 Update session selection message to "上のリストからセッションを選択してください"

## 4. Session State Management
- [x] 4.1 Initialize `st.session_state.date_filter_enabled = False` in main()
- [x] 4.2 Ensure checkbox state persists across reruns

## 5. Calendar Visualization
- [x] 5.1 Remove `render_calendar_visualization()` call from main() (or move to separate section)
- [x] 5.2 Consider moving to separate expandable section if needed in future

## 6. Testing & Validation
- [x] 6.1 Test filter layout displays correctly on various screen widths
- [x] 6.2 Test date filter toggle enables/disables date inputs
- [x] 6.3 Test session list height constraint works
- [x] 6.4 Test session selection updates details correctly
- [x] 6.5 Test filter changes update session list
- [x] 6.6 Verify no regressions in existing functionality

## 7. UI検証（必須）

**⚠️ MANDATORY: この変更は UI 検証が完了するまで実装完了とみなされません。**

- [ ] 7.1 E2Eテストの実行
  - [ ] Playwright E2Eテストを実行してHistoryページが正常に動作することを確認
  - [ ] 新しい3行レイアウトがE2Eテストで検証されることを確認

- [ ] 7.2 手動UIテスト
  - [ ] WebUIを起動して実際にHistoryページを操作
  - [ ] フィルタの横並びレイアウトを確認
  - [ ] セッションリストのコンパクト表示（200px）を確認
  - [ ] セッション詳細の全幅表示を確認
  - [ ] 日付フィルタのトグル動作を確認

- [ ] 7.3 検出問題の修正
  - [ ] UI上で見つかった問題を全て修正
  - [ ] レイアウト崩れやスタイリング問題を解決
  - [ ] ユーザビリティの問題を改善

- [ ] 7.4 修正後の再テスト
  - [ ] すべてのE2Eテストがパス
  - [ ] 手動テストで問題なし
  - [ ] スクリーンショットまたは動作確認結果をドキュメント化

**このセクションが完了するまで、この変更は実装完了とみなされません。**
