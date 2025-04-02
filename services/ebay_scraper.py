# eBayスクレイピングを行うクラス

import logging
from pathlib import Path
import time
import re
from datetime import datetime, timedelta
from playwright.sync_api import sync_playwright, TimeoutError as PlaywrightTimeoutError
from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception_type
import random
import os
import requests
import urllib.parse

logger = logging.getLogger(__name__)

# ユーザーエージェントリスト
USER_AGENTS = [
    'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
    'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/92.0.4515.107 Safari/537.36',
    'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/14.1.1 Safari/605.1.15',
    'Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:90.0) Gecko/20100101 Firefox/90.0',
    'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.114 Safari/537.36',
    'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/92.0.4515.107 Safari/537.36',
]

# 共通のヘッダー情報
COMMON_HEADERS = {
    'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
    'Accept-Language': 'en-US,en;q=0.5',
    'Accept-Encoding': 'gzip, deflate, br',
    'Connection': 'keep-alive',
    'Upgrade-Insecure-Requests': '1',
    'Sec-Fetch-Dest': 'document',
    'Sec-Fetch-Mode': 'navigate',
    'Sec-Fetch-Site': 'none',
    'Sec-Fetch-User': '?1',
    'DNT': '1',
}

class EbayScraper:
    """
    Playwrightを使用してeBayのデータをスクレイピングするクラス
    """
    
    def __init__(self, config=None):
        """
        EbayScraperの初期化
        
        Args:
            config (ConfigManager, optional): 設定マネージャー
        """
        self.config = config or {}
        
        # 基本設定
        self.base_url = self.config.get_with_env(
            ['ebay', 'base_url'],
            'EBAY_BASE_URL',
            "https://www.ebay.com",
            str
        )
        
        # 検索設定
        self.timeout = self.config.get(['ebay', 'search', 'timeout'], 30, int) * 1000
        self.request_delay = self.config.get(['ebay', 'search', 'request_delay'], 2, float)
        self.max_pages = self.config.get(['ebay', 'search', 'max_pages'], 2, int)
        self.items_per_page = self.config.get(['ebay', 'search', 'items_per_page'], 50, int)
        
        # スクレイピング設定
        self.headless = self.config.get(['scraping', 'headless'], True, bool)
        self.proxy_enabled = self.config.get(['scraping', 'proxy', 'enabled'], False, bool)
        self.proxy_url = self.config.get(['scraping', 'proxy', 'url'], None, str)
        
        # ブラウザとコンテキストの初期化
        self.playwright = None
        self.browser = None
        self.context = None
        self.user_agent = None
        self.is_logged_in = False
        
        # 追加のヘッダー情報
        self.additional_headers = {
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
        
        # ログイン情報
        self.username = self.config.get_from_env("EBAY_USERNAME", None)
        self.password = self.config.get_from_env("EBAY_PASSWORD", None)
        
        # requestsモジュールをクラス属性として保持
        self.requests = requests
        
    def _get_random_user_agent(self):
        """
        ランダムなユーザーエージェントを返す
        
        Returns:
            str: ランダムなユーザーエージェント文字列
        """
        default_ua = self.config.get(['scraping', 'user_agent'])
        if default_ua and random.random() < 0.3:  # 30%の確率で設定ファイルのUAを使用
            return default_ua
        return random.choice(USER_AGENTS)
    
    def _get_request_headers(self):
        """
        リクエスト用のヘッダーを取得
        
        Returns:
            dict: ヘッダー情報
        """
        headers = COMMON_HEADERS.copy()
        headers['User-Agent'] = self._get_random_user_agent()
        # リクエストのたびに少しずつ異なるRefererを使用
        if random.random() < 0.5:  # 50%の確率でリファラーを含める
            referers = [
                'https://www.google.com/',
                'https://www.bing.com/',
                f"{self.base_url}/",
                None
            ]
            referer = random.choice(referers)
            if referer:
                headers['Referer'] = referer
        
        return headers
    
    def start_browser(self):
        """
        ブラウザを起動し、新しいコンテキストを作成する
        
        Returns:
            bool: ブラウザの起動に成功したかどうか
        """
        try:
            # すでに起動している場合は何もしない
            if self.browser and self.context:
                return True
                
            # Playwrightの起動
            self.playwright = sync_playwright().start()
            
            # ブラウザ起動オプションの設定
            browser_options = {
                "headless": self.headless,
                "args": [
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
            }
            
            # プロキシ設定（必要な場合）
            if self.proxy_enabled and self.proxy_url:
                browser_options["proxy"] = {
                    "server": self.proxy_url
                }
            
            # ブラウザ起動
            self.browser = self.playwright.chromium.launch(**browser_options)
            
            # コンテキスト作成オプション
            context_options = {
                "viewport": {"width": 1920, "height": 1080},
                "screen": {"width": 1920, "height": 1080},
                "ignore_https_errors": True,
                "java_script_enabled": True,
                "bypass_csp": True,
                "has_touch": True,
                "is_mobile": False,
                "locale": "en-US",
                "timezone_id": "America/New_York",
                "permissions": ["geolocation"],
                "color_scheme": "light",
                "reduced_motion": "no-preference",
                "forced_colors": "none",
                "extra_http_headers": self.additional_headers
            }
            
            # ユーザーエージェント設定
            self.user_agent = self._get_random_user_agent()
            if self.user_agent:
                context_options["user_agent"] = self.user_agent
                
            # コンテキスト作成
            self.context = self.browser.new_context(**context_options)
            
            # タイムアウト設定
            self.context.set_default_timeout(self.timeout)
            
            # ランダムなJavaScriptフォントとプラグイン指紋情報を設定（指紋対策）
            if random.random() < 0.7:  # 70%の確率で偽装を行う
                self.context.add_init_script("""
                    // Webdriver検出の回避
                    Object.defineProperty(navigator, 'webdriver', { get: () => false });
                    
                    // ランダムなCanvas指紋を生成
                    const originalGetContext = HTMLCanvasElement.prototype.getContext;
                    HTMLCanvasElement.prototype.getContext = function(type) {
                        const context = originalGetContext.apply(this, arguments);
                        if (type === '2d') {
                            const originalFillText = context.fillText;
                            context.fillText = function() {
                                context.shadowColor = `rgb(${Math.floor(Math.random()*255)},${Math.floor(Math.random()*255)},${Math.floor(Math.random()*255)})`;
                                return originalFillText.apply(this, arguments);
                            };
                        }
                        return context;
                    };
                    
                    // プラグイン情報の偽装
                    Object.defineProperty(navigator, 'plugins', {
                        get: () => [
                            {
                                0: {type: "application/x-google-chrome-pdf", suffixes: "pdf", description: "Portable Document Format"},
                                description: "Portable Document Format",
                                filename: "internal-pdf-viewer",
                                length: 1,
                                name: "Chrome PDF Plugin"
                            }
                        ]
                    });
                    
                    // 言語設定の偽装
                    Object.defineProperty(navigator, 'languages', {
                        get: () => ['en-US', 'en']
                    });
                    
                    // プラットフォーム情報の偽装
                    Object.defineProperty(navigator, 'platform', {
                        get: () => 'Win32'
                    });
                    
                    // WebGL指紋の偽装
                    const getParameter = WebGLRenderingContext.prototype.getParameter;
                    WebGLRenderingContext.prototype.getParameter = function(parameter) {
                        if (parameter === 37445) {
                            return 'Intel Inc.'
                        }
                        if (parameter === 37446) {
                            return 'Intel(R) Iris(TM) Graphics 6100'
                        }
                        return getParameter.apply(this, [parameter]);
                    };
                """)
            
            logger.info("ブラウザを起動しました")
            return True
            
        except Exception as e:
            logger.error(f"ブラウザの起動に失敗しました: {e}")
            self.close_browser()
            return False
    
    def close_browser(self):
        """
        ブラウザとプレイライトインスタンスを閉じる
        """
        try:
            if self.context:
                self.context.close()
                self.context = None
                
            if self.browser:
                self.browser.close()
                self.browser = None
                
            if self.playwright:
                self.playwright.stop()
                self.playwright = None
                
            self.is_logged_in = False
            
            logger.info("ブラウザを閉じました")
        except Exception as e:
            logger.error(f"ブラウザを閉じる際にエラーが発生しました: {e}")
    
    def login(self, retry_on_failure=True):
        """
        eBayにログインする
        
        Args:
            retry_on_failure (bool): ログイン失敗時に再試行するかどうか
            
        Returns:
            bool: ログインに成功したかどうか
        """
        if not self.username or not self.password:
            logger.warning("ログイン情報が設定されていません。ログインなしでスクレイピングを続行します。")
            return False
            
        if self.is_logged_in:
            logger.info("すでにログインしています")
            return True
            
        if not self.start_browser():
            return False
            
        try:
            logger.info("eBayにログインしています...")
            
            # 新しいページを開く
            page = self.context.new_page()
            
            # eBayのログインページに移動
            page.goto(f"{self.base_url}/signin/")
            
            # ログインフォームが読み込まれるまで待機
            page.wait_for_selector('#userid', state="visible")
            
            # ユーザー名を入力
            page.fill('#userid', self.username)
            
            # 次へボタンをクリック
            page.click('#signin-continue-btn')
            
            # パスワード入力フォームが表示されるまで待機
            page.wait_for_selector('#pass', state="visible")
            
            # パスワードを入力
            page.fill('#pass', self.password)
            
            # ログインボタンをクリック
            page.click('#sgnBt')
            
            # ログイン後のページが読み込まれるまで待機
            page.wait_for_load_state('networkidle')
            
            # ログイン成功の確認
            # 通常はユーザー名が表示されるか、特定の要素が存在するかで判断
            if page.url.startswith(f"{self.base_url}/signin/") or 'signin.ebay' in page.url:
                logger.error("ログインに失敗しました。認証情報を確認してください。")
                # CAPTCHA対策などが必要な場合はここに実装
                page.close()
                return False
            
            logger.info("eBayへのログインに成功しました")
            self.is_logged_in = True
            page.close()
            return True
            
        except Exception as e:
            logger.error(f"ログイン中にエラーが発生しました: {e}")
            if retry_on_failure:
                logger.info("5秒後に再試行します...")
                time.sleep(5)
                return self.login(retry_on_failure=False)
            return False
    
    @retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=2, max=10),
           retry=retry_if_exception_type((PlaywrightTimeoutError, ConnectionError)))
    def search_keyword(self, keyword, category=None, condition=None, listing_type=None, min_price=None, max_price=None):
        """
        キーワードで商品を検索する
        
        Args:
            keyword (str): 検索キーワード
            category (str, optional): カテゴリーID
            condition (str, optional): 商品の状態
            listing_type (str, optional): 出品タイプ
            min_price (float, optional): 最低価格
            max_price (float, optional): 最高価格
            
        Returns:
            list: 検索結果のアイテムリスト
        """
        try:
            # ブラウザが起動していない場合は起動
            if not self.browser or not self.context:
                if not self.start_browser():
                    logger.error("ブラウザの起動に失敗しました")
                    return []
            
            # 検索URLの構築
            params = {
                '_nkw': keyword,
                '_ipg': 60,  # 1ページあたりの表示件数を100件に制限
            }
            
            # カテゴリーの追加
            if category:
                params['_sacat'] = category
                
            # 価格範囲の追加
            if min_price is not None:
                params['_udlo'] = min_price
            if max_price is not None:
                params['_udhi'] = max_price
                
            # 商品の状態
            if condition:
                condition_map = {
                    'new': '1000',
                    'used': '3000',
                    'not_specified': '10'
                }
                if condition.lower() in condition_map:
                    params['LH_ItemCondition'] = condition_map[condition.lower()]
                    
            # 出品タイプ
            if listing_type:
                listing_type_map = {
                    'auction': ('LH_Auction', '1'),
                    'buy_it_now': ('LH_BIN', '1'),
                    'best_offer': ('LH_BO', '1')
                }
                if listing_type.lower() in listing_type_map:
                    param_key, param_value = listing_type_map[listing_type.lower()]
                    params[param_key] = param_value
            
            all_items = []
            current_page = 1
            max_retries = 3
            
            while current_page <= self.max_pages:
                try:
                    # ページ番号を追加
                    params['_pgn'] = current_page
                    
                    # 検索URLの生成
                    search_url = f"{self.base_url}/sch/i.html"
                    # 日本語キーワードの特別なエンコード処理
                    encoded_params = {}
                    for k, v in params.items():
                        if k == '_nkw':
                            # 日本語キーワードの場合は特別なエンコード処理
                            encoded_params[k] = urllib.parse.quote(str(v), encoding='utf-8', safe='')
                        else:
                            encoded_params[k] = urllib.parse.quote(str(v))
                    query_string = '&'.join([f"{k}={v}" for k, v in encoded_params.items()])
                    url = f"{search_url}?{query_string}"
                    
                    logger.info(f"ページ {current_page} を処理中: {url}")
                    
                    # 新しいページを開く
                    page = self.context.new_page()
                    try:
                        # 検索ページに移動
                        page.goto(url)
                        page.wait_for_selector('.srp-results', state="visible", timeout=self.timeout)
                        
                        # 商品データの抽出
                        items = self._extract_items_data(page)
                        
                        if not items:  # アイテムが見つからない場合は終了
                            logger.info(f"ページ {current_page} にアイテムが見つかりませんでした。検索を終了します。")
                            break
                            
                        all_items.extend(items)
                        logger.info(f"ページ {current_page} から {len(items)} 件のアイテムを抽出しました（合計: {len(all_items)} 件）")
                        
                        # 次のページが存在するか確認
                        next_page = page.query_selector('.pagination__next:not(.disabled)')
                        if not next_page:
                            logger.info("最後のページに到達しました。")
                            break
                            
                        # ページ間の待機時間（レート制限対策）
                        delay = self.request_delay + random.uniform(1, 3)
                        logger.debug(f"{delay:.2f}秒間待機します")
                        time.sleep(delay)
                        
                    except PlaywrightTimeoutError as e:
                        logger.warning(f"タイムアウトが発生しました: {str(e)}")
                        self._save_debug_screenshot(page, f"{keyword}_page_{current_page}")
                        if max_retries > 0:
                            max_retries -= 1
                            continue
                        else:
                            break
                    except Exception as e:
                        logger.error(f"ページ {current_page} の処理中にエラーが発生しました: {str(e)}")
                        self._save_debug_screenshot(page, f"{keyword}_page_{current_page}")
                        break
                    finally:
                        page.close()
                        
                    current_page += 1
                    
                except Exception as e:
                    logger.error(f"ページ {current_page} の処理中にエラーが発生しました: {str(e)}")
                    break
                    
            return all_items
                
        except Exception as e:
            logger.error(f"検索処理中にエラーが発生しました: {str(e)}")
            return []
    
    def _extract_items_data(self, page):
        """
        ページから商品データを抽出する
        
        Args:
            page: Playwrightのページオブジェクト
            
        Returns:
            list: 商品データのリスト
        """
        results = []
        
        # 商品リスト要素を取得
        items = page.query_selector_all('li.s-item')
        
        for item in items:
            try:
                # 広告をスキップ
                if item.query_selector('.s-item__info-col .s-item__title--tagblock'):
                    continue
                    
                # 商品データを抽出
                item_data = {}
                
                # 商品ID
                item_link = item.query_selector('.s-item__link')
                if item_link:
                    item_url = item_link.get_attribute('href')
                    item_data['item_url'] = item_url
                    # URLから商品IDを抽出
                    item_id_match = re.search(r'/itm/(\d+)', item_url)
                    if item_id_match:
                        item_data['item_id'] = item_id_match.group(1)
                        
                # 商品タイトル
                title_elem = item.query_selector('.s-item__title')
                if title_elem:
                    item_data['title'] = title_elem.inner_text().strip()
                
                # 価格
                price_elem = item.query_selector('.s-item__price')
                if price_elem:
                    price_text = price_elem.inner_text().strip()
                    
                    if '$' in price_text: #ドルの場合
                        # 価格から数値を抽出
                        price_match = re.search(r'\$(\d{1,3}(?:,\d{3})*\.\d{2})', price_text)
                        if price_match:
                            item_data['price'] = float(price_match.group(1).replace(',', ''))
                            item_data['currency'] = 'USD'  # デフォルトはUSD
                    else: # 円の場合
                        # 価格から数値を抽出
                        price_match = re.search(r'(\d{1,3}(?:,\d{3})*|\d+)\s*(?:円|JPY)', price_text)
                        if price_match:
                            item_data['price'] = float(price_match.group(1).replace(',', ''))
                            item_data['currency'] = 'JPY'  # デフォルトはJPY
                        
                # 送料
                shipping_elem = item.query_selector('.s-item__shipping')
                if shipping_elem:
                    shipping_text = shipping_elem.inner_text().strip()
                    if 'Free' in shipping_text or '無料' in shipping_text:
                        item_data['shipping_price'] = 0.0
                    else:
                        # 送料から数値を抽出
                        shipping_match = re.search(r"(\d{1,3}(?:,\d{3})*)\s*(?:円|JPY)", shipping_text)
                        if shipping_match:
                            item_data['shipping_price'] = float(shipping_match.group(1).replace(',', ''))
                        
                # TODO: 出品者情報を抽出できない場合がある（例：Discount Computer Depot（128967）98.7%）
                # 出品者情報
                seller_elem = item.query_selector('.s-item__seller-info-text')
                if seller_elem:
                    seller_text = seller_elem.inner_text().strip()
                    seller_name_match = re.search(r"([a-zA-Z0-9_ -]+)\s\((\d{1,3}(?:,\d{3})*)\)\s(\d+(?:\.\d+)?%)", seller_text)
                    if seller_name_match:
                        # 出品者名を抽出
                        item_data['seller_name'] = seller_name_match.group(1).strip()
                        # 評価数を抽出
                        item_data['seller_feedback_count'] = int(seller_name_match.group(2).replace(",","").strip())
                        # 評価を抽出
                        item_data['seller_rating'] = float(seller_name_match.group(3).replace("%","")) / 100.0
                    else:
                        print(f"出品者情報の抽出に失敗: {seller_text}")
                                            
                # 入札数
                bids_elem = item.query_selector('.s-item__bids')
                if bids_elem:
                    bids_text = bids_elem.inner_text().strip()
                    bids_match = re.search(r'(\d+) bid', bids_text)
                    if bids_match:
                        item_data['bids_count'] = int(bids_match.group(1))
                    else:
                        item_data['bids_count'] = 0
                else:
                    item_data['bids_count'] = 0
                    
                # 在庫数（完全に正確ではない場合があります）
                item_data['stock_quantity'] = 1  # デフォルトは1
                
                # 商品の状態
                condition_elem = item.query_selector('.s-item__subtitle')
                if condition_elem:
                    item_data['condition'] = condition_elem.inner_text().strip()
                    
                # リスティングタイプ（オークションor固定価格）
                if 'bids_count' in item_data and item_data['bids_count'] > 0:
                    item_data['listing_type'] = 'auction'
                else:
                    buy_it_now_elem = item.query_selector('.s-item__dynamic.s-item__buyItNowOption')
                    if buy_it_now_elem:
                        item_data['listing_type'] = 'fixed_price'
                        item_data['is_buy_it_now'] = True
                    else:
                        item_data['listing_type'] = 'unknown'
                        
                # オークション終了時間
                time_left_elem = item.query_selector('.s-item__time-left')
                if time_left_elem:
                    time_left_text = time_left_elem.inner_text().strip()
                    # 例: "1d 2h left" から時間を計算
                    days_match = re.search(r'(\d+)d', time_left_text)
                    hours_match = re.search(r'(\d+)h', time_left_text)
                    minutes_match = re.search(r'(\d+)m', time_left_text)
                    
                    days = int(days_match.group(1)) if days_match else 0
                    hours = int(hours_match.group(1)) if hours_match else 0
                    minutes = int(minutes_match.group(1)) if minutes_match else 0
                    
                    # 現在時刻から終了時間を計算
                    end_time = datetime.now() + timedelta(days=days, hours=hours, minutes=minutes)
                    item_data['auction_end_time'] = end_time
                
                # 画像URL
                img_elem = item.query_selector('.s-item__image-wrapper >img')
                if img_elem:
                    item_data['image_url'] = img_elem.get_attribute('src')
                    
                # 結果リストに追加
                results.append(item_data)
                
            except Exception as e:
                logger.warning(f"商品データの抽出中にエラーが発生しました: {e}")
                continue
                
        return results
    
    def _save_debug_screenshot(self, page, keyword):
        """
        デバッグ用のスクリーンショットを保存する
        
        Args:
            page: Playwrightのページオブジェクト
            keyword: エラーが発生した検索キーワード
        """
        try:
            # データディレクトリ
            debug_dir = Path(__file__).parent.parent / 'logs' / 'screenshots'
            debug_dir.mkdir(parents=True, exist_ok=True)
            
            # タイムスタンプ付きのファイル名
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            file_name = f"error_{keyword.replace(' ', '_')}_{timestamp}.png"
            screenshot_path = debug_dir / file_name
            
            # スクリーンショットの保存
            page.screenshot(path=str(screenshot_path))
            logger.info(f"エラー発生時のスクリーンショットを保存しました: {screenshot_path}")
            
        except Exception as e:
            logger.error(f"スクリーンショットの保存中にエラーが発生しました: {e}")
    
    def _scroll_page(self, page):
        """
        ページを下までスクロールして、すべてのコンテンツを読み込む
        
        Args:
            page: Playwrightのページオブジェクト
        """
        try:
            # ページの高さを取得
            page_height = page.evaluate("""() => {
                return Math.max(
                    document.body.scrollHeight,
                    document.documentElement.scrollHeight,
                    document.body.offsetHeight,
                    document.documentElement.offsetHeight,
                    document.body.clientHeight,
                    document.documentElement.clientHeight
                );
            }""")
            
            # スクロール位置
            current_position = 0
            scroll_step = 100
            
            while current_position < page_height:
                # スクロール実行
                page.evaluate(f"window.scrollTo(0, {current_position});")
                # ランダムな待機時間（100-300ms）
                time.sleep(random.uniform(0.1, 0.3))
                current_position += scroll_step
                
            # ページトップに戻る（自然な動作をシミュレート）
            page.evaluate("window.scrollTo(0, 0);")
            
        except Exception as e:
            logger.warning(f"ページスクロール中にエラーが発生しました: {e}")
    
    def __enter__(self):
        """
        コンテキストマネージャのエントリーポイント
        """
        self.start_browser()
        return self
        
    def __exit__(self, exc_type, exc_val, exc_tb):
        """
        コンテキストマネージャの終了処理
        """
        self.close_browser()
