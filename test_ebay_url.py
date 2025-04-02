#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
eBay URLテスト - 日本語キーワードのURLエンコードテスト

このスクリプトはeBayの検索URLに直接アクセスして、応答コードを確認します。
"""

import urllib.parse
import time
import random
from playwright.sync_api import sync_playwright
from services.ebay_scraper import USER_AGENTS, COMMON_HEADERS

def test_ebay_url(keyword, delay=5):
    """
    eBayの検索URLに直接アクセスして応答を確認
    
    Args:
        keyword: 検索キーワード
        delay: リクエスト後の遅延（秒）
    """
    # キーワードをURLエンコード
    encoded_keyword = urllib.parse.quote(keyword)
    
    # 検索URLの構築
    search_url = f"https://www.ebay.com/sch/i.html?_nkw={encoded_keyword}"
    
    # ヘッダー設定
    headers = COMMON_HEADERS.copy()
    headers['User-Agent'] = random.choice(USER_AGENTS)
    
    # 何回も試す
    for i in range(3):
        try:
            print(f"試行 {i+1}: キーワード '{keyword}' でリクエスト中...")
            print(f"使用URL: {search_url}")
            print(f"使用UA: {headers['User-Agent']}")
            
            with sync_playwright() as p:
                browser = p.chromium.launch(headless=True)
                context = browser.new_context(
                    user_agent=headers['User-Agent'],
                    extra_http_headers=headers
                )
                page = context.new_page()
                
                # リクエスト実行
                response = page.goto(search_url)
                
                # 結果表示
                print(f"ステータスコード: {response.status}")
                print(f"レスポンスサイズ: {len(page.content())}")
                
                # ステータスコードに応じたメッセージ
                if response.status == 200:
                    print("成功: ページが正常に読み込まれました")
                    content = page.content().lower()
                    if "robot" in content or "captcha" in content:
                        print("警告: ページにロボット検出またはCAPTCHAが含まれています")
                    browser.close()
                    return True
                elif response.status == 503:
                    print("エラー: サービス利用不可 (503)")
                else:
                    print(f"エラー: 予期せぬステータスコード {response.status}")
                
                browser.close()
                
            # 遅延
            print(f"{delay}秒待機中...")
            time.sleep(delay)
            delay += 2  # 遅延を増やす
            
            # 次のリクエストでは異なるUAを使用
            headers['User-Agent'] = random.choice(USER_AGENTS)
            
        except Exception as e:
            print(f"エラー発生: {e}")
            time.sleep(delay)
    
    return False

def main():
    """
    日本語キーワードと英語キーワードの両方をテスト
    """
    # 英語キーワード
    print("==== 英語キーワードテスト ====")
    test_ebay_url("laptop")
    
    # 遅延
    print("\n5秒待機中...\n")
    time.sleep(5)
    
    # 日本語キーワード
    print("==== 日本語キーワードテスト ====")
    test_ebay_url("パソコン")

if __name__ == "__main__":
    main() 