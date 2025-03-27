# eBayスクレイピングを行うクラス

import logging
import time
import re
from datetime import datetime, timedelta
from playwright.sync_api import sync_playwright, TimeoutError as PlaywrightTimeoutError
from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception_type
import random
import os

logger = logging.getLogger(__name__)

class EbayScraper:
    """
    Playwrightを使用してeBayのデータをスクレイピングするクラス
    """
    
    def __init__(self, config_manager):
        """
        スクレイパーの初期化
        
        Args:
            config_manager: 設定マネージャーのインスタンス
        """
        self.config = config_manager
        self.base_url = self.config.get('ebay', 'base_url', 'https://www.ebay.com')
        self.country = self.config.get('ebay', 'country', 'US')
        self.headless = self.config.get('scraping', 'headless', True)
        self.user_agent = self.config.get('scraping', 'user_agent')
        self.timeout = self.config.get('ebay', 'search', 'timeout', 30) * 1000  # ミリ秒単位
        self.request_delay = self.config.get('ebay', 'search', 'request_delay', 2)
        self.max_pages = self.config.get('ebay', 'search', 'max_pages', 2)
        self.items_per_page = self.config.get('ebay', 'search', 'items_per_page', 50)
        self.proxy_enabled = self.config.get('scraping', 'proxy', 'enabled', False)
        self.proxy_url = self.config.get('scraping', 'proxy', 'url', '')
        
        # ログイン情報
        self.username = self.config.get_from_env(self.config.get('ebay', 'login', 'username_env'))
        self.password = self.config.get_from_env(self.config.get('ebay', 'login', 'password_env'))
        
        # ログイン状態を管理
        self.is_logged_in = False
        
        # Playwrightインスタンス
        self.playwright = None
        self.browser = None
        self.context = None
        
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
                "headless": self.headless
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
                "viewport": {"width": 1280, "height": 800}
            }
            
            # ユーザーエージェント設定
            if self.user_agent:
                context_options["user_agent"] = self.user_agent
                
            # コンテキスト作成
            self.context = self.browser.new_context(**context_options)
            
            # タイムアウト設定
            self.context.set_default_timeout(self.timeout)
            
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
        eBayで指定したキーワードで検索を実行し、結果を取得する
        
        Args:
            keyword (str): 検索キーワード
            category (str, optional): カテゴリID
            condition (str, optional): 商品の状態（new, used等）
            listing_type (str, optional): リスティングタイプ（auction, fixed等）
            min_price (float, optional): 最低価格
            max_price (float, optional): 最高価格
            
        Returns:
            list: 検索結果のリスト
        """
        if not self.start_browser():
            return []
            
        try:
            logger.info(f"キーワード '{keyword}' で検索を開始します")
            
            # 新しいページを開く
            page = self.context.new_page()
            
            # 検索URLの構築
            search_url = f"{self.base_url}/sch/i.html?_nkw={keyword.replace(' ', '+')}"
            
            # フィルターの追加
            if category:
                search_url += f"&_sacat={category}"
            
            if min_price and max_price:
                search_url += f"&_udlo={min_price}&_udhi={max_price}"
            elif min_price:
                search_url += f"&_udlo={min_price}"
            elif max_price:
                search_url += f"&_udhi={max_price}"
                
            if listing_type:
                if listing_type.lower() == 'auction':
                    search_url += "&LH_Auction=1"
                elif listing_type.lower() == 'fixed':
                    search_url += "&LH_BIN=1"
                    
            if condition:
                if condition.lower() == 'new':
                    search_url += "&LH_ItemCondition=1000"
                elif condition.lower() == 'used':
                    search_url += "&LH_ItemCondition=3000"
            
            # ページサイズの設定
            search_url += f"&_ipg={self.items_per_page}"
            
            # 検索ページに移動
            page.goto(search_url)
            
            # ページが完全に読み込まれるまで待機
            page.wait_for_load_state('networkidle')
            
            all_results = []
            current_page = 1
            
            while current_page <= self.max_pages:
                logger.info(f"ページ {current_page}/{self.max_pages} を処理中")
                
                # 検索結果が読み込まれるまで待機
                page.wait_for_selector('.srp-results', state="visible")
                
                # ページ内の商品データを抽出
                results = self._extract_items_data(page)
                all_results.extend(results)
                
                if current_page < self.max_pages:
                    # 次のページに移動
                    next_button = page.query_selector('.pagination__next')
                    if not next_button or not next_button.is_enabled():
                        logger.info("次のページがありません。検索を終了します。")
                        break
                        
                    next_button.click()
                    
                    # ページ遷移の待機
                    page.wait_for_load_state('networkidle')
                    
                    # リクエスト間の遅延（ブロックを避けるため）
                    delay = self.request_delay + random.uniform(0, 1)
                    time.sleep(delay)
                    
                current_page += 1
            
            page.close()
            logger.info(f"検索完了: {len(all_results)}件の結果を取得しました")
            return all_results
            
        except Exception as e:
            logger.error(f"検索中にエラーが発生しました: {e}")
            # エラー発生時にスクリーンショットを保存（デバッグ用）
            self._save_debug_screenshot(page, keyword)
            page.close()
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
                    # 価格から数値を抽出
                    price_match = re.search(r'\$(\d+\.?\d*)', price_text)
                    if price_match:
                        item_data['price'] = float(price_match.group(1))
                        item_data['currency'] = 'USD'  # デフォルトはUSD
                        
                # 送料
                shipping_elem = item.query_selector('.s-item__shipping')
                if shipping_elem:
                    shipping_text = shipping_elem.inner_text().strip()
                    if 'Free' in shipping_text or '無料' in shipping_text:
                        item_data['shipping_price'] = 0.0
                    else:
                        # 送料から数値を抽出
                        shipping_match = re.search(r'\$(\d+\.?\d*)', shipping_text)
                        if shipping_match:
                            item_data['shipping_price'] = float(shipping_match.group(1))
                        
                # 出品者情報
                seller_elem = item.query_selector('.s-item__seller-info')
                if seller_elem:
                    seller_text = seller_elem.inner_text().strip()
                    # 出品者名を抽出
                    seller_name_match = re.search(r'Seller: ([^\(]+)', seller_text)
                    if seller_name_match:
                        item_data['seller_name'] = seller_name_match.group(1).strip()
                    
                    # 評価数を抽出
                    feedback_match = re.search(r'\((\d+)\)', seller_text)
                    if feedback_match:
                        item_data['seller_feedback_count'] = int(feedback_match.group(1))
                        
                # 出品者の評価
                rating_elem = item.query_selector('.x-seller-rating')
                if rating_elem:
                    rating_text = rating_elem.inner_text().strip()
                    rating_match = re.search(r'(\d+\.?\d*)%', rating_text)
                    if rating_match:
                        item_data['seller_rating'] = float(rating_match.group(1)) / 100.0  # パーセントから小数に変換
                        
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
                img_elem = item.query_selector('.s-item__image-img')
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
