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
        if hasattr(self, 'db_manager'):
            self.db_manager.close()
        if hasattr(self, 'temp_dir'):
            self.temp_dir.cleanup()

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
            with pytest.raises(OperationalError):
                db_manager = DatabaseManager("sqlite:///non_existent.db")
            
            # ログファイルの内容を検証
            assert self.log_file.exists()
            with open(self.log_file, 'r', encoding='utf-8') as f:
                log_content = f.read()
                assert "connection error" in log_content
                assert "ERROR" in log_content

    @patch('services.ebay_scraper.requests.Session.get')
    def test_scraping_error(self, mock_get):
        """スクレイピングエラー時の挙動テスト"""
        # requestsのgetメソッドで例外を発生させる
        mock_response = MagicMock()
        mock_response.status_code = 503
        mock_response.raise_for_status.side_effect = Exception("Service Unavailable")
        mock_get.return_value = mock_response
        
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
            with EbayScraper(self.config) as scraper:
                try:
                    result = scraper.search_keyword("テストキーワード")
                except Exception as e:
                    # エラーを捕捉して検索ジョブを更新
                    self.db_manager.update_search_job_status(
                        job_id,
                        processed=1,
                        failed=1,
                        status='failed',
                        error=str(e)
                    )
            
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

    @patch('services.ebay_scraper.requests.Session.get')
    def test_error_recovery(self, mock_get):
        """エラー回復処理のテスト"""
        # 最初の呼び出しでは例外を発生、2回目は成功するように設定
        mock_error_response = MagicMock()
        mock_error_response.status_code = 500
        mock_error_response.raise_for_status.side_effect = Exception("Internal Server Error")
        
        mock_success_response = MagicMock()
        mock_success_response.status_code = 200
        mock_success_response.raise_for_status.return_value = None
        mock_success_response.text = "<html><body>テスト結果</body></html>"
        
        # 2回の呼び出しで異なる応答を返すように設定
        mock_get.side_effect = [mock_error_response, mock_success_response]
        
        # 環境変数を設定してロガーを初期化
        with temp_env_vars(self.env_vars):
            logger_manager = LoggerManager()
            logger = logger_manager.get_logger()
            
            # キーワードを追加
            keyword_id = self.db_manager.add_keyword("リトライテスト", "テストカテゴリ")
            
            # 検索ジョブを開始
            job_id = self.db_manager.start_search_job(1)
            
            # EbayScraperのsearch_keywordメソッドをパッチしてリトライ処理をテスト
            with patch.object(EbayScraper, 'search_keyword', side_effect=[
                Exception("最初のエラー"),
                [{"item_id": "123", "title": "リカバリーテスト商品"}]
            ]):
                with EbayScraper(self.config) as scraper:
                    try:
                        # 1回目の呼び出し（エラー）
                        scraper.search_keyword("リトライテスト")
                    except Exception as e:
                        # エラーを記録
                        self.db_manager.update_search_job_status(
                            job_id,
                            processed=0,
                            failed=1,
                            status='in_progress',
                            error=str(e)
                        )
                        logger.error(f"検索エラー: {e}")
                    
                    # エラー後のリカバリー処理（2回目の呼び出し）
                    try:
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
                    except Exception as e:
                        logger.error(f"リカバリー試行中にもエラー: {e}")
            
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
                assert "最初のエラー" in log_content
                assert "completed" in log_content 