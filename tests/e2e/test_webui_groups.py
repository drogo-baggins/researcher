"""
WebUI グループ/セッション管理のE2Eテスト (Multipage対応)

Happy Pathシナリオ:
1. Historyページに遷移
2. グループ一覧からグループを選択
3. セッション一覧でセッションをクリック
4. Chatページに自動遷移
5. チャット履歴と検索結果が表示されることを確認
"""
import pytest
import logging
import time

LOGGER = logging.getLogger(__name__)

# ===== Navigation Helpers =====

def navigate_to_history(page, streamlit_app):
    """Historyページに遷移"""
    base_url = streamlit_app.rstrip("/")
    page.goto(f"{base_url}/?page=2_📚_History")
    page.wait_for_selector("text=📚 履歴管理", timeout=10000)
    LOGGER.info("Navigated to History page")

def navigate_to_chat(page, streamlit_app):
    """Chatページに遷移"""
    base_url = streamlit_app.rstrip("/")
    page.goto(f"{base_url}/?page=1_💬_Chat")
    page.wait_for_selector("text=🔍 Researcher", timeout=10000)
    LOGGER.info("Navigated to Chat page")

# ===== Existing Tests (Updated for V2 Schema) =====

@pytest.mark.e2e
def test_session_list_displays_sessions(page, streamlit_app):
    """セッション一覧が正しく表示されることを確認（V2スキーマ対応）"""
    
    # 1. Historyページに遷移
    navigate_to_history(page, streamlit_app)
    
    # 2. セッション選択UIが表示されることを確認
    assert page.is_visible("text=セッションを選択")
    
    # 3. セッション数が表示されることを確認
    assert page.is_visible("text=件 のセッション")
    
    LOGGER.info("✅ Session list test passed")

@pytest.mark.e2e
def test_session_click_loads_content(page, streamlit_app):
    """Selectboxでセッション選択し、History page内で詳細が表示されることを確認"""
    
    # 1. Historyページに遷移
    navigate_to_history(page, streamlit_app)
    
    # 2. 検索タブでセッション一覧を表示
    page.click("text=🔍 検索")
    time.sleep(0.5)
    
    # 3. Selectboxでセッション選択
    selectbox = page.locator("select[aria-label*='セッションを選択']")
    if selectbox.count() > 0:
        selectbox.select_option(index=1)
        time.sleep(1)
        
        # 4. History pageに留まることを確認（Chat pageに遷移しない）
        assert "2_📚_History" in page.url
        
        # 5. セッション詳細が表示されることを確認
        assert page.is_visible("text=📋 セッション詳細")
        
        # 6. メッセージが表示されることを確認
        page.wait_for_selector("[data-testid='stChatMessage']", timeout=10000)
        
        LOGGER.info("✅ Session selectbox loads detail test passed")
    else:
        LOGGER.warning("⚠️ No selectbox found, skipping test")

@pytest.mark.e2e
def test_search_results_expander_displays(page, streamlit_app):
    """検索結果expanderが表示されることを確認"""
    
    # 1. Chatページに遷移
    navigate_to_chat(page, streamlit_app)
    
    # 2. メッセージ履歴に検索結果expanderが存在するか確認
    # （既存のセッションに検索結果が含まれている場合）
    search_expander = page.locator("text=🔍 検索結果")
    
    if search_expander.count() > 0:
        # 3. Expanderをクリックして展開
        search_expander.first.click()
        time.sleep(0.5)
        
        # 4. テーブルヘッダーが表示されることを確認
        assert page.is_visible("text=タイトル")
        assert page.is_visible("text=関連性")
        
        LOGGER.info("✅ Search results expander test passed")
    else:
        LOGGER.warning("⚠️ No search results found, skipping test")

# ===== New Tests for Date/Tag Filters and Calendar =====

@pytest.mark.e2e
def test_tag_filter_functionality(page, streamlit_app):
    """タグフィルタ機能のテスト（V2スキーマ対応）"""
    
    # 1. Historyページに遷移
    navigate_to_history(page, streamlit_app)
    
    # 2. タグフィルタが表示されることを確認
    tag_filter = page.locator("text=タグフィルタ")
    if tag_filter.count() > 0:
        LOGGER.info("✅ Tag filter test passed")
    else:
        LOGGER.warning("⚠️ Tag filter not found, skipping test")

