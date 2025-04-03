import pytest
from unittest.mock import Mock, patch, AsyncMock, MagicMock
from services.ebay_scraper import EbayScraper
from core.config_manager import ConfigManager
from core.database_manager import DatabaseManager
from datetime import datetime
import urllib.parse

@pytest.fixture
def mock_config():
    """設定のモック"""
    config = MagicMock()
    config.get = MagicMock(side_effect=lambda *args, **kwargs: {
        ('ebay', 'base_url'): 'https://www.ebay.com',
        ('ebay', 'username'): 'test_user',
        ('ebay', 'password'): 'test_pass',
        ('scraping', 'headless'): True,
        ('scraping', 'user_agent'): 'test_agent',
        ('ebay', 'search', 'request_delay'): 3,
        ('database', 'url'): 'sqlite:///:memory:',
        ('ebay', 'search', 'timeout'): 60,
    }.get(tuple(args[0]), args[1] if len(args) > 1 else None))
    
    config.get_with_env = MagicMock(side_effect=lambda *args, **kwargs: {
        (('ebay', 'base_url'), 'EBAY_BASE_URL'): 'https://www.ebay.com',
    }.get((tuple(args[0]), args[1]), args[2] if len(args) > 2 else None))
    
    return config

@pytest.fixture
def mock_db():
    """データベースのモック"""
    db = MagicMock()
    db.session_scope = AsyncMock()
    db.mark_keyword_as_processed = AsyncMock()
    return db

@pytest.fixture
def ebay_scraper(mock_config):
    """EbayScraperのインスタンス"""
    return EbayScraper(mock_config)

@patch.object(EbayScraper, '_get_random_user_agent')
def test_init(mock_random_ua, ebay_scraper, mock_config):
    """初期化のテスト"""
    # ユーザーエージェントのモック設定
    mock_random_ua.return_value = 'test_agent'
    
    assert ebay_scraper.base_url == 'https://www.ebay.com'
    assert ebay_scraper.headless is True
    assert ebay_scraper.request_delay == 3
    assert ebay_scraper.timeout == 60000  # タイムアウトを60秒に更新
    assert ebay_scraper.is_logged_in is False
    assert ebay_scraper.playwright is None
    assert ebay_scraper.additional_headers == {
        'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
        'Accept-Language': 'en-US,en;q=0.5',
        'Accept-Encoding': 'gzip, deflate, br',
        'DNT': '1',
        'Connection': 'keep-alive',
        'Upgrade-Insecure-Requests': '1',
        'Sec-Fetch-Dest': 'document',
        'Sec-Fetch-Mode': 'navigate',
        'Sec-Fetch-Site': 'none',
        'Sec-Fetch-User': '?1',
        'Pragma': 'no-cache',
        'Cache-Control': 'no-cache'
    }

@patch('services.ebay_scraper.sync_playwright')
@patch.object(EbayScraper, '_get_random_user_agent')
def test_start_browser(mock_random_ua, mock_playwright, ebay_scraper):
    """ブラウザ起動のテスト"""
    # ユーザーエージェントのモック設定
    mock_random_ua.return_value = 'test_agent'
    
    # Playwrightモックの設定
    mock_playwright_instance = MagicMock()
    mock_playwright.return_value.start.return_value = mock_playwright_instance
    
    # chromiumとcontextのモック設定
    mock_chromium = MagicMock()
    mock_playwright_instance.chromium = mock_chromium
    mock_browser = MagicMock()
    mock_chromium.launch.return_value = mock_browser
    mock_context = MagicMock()
    mock_browser.new_context.return_value = mock_context
    
    # メソッド実行
    result = ebay_scraper.start_browser()
    
    # 検証
    assert result is True
    assert ebay_scraper.playwright is not None
    assert ebay_scraper.browser is not None
    assert ebay_scraper.context is not None
    
    # ブラウザ起動オプションの確認
    mock_chromium.launch.assert_called_once_with(
        headless=True,
        args=[
            "--disable-blink-features=AutomationControlled",
            "--disable-features=IsolateOrigins,site-per-process",
            "--disable-site-isolation-trials",
            "--disable-dev-shm-usage",
            "--no-sandbox",
            "--disable-setuid-sandbox",
            "--disable-gpu",
            "--disable-infobars",
            "--window-size=1920,1080",
            "--start-maximized",
            "--ignore-certificate-errors",
            "--disable-accelerated-2d-canvas",
            "--disable-notifications"
        ]
    )
    
    # コンテキスト作成オプションの確認
    mock_browser.new_context.assert_called_once_with(
        viewport={"width": 1920, "height": 1080},
        screen={"width": 1920, "height": 1080},
        ignore_https_errors=True,
        java_script_enabled=True,
        bypass_csp=True,
        has_touch=True,
        is_mobile=False,
        locale="en-US",
        timezone_id="America/New_York",
        permissions=["geolocation"],
        color_scheme="light",
        reduced_motion="no-preference",
        forced_colors="none",
        extra_http_headers=ebay_scraper.additional_headers,
        user_agent='test_agent'
    )

