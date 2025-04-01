import pytest
from unittest.mock import Mock, patch, AsyncMock, MagicMock
from services.ebay_scraper import EbayScraper
from core.config_manager import ConfigManager
from core.database_manager import DatabaseManager
from datetime import datetime

@pytest.fixture
def mock_config():
    """設定のモック"""
    config = MagicMock()
    config.get = lambda path, default=None: {
        ('ebay', 'base_url'): 'https://www.ebay.com',
        ('ebay', 'username'): 'test_user',
        ('ebay', 'password'): 'test_pass',
        ('scraping', 'headless'): True,
        ('scraping', 'user_agent'): 'test_agent',
        ('ebay', 'search', 'request_delay'): 2
    }.get(tuple(path), default)
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

def test_init(ebay_scraper, mock_config):
    """初期化のテスト"""
    assert ebay_scraper.base_url == 'https://www.ebay.com'
    assert ebay_scraper.headless is True
    assert ebay_scraper.user_agent == 'test_agent'
    assert ebay_scraper.request_delay == 2
    assert ebay_scraper.is_logged_in is False
    assert ebay_scraper.playwright is None

@patch('services.ebay_scraper.sync_playwright')
def test_start_browser(mock_playwright, ebay_scraper):
    """ブラウザ起動のテスト"""
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
    mock_chromium.launch.assert_called_once_with(headless=True)
    
    # コンテキスト作成オプションの確認
    mock_browser.new_context.assert_called_once_with(
        viewport={"width": 1280, "height": 800},
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
def test_login_success(mock_start_browser, ebay_scraper):
    """ログイン成功のテスト"""
    # start_browserのモック
    mock_start_browser.return_value = True
    
    # Playwrightのコンテキストとページのモック
    mock_context = MagicMock()
    ebay_scraper.context = mock_context
    mock_page = MagicMock()
    mock_context.new_page.return_value = mock_page
    
    # ログイン後のURLをモック（ログイン成功を示す）
    mock_page.url = 'https://www.ebay.com/myebay/summary'
    
    # ログイン実行
    result = ebay_scraper.login()
    
    # 検証
    assert result is True
    assert ebay_scraper.is_logged_in is True
    mock_page.goto.assert_called_once_with('https://www.ebay.com/signin/')
    mock_page.wait_for_selector.assert_any_call('#userid', state="visible")
    mock_page.fill.assert_any_call('#userid', ebay_scraper.username)
    mock_page.click.assert_any_call('#signin-continue-btn')
    mock_page.close.assert_called_once()

@patch.object(EbayScraper, 'start_browser')
def test_login_failure(mock_start_browser, ebay_scraper):
    """ログイン失敗のテスト"""
    # start_browserのモック
    mock_start_browser.return_value = True
    
    # Playwrightのコンテキストとページのモック
    mock_context = MagicMock()
    ebay_scraper.context = mock_context
    mock_page = MagicMock()
    mock_context.new_page.return_value = mock_page
    
    # ログイン後のURLをモック（ログイン失敗を示す）
    mock_page.url = 'https://www.ebay.com/signin/'
    
    # ログイン実行
    result = ebay_scraper.login(retry_on_failure=False)
    
    # 検証
    assert result is False
    assert ebay_scraper.is_logged_in is False
    mock_page.goto.assert_called_once_with('https://www.ebay.com/signin/')
    mock_page.close.assert_called_once()

@patch.object(EbayScraper, 'start_browser')
@patch.object(EbayScraper, '_extract_items_data')
def test_search_keyword(mock_extract_items, mock_start_browser, ebay_scraper):
    """キーワード検索のテスト"""
    # モックの設定
    mock_start_browser.return_value = True
    test_items = [
        {'item_id': '123', 'title': 'Test Item 1', 'price': 10.99},
        {'item_id': '456', 'title': 'Test Item 2', 'price': 20.50}
    ]
    mock_extract_items.return_value = test_items
    
    # Playwrightのコンテキストとページのモック
    mock_context = MagicMock()
    ebay_scraper.context = mock_context
    mock_page = MagicMock()
    mock_context.new_page.return_value = mock_page
    
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
    mock_page.wait_for_selector.assert_called_with('.srp-results', state="visible")
    mock_extract_items.assert_called_once_with(mock_page)
    mock_page.close.assert_called_once()

@patch.object(EbayScraper, 'start_browser')
def test_search_keyword_with_filters(mock_start_browser, ebay_scraper):
    """フィルター付きキーワード検索のテスト"""
    # モックの設定
    mock_start_browser.return_value = True
    
    # Playwrightのコンテキストとページのモック
    mock_context = MagicMock()
    ebay_scraper.context = mock_context
    mock_page = MagicMock()
    mock_context.new_page.return_value = mock_page
    
    # _extract_items_dataのモック
    with patch.object(ebay_scraper, '_extract_items_data', return_value=[]):
        # 検索実行
        ebay_scraper.search_keyword(
            'test keyword', 
            category='123', 
            condition='new', 
            listing_type='auction', 
            min_price=10, 
            max_price=100
        )
        
        # URLの検証
        expected_url = 'https://www.ebay.com/sch/i.html?_nkw=test+keyword&_sacat=123&_udlo=10&_udhi=100&LH_Auction=1&LH_ItemCondition=1000'
        mock_page.goto.assert_called_once()
        call_args = mock_page.goto.call_args[0][0]
        
        # URL内の全てのパラメータが含まれているか確認
        assert '_nkw=test+keyword' in call_args
        assert '_sacat=123' in call_args
        assert '_udlo=10' in call_args
        assert '_udhi=100' in call_args
        assert 'LH_Auction=1' in call_args
        assert 'LH_ItemCondition=1000' in call_args

def test_extract_items_data(ebay_scraper):
    """商品データ抽出のテスト"""
    # モックページの作成
    mock_page = MagicMock()
    
    # 商品リスト要素のモック
    mock_item = MagicMock()
    mock_item_link = MagicMock()
    mock_item_link.get_attribute.return_value = "https://www.ebay.com/itm/123456789"
    mock_item.query_selector.side_effect = lambda selector: {
        '.s-item__link': mock_item_link,
        '.s-item__info-col .s-item__title--tagblock': None,  # 広告ではない
        '.s-item__title': MagicMock(inner_text=lambda: "Test Item"),
        '.s-item__price': MagicMock(inner_text=lambda: "$10.99"),
        '.s-item__shipping': MagicMock(inner_text=lambda: "Free shipping"),
        '.s-item__seller-info-text': MagicMock(inner_text=lambda: "seller123 (1,234) 99.8%"),
        '.s-item__bids': None,  # 入札なし
        '.s-item__subtitle': MagicMock(inner_text=lambda: "New"),
        '.s-item__dynamic.s-item__buyItNowOption': MagicMock(),
        '.s-item__time-left': None,  # オークションではない
        '.s-item__image-wrapper >img': MagicMock(get_attribute=lambda attr: "https://example.com/img.jpg" if attr == 'src' else None)
    }.get(selector, None)
    
    # query_selector_allのモック
    mock_page.query_selector_all.return_value = [mock_item]
    
    # 商品データの抽出実行
    results = ebay_scraper._extract_items_data(mock_page)
    
    # 検証
    assert len(results) == 1
    item_data = results[0]
    assert item_data['item_id'] == "123456789"
    assert item_data['title'] == "Test Item"
    assert item_data['price'] == 10.99
    assert item_data['currency'] == "USD"
    assert item_data['shipping_price'] == 0.0
    assert item_data['listing_type'] == "fixed_price"
    assert item_data['condition'] == "New"
    assert item_data['image_url'] == "https://example.com/img.jpg"

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