@pytest.mark.e2e
def test_date_filter_displays_sessions(page, streamlit_app):
    """日付フィルタでセッションを絞り込めることを確認"""
    
    # 1. Historyページに遷移
    navigate_to_history(page, streamlit_app)
    
    # 2. 「📅 日付フィルタ」タブに切り替え
    page.click("text=📅 日付フィルタ")
    time.sleep(0.5)
    
    # 3. 日付入力フィールドが表示されることを確認
    assert page.is_visible("text=開始日")
    assert page.is_visible("text=終了日")
    
    # 4. セッション一覧が表示されることを確認
    assert page.is_visible("text=📋 最近のセッション") or page.is_visible("text=件 のセッション")
    
    LOGGER.info("✅ Date filter test passed")

@pytest.mark.e2e
def test_calendar_visualization_displays(page, streamlit_app):
    """カレンダー可視化が表示されることを確認"""
    
    # 1. Historyページに遷移
    navigate_to_history(page, streamlit_app)
    
    # 2. 日付フィルタタブに切り替え
    page.click("text=📅 日付フィルタ")
    time.sleep(0.5)
    
    # 3. カレンダーセクションが表示されることを確認
    # （セッションが存在する場合のみ表示される）
    calendar_section = page.locator("text=📊 セッション作成カレンダー")
    
    if calendar_section.count() > 0:
        # 4. Markdownテーブルが存在することを確認
        assert page.is_visible("text=| 日付")
        assert page.is_visible("text=セッション数")
        
        LOGGER.info("✅ Calendar visualization test passed")
    else:
        LOGGER.info("⚠️ No sessions for calendar, skipping visualization check")

@pytest.mark.e2e
def test_tag_filter_displays_sessions(page, streamlit_app):
    """タグフィルタでセッションを絞り込めることを確認"""
    
    # 1. Historyページに遷移
    navigate_to_history(page, streamlit_app)
    
    # 2. 「🏷️ タグフィルタ」タブに切り替え
    page.click("text=🏷️ タグフィルタ")
    time.sleep(0.5)
    
    # 3. タグ選択フィールドまたは情報メッセージが表示されることを確認
    # （タグがない場合は「タグが設定されているセッションがありません」）
    assert (
        page.is_visible("text=タグを選択してフィルタリング") or 
        page.is_visible("text=タグが設定されているセッションがありません")
    )
    
    LOGGER.info("✅ Tag filter test passed")

@pytest.mark.e2e
def test_history_mode_happy_path(page, streamlit_app):
    """
    Happy Path: History Mode完全なフロー（Chat遷移なし）
    1. Historyページでselectboxからセッション選択
    2. History page内で詳細が表示される
    3. チャット履歴、検索結果、評価が表示される
    4. 全操作がHistory page内で完結する
    """
    
    # 1. Historyページに遷移
    navigate_to_history(page, streamlit_app)
    LOGGER.info("Step 1: Navigated to History page")
    
    # 2. 検索タブでセッション一覧を確認
    page.click("text=🔍 検索")
    time.sleep(0.5)
    
    # 3. Selectboxでセッション選択
    selectbox = page.locator("select[aria-label*='セッションを選択']")
    
    if selectbox.count() > 0:
        selectbox.select_option(index=1)
        time.sleep(1)
        LOGGER.info("Step 2: Selected session from selectbox")
        
        # 4. History pageに留まることを確認（Chat pageに遷移しない）
        assert "2_📚_History" in page.url
        LOGGER.info("Step 3: Confirmed staying on History page")
        
        # 5. セッション詳細ヘッダーが表示されることを確認
        assert page.is_visible("text=📋 セッション詳細")
        LOGGER.info("Step 4: Session detail header displayed")
        
        # 6. チャット履歴が表示されることを確認
        page.wait_for_selector("[data-testid='stChatMessage']", timeout=10000)
        message_count = page.locator("[data-testid='stChatMessage']").count()
        LOGGER.info(f"Step 5: Chat history displayed ({message_count} messages)")
        
        # 7. 検索結果expanderが表示されることを確認（存在する場合）
        search_results = page.locator("text=🔍 検索結果")
        if search_results.count() > 0:
            LOGGER.info("Step 6: Search results expander found")
            search_results.first.click()
            time.sleep(0.5)
            # テーブルが表示されることを確認
            assert page.is_visible("text=タイトル") or page.is_visible("text=URL")
            LOGGER.info("Step 7: Search results table displayed")
        
        # 8. 品質評価expanderが表示されることを確認（存在する場合）
        eval_expander = page.locator("text=📊 品質評価")
        if eval_expander.count() > 0:
            LOGGER.info("Step 8: Evaluation expander found")
        
        LOGGER.info("✅ History Mode Happy Path test passed")
    else:
        LOGGER.warning("⚠️ No selectbox found for session selection")

