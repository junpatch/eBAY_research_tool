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
            "ebay": {
                "base_url": "https://www.ebay.com",
                "search": {
                    "timeout": 30,
                    "request_delay": 2,
                    "max_pages": 2,
                    "items_per_page": 50
                },
                "login": {
                    "username_env": "EBAY_USERNAME",
                    "password_env": "EBAY_PASSWORD"
                }
            },
            "scraping": {
                "user_agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
                "headless": True,
                "proxy": {
                    "enabled": False,
                    "url": None
                }
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
        if isinstance(value, dict) and key in config_data[section] and isinstance(config_data[section][key], dict):
            # ネストした辞書の場合は既存の辞書を更新
            config_data[section][key].update(value)
        else:
            # 単一の値または新規辞書の場合は置き換え
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

    @patch('services.ebay_scraper.EbayScraper._make_request')
    def test_scraper_config_change(self, mock_make_request):
        """スクレイパー設定変更のテスト"""
        # 環境変数で設定ファイルのパスと必要な環境変数を指定
        env_vars = {
            "CONFIG_PATH": str(self.config_path),
            "EBAY_USERNAME": "test_user",
            "EBAY_PASSWORD": "test_password"
        }
        
        # _make_requestメソッドのモック設定
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.text = "<html><body>テスト結果</body></html>"
        mock_make_request.return_value = mock_response
        
        # 最初の設定でConfigManagerとEbayScraperを初期化
        with temp_env_vars(env_vars):
            # 明示的に設定パスを指定してConfigManagerを初期化
            config = ConfigManager(str(self.config_path))
            
            with EbayScraper(config) as scraper:
                # 初期設定値の確認（スクレイパーオブジェクトの属性値を直接確認）
                print(f"初期設定: timeout={scraper.timeout/1000}, request_delay={scraper.request_delay}, max_pages={scraper.max_pages}, items_per_page={scraper.items_per_page}")
                
                # この時点での属性値をアサート
                assert scraper.timeout == 30 * 1000  # ミリ秒単位で保存されているため
                assert scraper.request_delay == 2
                assert scraper.max_pages == 2
                assert scraper.items_per_page == 50
        
        # スクレイパー設定を更新
        self._update_config("ebay", "search", {
            "timeout": 20,
            "request_delay": 1.0,
            "max_pages": 3,
            "items_per_page": 100
        })
        
        # 新しい設定でConfigManagerとEbayScraperを初期化
        with temp_env_vars(env_vars):
            # 明示的に設定パスを指定してConfigManagerを初期化
            config = ConfigManager(str(self.config_path))
            
            with EbayScraper(config) as scraper:
                # 更新後の設定値を確認（スクレイパーオブジェクトの属性値を直接確認）
                print(f"更新後: timeout={scraper.timeout/1000}, request_delay={scraper.request_delay}, max_pages={scraper.max_pages}, items_per_page={scraper.items_per_page}")
                
                # 更新後の属性値をアサート
                assert scraper.timeout == 20 * 1000  # ミリ秒単位で保存されているため
                assert scraper.request_delay == 1.0
                assert scraper.max_pages == 3
                assert scraper.items_per_page == 100

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
            assert config.get_from_env(config.get(['ebay', 'base_url'])) == "https://www.ebay.co.jp"
            assert config.get_from_env(config.get(['database', 'url'])) == "sqlite:///env_override.db"
            assert config.get_from_env(config.get(['export', 'default_format'])) == "json" 