@patch('services.ebay_scraper.sync_playwright')
def test_close_browser(mock_playwright, ebay_scraper):
    """ブラウザ終了のテスト"""
    # モックの設定
    mock_browser = MagicMock()
    mock_context = MagicMock()
    mock_playwright_instance = MagicMock()
    
    ebay_scraper.browser = mock_browser
    ebay_scraper.context = mock_context
    ebay_scraper.playwright = mock_playwright_instance
    ebay_scraper.is_logged_in = True
    
    # メソッド実行
    ebay_scraper.close_browser()
    
    # 検証
    mock_context.close.assert_called_once()
    mock_browser.close.assert_called_once()
    mock_playwright_instance.stop.assert_called_once()
    assert ebay_scraper.browser is None
    assert ebay_scraper.context is None
    assert ebay_scraper.playwright is None
    assert ebay_scraper.is_logged_in is False

@patch.object(EbayScraper, 'start_browser')
@patch.object(EbayScraper, '_extract_items_data')
@patch.object(EbayScraper, '_get_random_user_agent')
def test_search_keyword(mock_random_ua, mock_extract_items, mock_start_browser, ebay_scraper):
    """キーワード検索のテスト"""
    # max_pagesを1に設定
    ebay_scraper.max_pages = 1
    
    # モックの設定
    mock_start_browser.return_value = True
    mock_random_ua.return_value = 'test_agent'
    test_items = [
        {
            'item_id': '123',
            'title': 'Test Item 1',
            'price': 10.99,
            'currency': 'USD',
            'shipping_price': 0.0,
            'listing_type': 'fixed_price',
            'condition': 'New',
            'item_url': 'https://www.ebay.com/itm/123',
            'image_url': 'https://example.com/img1.jpg'
        },
        {
            'item_id': '456',
            'title': 'Test Item 2',
            'price': 20.50,
            'currency': 'USD',
            'shipping_price': 5.99,
            'listing_type': 'auction',
            'condition': 'Used',
            'item_url': 'https://www.ebay.com/itm/456',
            'image_url': 'https://example.com/img2.jpg'
        }
    ]
    mock_extract_items.return_value = test_items
    
    # Playwrightのコンテキストとページのモック
    mock_context = MagicMock()
    ebay_scraper.context = mock_context
    mock_page = MagicMock()
    mock_context.new_page.return_value = mock_page
    
    # responseのモック作成とstatusの設定
    mock_response = MagicMock()
    mock_response.status = 200  # ステータスコードを200に設定
    mock_page.goto.return_value = mock_response
    
    # ページコンテンツの設定（検索結果あり）
    mock_page.content.return_value = "検索結果が見つかりました。"

    # ページのセレクタモック
    mock_next_button = MagicMock()
    mock_next_button.is_enabled.return_value = False
    mock_page.query_selector.return_value = mock_next_button
    
    # 検索実行
    results = ebay_scraper.search_keyword('test keyword')
    
    # 検証
    assert results == test_items
    mock_start_browser.assert_called_once()
    mock_context.new_page.assert_called_once()
    mock_page.goto.assert_called_once()
    
    # wait_for_selectorが呼ばれていない問題を修正
    # eBayScraperではwait_for_selectorが使われていないため、この検証は削除
    # 代わりにwait_for_load_stateが呼び出されていることを確認
    mock_page.wait_for_load_state.assert_called_with("load")