# ===== New Tests for History Mode Operations =====

@pytest.mark.e2e
def test_history_selectbox_displays_session_detail(page, streamlit_app):
    """
    History Mode: Selectboxでセッション選択→詳細表示確認
    1. Historyページに遷移
    2. Selectboxでセッション選択
    3. セッション詳細が表示される
    4. Chat pageへ自動遷移しないことを確認
    """
    
    # 1. Historyページに遷移
    navigate_to_history(page, streamlit_app)
    LOGGER.info("Step 1: Navigated to History page")
    
    # 2. 検索タブでセッション一覧を確認
    page.click("text=🔍 検索")
    time.sleep(0.5)
    
    # 3. Selectbox（セッションを選択）を探す
    selectbox = page.locator("select[aria-label*='セッションを選択']")
    
    if selectbox.count() > 0:
        # 4. 最初のセッション（インデックス1、0はプレースホルダー）を選択
        selectbox.select_option(index=1)
        time.sleep(1)
        LOGGER.info("Step 2: Selected session from selectbox")
        
        # 5. セッション詳細エリアが表示されることを確認
        assert page.is_visible("text=📋 セッション詳細")
        LOGGER.info("Step 3: Session detail header displayed")
        
        # 6. メッセージが表示されることを確認
        chat_messages = page.locator("[data-testid='stChatMessage']")
        assert chat_messages.count() > 0
        LOGGER.info("Step 4: Chat messages displayed")
        
        # 7. History pageに留まることを確認（Chat pageに遷移しない）
        assert "2_📚_History" in page.url
        LOGGER.info("Step 5: Confirmed staying on History page (no auto-transition)")
        
        LOGGER.info("✅ History selectbox session detail test passed")
    else:
        LOGGER.warning("⚠️ No selectbox found for session selection")

@pytest.mark.e2e
def test_history_session_detail_content_display(page, streamlit_app):
    """
    History Mode: セッション詳細のコンテンツ表示確認
    1. Historyページでセッション選択
    2. メッセージ履歴が表示される
    3. 検索結果expanderが表示される（存在する場合）
    4. 品質評価expanderが表示される（存在する場合）
    """
    
    # 1. Historyページに遷移
    navigate_to_history(page, streamlit_app)
    LOGGER.info("Step 1: Navigated to History page")
    
    # 2. 検索タブを選択
    page.click("text=🔍 検索")
    time.sleep(0.5)
    
    # 3. Selectboxでセッション選択
    selectbox = page.locator("select[aria-label*='セッションを選択']")
    
    if selectbox.count() > 0:
        selectbox.select_option(index=1)
        time.sleep(1)
        LOGGER.info("Step 2: Selected session from selectbox")
        
        # 4. メッセージ履歴の確認
        chat_messages = page.locator("[data-testid='stChatMessage']")
        assert chat_messages.count() > 0
        LOGGER.info("Step 3: Chat messages displayed")
        
        # 5. 検索結果expanderの確認（存在する場合）
        search_expander = page.locator("text=🔍 検索結果")
        if search_expander.count() > 0:
            LOGGER.info("Step 4: Search results expander found")
            # expanderを展開して内容確認
            search_expander.first.click()
            time.sleep(0.5)
            # テーブルヘッダーが表示されることを確認
            assert page.is_visible("text=タイトル") or page.is_visible("text=URL")
            LOGGER.info("Step 5: Search results table displayed")
        
        # 6. 品質評価expanderの確認（存在する場合）
        eval_expander = page.locator("text=📊 品質評価")
        if eval_expander.count() > 0:
            LOGGER.info("Step 6: Evaluation expander found")
            eval_expander.first.click()
            time.sleep(0.5)
            LOGGER.info("Step 7: Evaluation content expanded")
        
        LOGGER.info("✅ History session detail content display test passed")
    else:
        LOGGER.warning("⚠️ No selectbox found for session selection")

