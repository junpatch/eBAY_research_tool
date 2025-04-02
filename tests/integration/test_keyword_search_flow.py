"""
キーワードインポートから検索までの統合テスト

このテストモジュールでは、キーワードのインポートから検索、結果の保存までの一連の流れをテストします。
"""

import pytest
import os
from pathlib import Path
import tempfile
import json
from unittest.mock import patch, MagicMock
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from core.config_manager import ConfigManager
from core.database_manager import DatabaseManager
from services.keyword_manager import KeywordManager
from services.ebay_scraper import EbayScraper
from models.data_models import Base, Keyword, EbaySearchResult, SearchHistory

from tests.integration.utils import (
    setup_test_database,
    get_fixture_path,
    get_ebay_response_fixture
)

class TestKeywordSearchFlow:
    """キーワードインポートから検索までの統合テスト"""

    def setup_method(self):
        """各テストメソッド実行前の準備"""
        # テスト用の設定
        self.config = ConfigManager()
        
        # テスト用データベースの作成
        self.db_engine = create_engine('sqlite:///:memory:', echo=False)
        self.Session = sessionmaker(bind=self.db_engine)
        
        # テーブルの作成
        Base.metadata.create_all(self.db_engine)
        
        # テスト用マネージャーの作成
        self.db_manager = DatabaseManager('sqlite:///:memory:', echo=False)
        self.db_manager.create_tables()
        
        # キーワードマネージャーの作成
        self.keyword_manager = KeywordManager(self.db_manager, self.config)
        
        # テスト用のCSVファイルパス
        self.test_csv_path = get_fixture_path('test_keywords.csv')

    def teardown_method(self):
        """各テストメソッド実行後のクリーンアップ"""
        if hasattr(self, 'db_manager'):
            self.db_manager.close()
        if hasattr(self, 'db_engine'):
            self.db_engine.dispose()

    def test_single_keyword_import_and_search(self):
        """単一キーワードのインポートと検索テスト"""
        # キーワードの登録
        keyword_id = self.db_manager.add_keyword("テスト用キーワード", "テストカテゴリ")
        assert keyword_id is not None
        
        # キーワードが正しく保存されたか確認
        with self.db_manager.session_scope() as session:
            keyword = session.query(Keyword).filter(Keyword.id == keyword_id).first()
            assert keyword is not None
            assert keyword.keyword == "テスト用キーワード"
            assert keyword.category == "テストカテゴリ"
            assert keyword.status == "active"
        
        # 検索結果のモックデータ
        mock_search_results = get_ebay_response_fixture('search_result_sample.json')
        
        # EbayScraperのsearch_keywordメソッドをモック化
        with patch('services.ebay_scraper.EbayScraper.search_keyword') as mock_search:
            # モックが検索結果を返すように設定
            mock_search.return_value = mock_search_results
            
            # EbayScraperを使用して検索を実行
            with EbayScraper(self.config) as scraper:
                results = scraper.search_keyword("テスト用キーワード")
                
                # 検索結果が正しく返されたか確認
                assert len(results) == 3
                assert results[0]['item_id'] == "123456789012"
                
                # 検索結果をDBに保存
                saved_count = self.db_manager.save_search_results(keyword_id, results)
                assert saved_count == 3
        
        # 検索結果が正しく保存されたか確認
        with self.db_manager.session_scope() as session:
            saved_results = session.query(EbaySearchResult).filter(
                EbaySearchResult.keyword_id == keyword_id
            ).all()
            assert len(saved_results) == 3
            assert saved_results[0].item_id == "123456789012"
            assert saved_results[0].title == "テスト商品 1"
            assert saved_results[0].price == 1999.99

    def test_batch_keywords_import_and_search(self):
        """複数キーワードのバッチインポートと検索テスト"""
        # CSVファイルからキーワードをインポート
        added_count = self.keyword_manager.import_from_csv(
            self.test_csv_path, 
            keyword_column='keyword', 
            category_column='category',
            has_header=True
        )
        
        # 正しい数のキーワードがインポートされたか確認
        assert added_count == 3
        
        # キーワードが正しく保存されたか確認
        keywords = self.db_manager.get_keywords()
        assert len(keywords) == 3
        assert keywords[0].keyword == "テスト用キーワード1"
        assert keywords[0].category == "テストカテゴリ1"
        
        # 検索結果のモックデータ
        mock_search_results = get_ebay_response_fixture('search_result_sample.json')
        
        # EbayScraperのsearch_keywordメソッドをモック化
        with patch('services.ebay_scraper.EbayScraper.search_keyword') as mock_search:
            # モックが検索結果を返すように設定
            mock_search.return_value = mock_search_results
            
            # 検索ジョブの開始
            job_id = self.db_manager.start_search_job(len(keywords))
            assert job_id is not None
            
            # すべてのキーワードで検索を実行し結果を保存
            with EbayScraper(self.config) as scraper:
                for i, keyword in enumerate(keywords):
                    results = scraper.search_keyword(keyword.keyword)
                    saved_count = self.db_manager.save_search_results(keyword.id, results)
                    assert saved_count == 3
                    
                    # 検索履歴を更新
                    self.db_manager.update_search_job_status(
                        job_id, 
                        processed=i+1,
                        successful=i+1,
                        status='in_progress'
                    )
                
                # 検索ジョブを完了状態に更新
                self.db_manager.update_search_job_status(job_id, status='completed')
        
        # 検索履歴が正しく記録されたか確認
        with self.db_manager.session_scope() as session:
            job = session.query(SearchHistory).filter(SearchHistory.id == job_id).first()
            assert job is not None
            assert job.total_keywords == 3
            assert job.processed_keywords == 3
            assert job.successful_keywords == 3
            assert job.status == 'completed'
            
        # 検索結果が正しく保存されたか確認
        with self.db_manager.session_scope() as session:
            for keyword in keywords:
                saved_results = session.query(EbaySearchResult).filter(
                    EbaySearchResult.keyword_id == keyword.id
                ).all()
                assert len(saved_results) == 3

    def test_categorized_keywords_import_and_search(self):
        """カテゴリ付きキーワードのインポートと検索テスト"""
        # カテゴリ付きのキーワードリストを作成
        keywords_with_categories = [
            ("カテゴリテスト1", "電子機器"),
            ("カテゴリテスト2", "家具"),
            ("カテゴリテスト3", "衣類")
        ]
        
        # バルクインポート
        added_count = self.db_manager.add_keywords_bulk(keywords_with_categories)
        assert added_count == 3
        
        # カテゴリごとにキーワードを取得して確認
        with self.db_manager.session_scope() as session:
            electronics_keywords = session.query(Keyword).filter(Keyword.category == "電子機器").all()
            assert len(electronics_keywords) == 1
            assert electronics_keywords[0].keyword == "カテゴリテスト1"
            
            furniture_keywords = session.query(Keyword).filter(Keyword.category == "家具").all()
            assert len(furniture_keywords) == 1
            assert furniture_keywords[0].keyword == "カテゴリテスト2"
            
            clothing_keywords = session.query(Keyword).filter(Keyword.category == "衣類").all()
            assert len(clothing_keywords) == 1
            assert clothing_keywords[0].keyword == "カテゴリテスト3"
        
        # 検索結果のモックデータ
        mock_search_results = get_ebay_response_fixture('search_result_sample.json')
        
        # EbayScraperのsearch_keywordメソッドをモック化
        with patch('services.ebay_scraper.EbayScraper.search_keyword') as mock_search:
            # モックが検索結果を返すように設定
            mock_search.return_value = mock_search_results
            
            # 各カテゴリのキーワードで検索を実行
            with EbayScraper(self.config) as scraper:
                keywords = self.db_manager.get_keywords()
                for keyword in keywords:
                    results = scraper.search_keyword(keyword.keyword)
                    saved_count = self.db_manager.save_search_results(keyword.id, results)
                    assert saved_count == 3
        
        # カテゴリごとの検索結果を確認
        with self.db_manager.session_scope() as session:
            for category in ["電子機器", "家具", "衣類"]:
                # カテゴリに対応するキーワードを取得
                keyword = session.query(Keyword).filter(Keyword.category == category).first()
                
                # そのキーワードに紐づく検索結果を確認
                results = session.query(EbaySearchResult).filter(
                    EbaySearchResult.keyword_id == keyword.id
                ).all()
                assert len(results) == 3
                
                # 検索結果の内容を確認
                item_ids = sorted([r.item_id for r in results])
                assert item_ids == ["123456789012", "234567890123", "345678901234"] 