@patch.object(EbayScraper, 'start_browser')
@patch.object(EbayScraper, '_extract_items_data')
@patch.object(EbayScraper, '_get_random_user_agent')
def test_search_keyword_with_filters(mock_random_ua, mock_extract_items, mock_start_browser, ebay_scraper):
    """フィルター付きキーワード検索のテスト"""
    # max_pagesを1に設定
    ebay_scraper.max_pages = 1
    
    # モックの設定
    mock_start_browser.return_value = True
    mock_random_ua.return_value = 'test_agent'
    test_items = [
        {
            'item_id': '123',
            'title': 'Test Item 1',
            'price': 10.99,
            'currency': 'USD',
            'listing_type': 'auction',
            'condition': 'Used',
            'item_url': 'https://www.ebay.com/itm/123',
        }
    ]
    mock_extract_items.return_value = test_items
    
    # Playwrightのコンテキストとページのモック
    mock_context = MagicMock()
    ebay_scraper.context = mock_context
    mock_page = MagicMock()
    mock_context.new_page.return_value = mock_page
    
    # responseのモック作成とstatusの設定
    mock_response = MagicMock()
    mock_response.status = 200  # ステータスコードを200に設定
    mock_page.goto.return_value = mock_response
    
    # ページコンテンツの設定（検索結果あり）
    mock_page.content.return_value = "検索結果が見つかりました。"

    # ページのセレクタモック
    mock_next_button = MagicMock()
    mock_next_button.is_enabled.return_value = False
    mock_page.query_selector.return_value = mock_next_button

    # 検索実行（フィルター付き）
    keyword = 'test keyword'
    encoded_keyword = urllib.parse.quote(keyword)
    results = ebay_scraper.search_keyword(
        keyword,
        category='550',
        condition='used',
        listing_type='auction',
        min_price=10.0,
        max_price=100.0
    )

    # 検証
    assert results == test_items
    
    # URLに正しいパラメータが含まれているか確認
    call_args = mock_page.goto.call_args[0][0]
    assert 'test+keyword' in call_args or 'test%20keyword' in call_args
    assert '_sacat=550' in call_args
    assert 'LH_ItemCondition=3000' in call_args  # 'used'に対応するコード
    assert 'LH_Auction=1' in call_args
    assert '_udlo=10.0' in call_args
    assert '_udhi=100.0' in call_args

@patch.object(EbayScraper, 'start_browser')
@patch.object(EbayScraper, '_extract_items_data')
@patch.object(EbayScraper, '_get_random_user_agent')
def test_search_keyword_japanese(mock_random_ua, mock_extract_items, mock_start_browser, ebay_scraper):
    """日本語キーワード検索のテスト"""
    # max_pagesを1に設定
    ebay_scraper.max_pages = 1
    
    # モックの設定
    mock_start_browser.return_value = True
    mock_random_ua.return_value = 'test_agent'
    test_items = [
        {
            'item_id': '123',
            'title': '日本語テストアイテム',
            'price': 10.99,
            'currency': 'JPY',
            'listing_type': 'fixed_price',
            'condition': 'New',
            'item_url': 'https://www.ebay.com/itm/123',
        }
    ]
    mock_extract_items.return_value = test_items
    
    # Playwrightのコンテキストとページのモック
    mock_context = MagicMock()
    ebay_scraper.context = mock_context
    mock_page = MagicMock()
    mock_context.new_page.return_value = mock_page
    
    # responseのモック作成とstatusの設定
    mock_response = MagicMock()
    mock_response.status = 200  # ステータスコードを200に設定
    mock_page.goto.return_value = mock_response
    
    # ページコンテンツの設定（検索結果あり）
    mock_page.content.return_value = "検索結果が見つかりました。"

    # ページのセレクタモック
    mock_next_button = MagicMock()
    mock_next_button.is_enabled.return_value = False
    mock_page.query_selector.return_value = mock_next_button

    # 日本語キーワードで検索
    keyword = '日本語検索'
    encoded_keyword = urllib.parse.quote(keyword, encoding='utf-8')
    results = ebay_scraper.search_keyword(keyword)

    # 検証
    assert results == test_items
    
    # URLに正しくエンコードされた日本語が含まれているか確認
    call_args = mock_page.goto.call_args[0][0]
    assert encoded_keyword in call_args