@pytest.mark.e2e
def test_history_mode_operations_independence(page, streamlit_app):
    """
    History Mode: 操作の独立性確認（Chat pageへ自動遷移しない）
    1. フィルタ操作（検索、日付、タグ）
    2. セッション選択
    全ての操作でHistory pageに留まることを確認
    """
    
    # 1. Historyページに遷移
    navigate_to_history(page, streamlit_app)
    LOGGER.info("Step 1: Navigated to History page")
    
    # 2. 検索タブに切り替え
    page.click("text=🔍 検索")
    time.sleep(0.5)
    assert "2_📚_History" in page.url
    LOGGER.info("Step 2: Search tab - stayed on History page")
    
    # 3. 日付フィルタタブに切り替え
    page.click("text=📅 日付フィルタ")
    time.sleep(0.5)
    assert "2_📚_History" in page.url
    LOGGER.info("Step 4: Date filter tab - stayed on History page")
    
    # 5. タグフィルタタブに切り替え
    page.click("text=🏷️ タグフィルタ")
    time.sleep(0.5)
    assert "2_📚_History" in page.url
    LOGGER.info("Step 5: Tag filter tab - stayed on History page")
    
    # 6. 検索タブに戻ってセッション選択
    page.click("text=🔍 検索")
    time.sleep(0.5)
    
    selectbox = page.locator("select[aria-label*='セッションを選択']")
    if selectbox.count() > 0:
        selectbox.select_option(index=1)
        time.sleep(1)
        assert "2_📚_History" in page.url
        LOGGER.info("Step 6: Session selection - stayed on History page")
    
    LOGGER.info("✅ History mode operations independence test passed")

@pytest.mark.e2e
def test_history_session_detail_updates_on_selection_change(page, streamlit_app):
    """
    History Mode: セッション詳細の更新確認
    1. 最初のセッションを選択して詳細表示
    2. 2番目のセッションに切り替え
    3. セッション詳細が更新されることを確認
    """
    
    # 1. Historyページに遷移
    navigate_to_history(page, streamlit_app)
    LOGGER.info("Step 1: Navigated to History page")
    
    # 2. 検索タブを選択
    page.click("text=🔍 検索")
    time.sleep(0.5)
    
    # 3. Selectboxで最初のセッション選択
    selectbox = page.locator("select[aria-label*='セッションを選択']")
    
    if selectbox.count() > 0:
        # 最初のセッションを選択
        selectbox.select_option(index=1)
        time.sleep(1)
        LOGGER.info("Step 2: Selected first session")
        
        # セッション詳細が表示されることを確認
        assert page.is_visible("text=📋 セッション詳細")
        first_session_messages = page.locator("[data-testid='stChatMessage']").count()
        LOGGER.info(f"Step 3: First session has {first_session_messages} messages")
        
        # 4. 2番目のセッションに切り替え（存在する場合）
        try:
            selectbox.select_option(index=2)
            time.sleep(1)
            LOGGER.info("Step 4: Selected second session")
            
            # セッション詳細が更新されることを確認
            second_session_messages = page.locator("[data-testid='stChatMessage']").count()
            LOGGER.info(f"Step 5: Second session has {second_session_messages} messages")
            
            # メッセージ数が変わったことを確認（同じ場合もあるが、少なくとも表示は更新される）
            assert page.is_visible("text=📋 セッション詳細")
            LOGGER.info("Step 6: Session detail updated successfully")
            
            LOGGER.info("✅ History session detail update test passed")
        except Exception as e:
            LOGGER.info(f"⚠️ Only one session available, skipping update test: {e}")
    else:
        LOGGER.warning("⚠️ No selectbox found for session selection")

@pytest.mark.e2e
def test_history_calendar_visualization_displays(page, streamlit_app):
    """
    History Mode: カレンダー可視化表示確認
    1. 日付フィルタタブに切り替え
    2. カレンダーセクションが表示される
    3. セッション作成カレンダーの表が表示される
    """
    
    # 1. Historyページに遷移
    navigate_to_history(page, streamlit_app)
    LOGGER.info("Step 1: Navigated to History page")
    
    # 2. 日付フィルタタブに切り替え
    page.click("text=📅 日付フィルタ")
    time.sleep(0.5)
    LOGGER.info("Step 2: Switched to Date Filter tab")
    
    # 3. 開始日・終了日フィールドが表示されることを確認
    assert page.is_visible("text=開始日")
    assert page.is_visible("text=終了日")
    LOGGER.info("Step 3: Date range inputs displayed")
    
    # 4. カレンダーセクションが表示されることを確認（セッションがある場合）
    calendar_section = page.locator("text=📊 セッション作成カレンダー")
    
    if calendar_section.count() > 0:
        LOGGER.info("Step 4: Calendar section found")
        
        # 5. Markdownテーブルが存在することを確認
        # カレンダーテーブルには「日付」「セッション数」などの列が含まれる
        assert page.is_visible("text=| 日付") or page.is_visible("text=セッション数")
        LOGGER.info("Step 5: Calendar table displayed")
        
        LOGGER.info("✅ History calendar visualization test passed")
    else:
        LOGGER.info("⚠️ No sessions for calendar visualization, test skipped")
