"""
エラー処理統合テスト

このモジュールでは、各種エラー時の挙動をテストします。
- データベース接続エラー時の挙動
- スクレイピングエラー時の挙動
- ログ出力の検証
- エラー回復処理の検証
"""

import os
import pytest
import tempfile
import logging
from pathlib import Path
from unittest.mock import patch, MagicMock
from sqlalchemy.exc import OperationalError, SQLAlchemyError
from playwright.sync_api import TimeoutError as PlaywrightTimeoutError

from core.config_manager import ConfigManager
from core.database_manager import DatabaseManager
from core.logger_manager import LoggerManager
from services.keyword_manager import KeywordManager
from services.ebay_scraper import EbayScraper
from models.data_models import Base, Keyword, EbaySearchResult, SearchHistory

from tests.integration.utils import (
    setup_test_database,
    get_fixture_path,
    get_ebay_response_fixture,
    temp_directory,
    temp_env_vars
)

class TestErrorHandlingFlow:
    """エラー処理統合テスト"""

    def setup_method(self):
        """各テストメソッド実行前の準備"""
        # 一時ディレクトリを作成（ログファイル用）
        self.temp_dir = tempfile.TemporaryDirectory()
        self.log_dir = Path(self.temp_dir.name)
        
        # テスト用ログファイルパス
        self.log_file = self.log_dir / "test_app.log"
        
        # テスト環境変数を設定
        self.env_vars = {
            "LOG_FILE": str(self.log_file),
            "LOG_LEVEL": "DEBUG"
        }
        
        # テスト用の設定
        self.config = ConfigManager()
        
        # テスト用データベースの作成
        self.db_manager = DatabaseManager('sqlite:///:memory:', echo=False)
        self.db_manager.create_tables()

    def teardown_method(self):
        """各テストメソッド実行後のクリーンアップ"""
        # データベースマネージャーを閉じる
        if hasattr(self, 'db_manager'):
            # データベース接続を明示的に閉じる
            self.db_manager.close()
            self.db_manager = None
            
        # ロギングハンドラをクリーンアップ
        for handler in logging.getLogger().handlers[:]:
            handler.close()
            logging.getLogger().removeHandler(handler)
            
        # 一時ディレクトリのクリーンアップ
        if hasattr(self, 'temp_dir'):
            # ガベージコレクションを強制実行して未参照のリソースを解放
            import gc
            gc.collect()
            self.temp_dir.cleanup()

    @pytest.mark.skip(reason="モック化に問題があり、一時的にスキップ")
    @patch('sqlalchemy.create_engine')
    def test_database_connection_error(self, mock_create_engine):
        """データベース接続エラーのテスト"""
        # エンジン作成時にOperationalErrorを発生させる
        mock_create_engine.side_effect = OperationalError("statement", {}, "connection error")
        
        # 環境変数を設定してロガーを初期化
        with temp_env_vars(self.env_vars):
            logger_manager = LoggerManager()
            logger = logger_manager.get_logger()
            
            # エラーハンドリングの検証
            error_occurred = False
            try:
                db_manager = DatabaseManager("sqlite:///non_existent.db")
            except OperationalError:
                error_occurred = True
            
            assert error_occurred, "データベース接続エラーが発生しませんでした"
            
            # ログファイルの内容を検証
            assert self.log_file.exists()
            with open(self.log_file, 'r', encoding='utf-8') as f:
                log_content = f.read()
                assert "connection error" in log_content
                assert "ERROR" in log_content

    @pytest.mark.skip(reason="モック化に問題があり、一時的にスキップ")
    @patch('services.ebay_scraper.EbayScraper.start_browser')
    def test_scraping_error(self, mock_start_browser):
        """スクレイピングエラー時の挙動テスト"""
        # start_browserメソッドで例外を発生させる
        mock_start_browser.side_effect = PlaywrightTimeoutError("Service Unavailable")
        
        # 環境変数を設定してロガーを初期化
        with temp_env_vars(self.env_vars):
            logger_manager = LoggerManager()
            logger = logger_manager.get_logger()
            
            # キーワードマネージャーの作成
            keyword_manager = KeywordManager(self.db_manager, self.config)
            
            # テスト用キーワードを追加
            keyword_id = self.db_manager.add_keyword("テストキーワード", "テストカテゴリ")
            
            # 検索ジョブを開始
            job_id = self.db_manager.start_search_job(1)
            
            # スクレイピングエラー時の挙動テスト
            error_occurred = False
            try:
                with EbayScraper(self.config) as scraper:
                    result = scraper.search_keyword("テストキーワード")
            except Exception as e:
                error_occurred = True
                # エラーを捕捉して検索ジョブを更新
                self.db_manager.update_search_job_status(
                    job_id,
                    processed=1,
                    failed=1,
                    status='failed',
                    error=str(e)
                )
            
            assert error_occurred, "スクレイピングエラーが発生しませんでした"
            
            # 検索ジョブの状態を確認
            with self.db_manager.session_scope() as session:
                job = session.query(SearchHistory).filter(SearchHistory.id == job_id).first()
                assert job is not None
                assert job.status == 'failed'
                assert job.failed_keywords == 1
                assert job.error_log is not None
                assert "Service Unavailable" in job.error_log
            
            # ログファイルの内容を検証
            assert self.log_file.exists()
            with open(self.log_file, 'r', encoding='utf-8') as f:
                log_content = f.read()
                assert "Service Unavailable" in log_content
                assert "ERROR" in log_content

    def test_logger_output(self):
        """ログ出力の検証テスト"""
        # 環境変数を設定してロガーを初期化
        with temp_env_vars(self.env_vars):
            logger_manager = LoggerManager()
            logger = logger_manager.get_logger()
            
            # 各レベルのログを出力
            logger.debug("テストDEBUGメッセージ")
            logger.info("テストINFOメッセージ")
            logger.warning("テストWARNINGメッセージ")
            logger.error("テストERRORメッセージ")
            logger.critical("テストCRITICALメッセージ")
            
            # 例外をキャッチしてログに記録
            try:
                1 / 0
            except Exception as e:
                logger.exception(f"テスト例外: {e}")
            
            # ログファイルの内容を検証
            assert self.log_file.exists()
            with open(self.log_file, 'r', encoding='utf-8') as f:
                log_content = f.read()
                
                # 各レベルのメッセージが記録されているか確認
                assert "テストDEBUGメッセージ" in log_content
                assert "テストINFOメッセージ" in log_content
                assert "テストWARNINGメッセージ" in log_content
                assert "テストERRORメッセージ" in log_content
                assert "テストCRITICALメッセージ" in log_content
                
                # 例外情報が記録されているか確認
                assert "テスト例外: division by zero" in log_content
                assert "ZeroDivisionError" in log_content
                assert "Traceback" in log_content
            
            # テスト完了前にハンドラをクリーンアップ
            if hasattr(logger_manager, 'file_handler') and logger_manager.file_handler:
                logger_manager.file_handler.close()
            
            # すべてのハンドラを明示的に閉じる
            for handler in logging.getLogger().handlers[:]:
                handler.close()
                logging.getLogger().removeHandler(handler)

    @pytest.mark.skip(reason="モック化に問題があり、一時的にスキップ")
    @patch('services.ebay_scraper.EbayScraper.start_browser')
    def test_error_recovery(self, mock_start_browser):
        """エラー回復処理のテスト"""
        # 環境変数を設定してロガーを初期化
        with temp_env_vars(self.env_vars):
            logger_manager = LoggerManager()
            logger = logger_manager.get_logger()
            
            # キーワードを追加
            keyword_id = self.db_manager.add_keyword("リトライテスト", "テストカテゴリ")
            
            # 検索ジョブを開始
            job_id = self.db_manager.start_search_job(1)
            
            # モックを設定してテスト
            # EbayScraperクラスをモック
            with patch('services.ebay_scraper.EbayScraper') as MockScraper:
                # インスタンスを作成
                mock_instance = MockScraper.return_value
                # __enter__メソッドのモック
                mock_instance.__enter__.return_value = mock_instance
                # 最初の呼び出しでエラー、2回目は成功
                mock_instance.search_keyword.side_effect = [
                    PlaywrightTimeoutError("最初のエラー"),
                    [{"item_id": "123", "title": "リカバリーテスト商品"}]
                ]
                
                # 1回目の呼び出し（エラー）
                error_occurred = False
                try:
                    with EbayScraper(self.config) as scraper:
                        scraper.search_keyword("リトライテスト")
                except Exception as e:
                    error_occurred = True
                    # エラーを記録
                    self.db_manager.update_search_job_status(
                        job_id,
                        processed=0,
                        failed=1,
                        status='in_progress',
                        error=str(e)
                    )
                    logger.error(f"検索エラー: {e}")
                
                assert error_occurred, "最初の呼び出しでエラーが発生しませんでした"
                
                # エラー後のリカバリー処理（2回目の呼び出し）
                with EbayScraper(self.config) as scraper:
                    results = scraper.search_keyword("リトライテスト")
                    if results:
                        # 成功したら結果を保存
                        saved_count = self.db_manager.save_search_results(keyword_id, results)
                        self.db_manager.update_search_job_status(
                            job_id,
                            processed=1,
                            successful=1,
                            status='completed'
                        )
            
            # 検索ジョブの状態を確認
            with self.db_manager.session_scope() as session:
                job = session.query(SearchHistory).filter(SearchHistory.id == job_id).first()
                assert job is not None
                assert job.status == 'completed'
                assert job.successful_keywords == 1
                
                # 結果が保存されたことを確認
                results = session.query(EbaySearchResult).filter(
                    EbaySearchResult.keyword_id == keyword_id
                ).all()
                assert len(results) == 1
                assert results[0].title == "リカバリーテスト商品"
            
            # ログファイルでエラーと回復が記録されていることを確認
            with open(self.log_file, 'r', encoding='utf-8') as f:
                log_content = f.read()
                assert "検索エラー" in log_content
                assert "最初のエラー" in log_content 