@patch.object(EbayScraper, '_get_random_user_agent')
def test_get_random_user_agent(mock_random_ua, ebay_scraper):
    """ランダムユーザーエージェント取得のテスト"""
    # テスト用のユーザーエージェント
    test_ua = "Mozilla/5.0 Test User Agent"
    mock_random_ua.return_value = test_ua
    
    # メソッド実行
    ua = ebay_scraper._get_random_user_agent()
    
    # 検証
    assert ua == test_ua
    mock_random_ua.assert_called_once()

@patch.object(EbayScraper, '_get_random_user_agent')
def test_get_request_headers(mock_random_ua, ebay_scraper):
    """リクエストヘッダー取得のテスト"""
    # テスト用のユーザーエージェント
    test_ua = "Mozilla/5.0 Test User Agent"
    mock_random_ua.return_value = test_ua
    
    # メソッド実行
    headers = ebay_scraper._get_request_headers()
    
    # 検証
    assert 'User-Agent' in headers
    assert headers['User-Agent'] == test_ua
    assert 'Accept' in headers
    assert 'Accept-Language' in headers
    mock_random_ua.assert_called_once()

@pytest.mark.parametrize("main_container_found", [True, False]) # メインコンテナが見つかる場合と見つからない場合をテスト
def test_extract_items_data(ebay_scraper, main_container_found):
    """商品データ抽出のテスト"""
    # モックページの作成
    mock_page = MagicMock()

    # 商品リスト要素のモック (共通)
    mock_item = MagicMock(name="mock_item")
    mock_item_link = MagicMock(name="mock_item_link")
    mock_item_link.get_attribute.return_value = "https://www.ebay.com/itm/123456789"
    mock_title_elem = MagicMock(name="mock_title_elem")
    mock_title_elem.inner_text.return_value = "  Test Item  " # 前後の空白を含むテスト
    mock_price_elem = MagicMock(name="mock_price_elem")
    mock_price_elem.inner_text.return_value = "  $10.99  "
    mock_shipping_elem = MagicMock(name="mock_shipping_elem")
    mock_shipping_elem.inner_text.return_value = "  Free shipping  "
    mock_seller_elem = MagicMock(name="mock_seller_elem")
    mock_seller_elem.inner_text.return_value = " seller123 (1,234) 99.8% "
    mock_condition_elem = MagicMock(name="mock_condition_elem")
    mock_condition_elem.inner_text.return_value = " New "
    mock_buy_it_now_elem = MagicMock(name="mock_buy_it_now_elem") # 固定価格用
    mock_img_elem = MagicMock(name="mock_img_elem")
    mock_img_elem.get_attribute.return_value = "https://example.com/img.jpg"

    # item.query_selector のモック (Lambdaではなく辞書で定義)
    item_selectors = {
        '.s-item__link': mock_item_link,
        '.s-item__title': mock_title_elem,
        '.s-item__price': mock_price_elem,
        '.s-item__shipping': mock_shipping_elem,
        '.s-item__seller-info-text': mock_seller_elem,
        '.s-item__bids': None,  # 入札なし
        '.s-item__subtitle': mock_condition_elem,
        '.s-item__dynamic.s-item__buyItNowOption': mock_buy_it_now_elem, # 固定価格
        '.s-item__time-left': None,  # オークションではない
        '.s-item__image-wrapper >img': mock_img_elem
    }
    mock_item.query_selector.side_effect = lambda selector: item_selectors.get(selector)

    # メインコンテナのモック
    mock_main_container = MagicMock(name="mock_main_container")
    mock_main_container.query_selector_all.return_value = [mock_item] # コンテナ内に1つのアイテム

    if main_container_found:
        # メインコンテナが見つかる場合の page.query_selector のモック
        page_selectors = {
            'ul.srp-results.srp-list': mock_main_container,
            '#srp-river-results > ul': None # 1つ目で見つかる想定
        }
        mock_page.query_selector.side_effect = lambda selector: page_selectors.get(selector)
        # フォールバック用の query_selector_all は呼ばれないはず
        mock_page.query_selector_all = MagicMock(name="page_qs_all", side_effect=AssertionError("コンテナが見つかった場合、これは呼ばれないはず"))

    else:
        # メインコンテナが見つからない場合の page.query_selector のモック
        page_selectors = {
            'ul.srp-results.srp-list': None,
            '#srp-river-results > ul': None
        }
        mock_page.query_selector.side_effect = lambda selector: page_selectors.get(selector)
        # フォールバック用の query_selector_all を設定
        mock_page.query_selector_all.return_value = [mock_item] # フォールバックで1つのアイテム

    # 商品データの抽出実行
    results = ebay_scraper._extract_items_data(mock_page)

    # --- 検証 ---
    assert len(results) == 1
    item_data = results[0]

    # 各フィールドの値の検証 (strip() が適用されているかも確認)
    assert item_data.get('item_id') == "123456789"
    assert item_data.get('title') == "Test Item"
    assert item_data.get('price') == 10.99
    assert item_data.get('currency') == "USD"
    assert item_data.get('shipping_price') == 0.0
    assert item_data.get('seller_name') == "seller123"
    assert item_data.get('seller_feedback_count') == 1234
    assert item_data.get('seller_rating') == 0.998
    assert item_data.get('bids_count') == 0 # 入札なし
    assert item_data.get('condition') == "New"
    assert item_data.get('listing_type') == "fixed_price" # BuyItNow要素があるため
    assert item_data.get('is_buy_it_now') is True
    assert 'auction_end_time' not in item_data # オークションではない
    assert item_data.get('image_url') == "https://example.com/img.jpg"

    # どのパスでアイテムが取得されたか確認
    if main_container_found:
        mock_page.query_selector.assert_any_call('ul.srp-results.srp-list') # 呼ばれたはず
        mock_main_container.query_selector_all.assert_called_once_with(':scope > li.s-item') # :scopeセレクタ確認
        mock_page.query_selector_all.assert_not_called() # フォールバックは呼ばれていない
    else:
        mock_page.query_selector.assert_any_call('ul.srp-results.srp-list')
        mock_page.query_selector.assert_any_call('#srp-river-results > ul')
        mock_page.query_selector_all.assert_called_once_with('li.s-item:has(div.s-item__image-wrapper)') # フォールバックセレクタ確認
        mock_main_container.query_selector_all.assert_not_called() # メインコンテナのメソッドは呼ばれない

@patch('pathlib.Path.mkdir')
def test_save_debug_screenshot(mock_mkdir, ebay_scraper):
    """デバッグスクリーンショット保存のテスト"""
    # モックページの作成
    mock_page = MagicMock()
    mock_page.screenshot = MagicMock()
    
    # スクリーンショット保存実行
    ebay_scraper._save_debug_screenshot(mock_page, "test keyword")
    
    # 検証
    mock_mkdir.assert_called_once_with(parents=True, exist_ok=True)
    mock_page.screenshot.assert_called_once()
    # スクリーンショットのパス検証
    assert "error_test_keyword_" in mock_page.screenshot.call_args[1]['path']
    assert mock_page.screenshot.call_args[1]['path'].endswith(".png")

def test_context_manager(ebay_scraper):
    """コンテキストマネージャのテスト"""
    with patch.object(ebay_scraper, 'start_browser') as mock_start:
        with patch.object(ebay_scraper, 'close_browser') as mock_close:
            mock_start.return_value = True
            
            # with文を使用
            with ebay_scraper as scraper:
                assert scraper is ebay_scraper
                mock_start.assert_called_once()
                mock_close.assert_not_called()
                
            # with文を抜けた後
            mock_close.assert_called_once()
