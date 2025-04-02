"""
設定変更時の動作テスト

このモジュールでは、設定変更が各コンポーネントに正しく反映されることをテストします。
- データベース設定変更のテスト
- スクレイパー設定変更のテスト
- エクスポート設定変更のテスト
"""

import os
import pytest
import tempfile
import yaml
from pathlib import Path
from unittest.mock import patch, MagicMock

from core.config_manager import ConfigManager
from core.database_manager import DatabaseManager
from services.ebay_scraper import EbayScraper
from services.data_exporter import DataExporter

from tests.integration.utils import (
    temp_directory,
    temp_env_vars
)

class TestConfigChangeFlow:
    """設定変更時の動作テスト"""

    def setup_method(self):
        """各テストメソッド実行前の準備"""
        # 一時ディレクトリを作成（設定ファイル用）
        self.temp_dir = tempfile.TemporaryDirectory()
        self.config_dir = Path(self.temp_dir.name)
        
        # テスト用の設定ファイルを作成
        self.config_path = self.config_dir / "test_config.yaml"
        self._create_test_config()

    def teardown_method(self):
        """各テストメソッド実行後のクリーンアップ"""
        if hasattr(self, 'temp_dir'):
            self.temp_dir.cleanup()

    def _create_test_config(self):
        """テスト用の設定ファイルを作成"""
        config_data = {
            "database": {
                "url": "sqlite:///:memory:",
                "echo": False
            },
            "ebay_scraper": {
                "base_url": "https://www.ebay.com",
                "user_agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
                "timeout": 10,
                "retry_count": 3,
                "delay_between_requests": 1.0
            },
            "export": {
                "default_format": "csv",
                "default_path": str(self.config_dir / "exports"),
                "excel_template": None
            },
            "logging": {
                "level": "INFO",
                "file": str(self.config_dir / "app.log")
            }
        }
        
        # YAMLファイルとして保存
        with open(self.config_path, 'w', encoding='utf-8') as f:
            yaml.dump(config_data, f)

    def _update_config(self, section, key, value):
        """設定ファイルの特定のセクションと項目を更新"""
        # 現在の設定を読み込み
        with open(self.config_path, 'r', encoding='utf-8') as f:
            config_data = yaml.safe_load(f)
        
        # 指定されたセクションと項目を更新
        config_data[section][key] = value
        
        # 変更を保存
        with open(self.config_path, 'w', encoding='utf-8') as f:
            yaml.dump(config_data, f)

    def test_database_config_change(self):
        """データベース設定変更のテスト"""
        # 環境変数で設定ファイルのパスを指定
        env_vars = {"CONFIG_PATH": str(self.config_path)}
        
        # 最初の設定でConfigManagerとDatabaseManagerを初期化
        with temp_env_vars(env_vars):
            config = ConfigManager()
            db_manager = DatabaseManager(config.get_db_url())
            
            # 初期設定値の確認
            assert config.get(['database', 'url']) == "sqlite:///:memory:"
            assert db_manager.engine.url.render_as_string() == "sqlite:///:memory:"
        
        # データベース設定を更新
        self._update_config("database", "url", "sqlite:///test_new.db")
        
        # 新しい設定でConfigManagerとDatabaseManagerを初期化
        with temp_env_vars(env_vars):
            config = ConfigManager()
            db_manager = DatabaseManager(config.get_db_url())
            
            # 変更された設定値の確認
            assert config.get(['database', 'url']) == "sqlite:///test_new.db"
            assert db_manager.engine.url.render_as_string() == "sqlite:///test_new.db"

    @patch('requests.Session')
    def test_scraper_config_change(self, mock_session):
        """スクレイパー設定変更のテスト"""
        # 環境変数で設定ファイルのパスを指定
        env_vars = {"CONFIG_PATH": str(self.config_path)}
        
        # セッションのモック設定
        mock_session_instance = MagicMock()
        mock_session.return_value = mock_session_instance
        
        # 最初の設定でConfigManagerとEbayScraperを初期化
        with temp_env_vars(env_vars):
            config = ConfigManager()
            
            with EbayScraper(config) as scraper:
                # 初期設定値の確認
                assert config.get(['ebay_scraper', 'timeout']) == 10
                assert config.get(['ebay_scraper', 'retry_count']) == 3
                assert config.get(['ebay_scraper', 'delay_between_requests']) == 1.0
        
        # スクレイパー設定を更新
        self._update_config("ebay_scraper", "timeout", 20)
        self._update_config("ebay_scraper", "retry_count", 5)
        self._update_config("ebay_scraper", "delay_between_requests", 2.0)
        
        # 新しい設定でConfigManagerとEbayScraperを初期化
        with temp_env_vars(env_vars):
            config = ConfigManager()
            
            with EbayScraper(config) as scraper:
                # 変更された設定値の確認
                assert config.get(['ebay_scraper', 'timeout']) == 20
                assert config.get(['ebay_scraper', 'retry_count']) == 5
                assert config.get(['ebay_scraper', 'delay_between_requests']) == 2.0

    def test_export_config_change(self):
        """エクスポート設定変更のテスト"""
        # 環境変数で設定ファイルのパスを指定
        env_vars = {"CONFIG_PATH": str(self.config_path)}
        
        # 最初の設定でConfigManagerとDataExporterを初期化
        with temp_env_vars(env_vars):
            config = ConfigManager()
            db_manager = DatabaseManager(config.get_db_url())
            exporter = DataExporter(config, db_manager)
            
            # 初期設定値の確認
            assert config.get(['export', 'default_format']) == "csv"
            assert config.get(['export', 'default_path']) == str(self.config_dir / "exports")
        
        # エクスポート設定を更新
        self._update_config("export", "default_format", "excel")
        self._update_config("export", "default_path", str(self.config_dir / "new_exports"))
        
        # 新しい設定でConfigManagerとDataExporterを初期化
        with temp_env_vars(env_vars):
            config = ConfigManager()
            db_manager = DatabaseManager(config.get_db_url())
            exporter = DataExporter(config, db_manager)
            
            # 変更された設定値の確認
            assert config.get(['export', 'default_format']) == "excel"
            assert config.get(['export', 'default_path']) == str(self.config_dir / "new_exports")

    def test_env_var_override(self):
        """環境変数による設定上書きテスト"""
        # 環境変数で設定ファイルのパスと上書き設定を指定
        env_vars = {
            "CONFIG_PATH": str(self.config_path),
            "EBAY_BASE_URL": "https://www.ebay.co.jp",  # 日本のeBayサイト
            "DB_URL": "sqlite:///env_override.db",
            "EXPORT_FORMAT": "json"
        }
        
        # 環境変数で上書きされた設定で初期化
        with temp_env_vars(env_vars):
            config = ConfigManager()
            
            # 環境変数による上書きの確認
            assert config.get_from_env(config.get(['ebay_scraper', 'base_url'])) == "https://www.ebay.co.jp"
            assert config.get_from_env(config.get(['database', 'url'])) == "sqlite:///env_override.db"
            assert config.get_from_env(config.get(['export', 'default_format'])) == "json" 