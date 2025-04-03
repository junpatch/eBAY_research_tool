# -*- coding: utf-8 -*-

import pytest
import os
import sys
from pathlib import Path
from unittest.mock import patch, MagicMock, call
import typer
from typer.testing import CliRunner
import pandas as pd

# テスト対象のモジュールをインポート
sys.path.append(str(Path(__file__).parent.parent))
from interfaces.cli_interface import app

# テスト用のランナー
runner = CliRunner()

@pytest.fixture
def mock_config():
    """設定マネージャーのモック"""
    mock_config = MagicMock()
    # 必要な設定値を設定
    mock_config.get_db_url.return_value = 'sqlite:///:memory:'
    mock_config.get.return_value = 'test_value'
    mock_config.get_path.return_value = Path('/mock/path')
    mock_config.get_from_env.return_value = 'test_env_value'
    
    # ConfigManagerのインスタンス化をモック
    with patch('core.config_manager.ConfigManager', return_value=mock_config):
        yield mock_config

@pytest.fixture
def mock_logger():
    """ロガーのモック"""
    mock_logger = MagicMock()
    mock_logger_manager = MagicMock()
    mock_logger_manager.get_logger.return_value = mock_logger
    
    # LoggerManagerのインスタンス化をモック
    with patch('core.logger_manager.LoggerManager', return_value=mock_logger_manager):
        yield mock_logger

@pytest.fixture
def mock_db():
    """データベースマネージャーのモック"""
    mock_db = MagicMock()
    # 必要なメソッドのモック
    mock_db.create_tables.return_value = None
    mock_db.start_search_job.return_value = 1  # ジョブID
    mock_db.save_search_results.return_value = 5  # 保存された結果数
    
    # DatabaseManagerのインスタンス化をモック
    with patch('core.database_manager.DatabaseManager', return_value=mock_db):
        yield mock_db

@pytest.fixture
def mock_keyword_manager():
    """キーワードマネージャーのモック"""
    mock_km = MagicMock()
    # 必要なメソッドのモック
    mock_km.import_from_csv.return_value = 10  # インポートされたキーワード数
    mock_km.import_from_excel.return_value = 10  # インポートされたキーワード数
    mock_km.import_from_google_sheets.return_value = 10  # インポートされたキーワード数
    
    # 仮のキーワードリスト
    mock_keyword = MagicMock()
    mock_keyword.id = 1
    mock_keyword.keyword = "test keyword"
    mock_km.get_active_keywords.return_value = [mock_keyword]
    
    # KeywordManagerのインスタンス化をモック
    with patch('services.keyword_manager.KeywordManager', return_value=mock_km):
        yield mock_km

@pytest.fixture
def mock_scraper():
    """スクレイパーのモック"""
    mock_scraper = MagicMock()
    mock_scraper.login.return_value = True
    mock_scraper.search_keyword.return_value = [{"title": "Test Item", "price": 10.99}]
    
    # EbayScraperのインスタンス化とwith文のコンテキスト管理をモック
    with patch('services.ebay_scraper.EbayScraper') as scraper_mock:
        scraper_mock.return_value.__enter__.return_value = mock_scraper
        yield mock_scraper

@pytest.fixture
def mock_exporter():
    """データエクスポーターのモック"""
    mock_exp = MagicMock()
    # 戻り値を辞書形式に変更
    mock_exp.export_results.return_value = {
        "path": "/mock/path/output.csv", 
        "is_empty": False, 
        "count": 10
    }
    
    # DataExporterのインスタンス化をモック
    with patch('services.data_exporter.DataExporter', return_value=mock_exp):
        yield mock_exp

@pytest.fixture
def mock_file_exists():
    """ファイル存在確認のモック"""
    with patch('pathlib.Path.exists', return_value=True):
        yield

# importコマンドのテスト
def test_import_keywords_csv(mock_config, mock_logger, mock_db, mock_keyword_manager, mock_file_exists):
    """CSVからのインポートテスト"""
    # コマンド実行
    result = runner.invoke(app, ["import", "--format", "csv", "--file", "test.csv"])
    
    # 結果確認
    assert result.exit_code == 0
    assert "成功" in result.stdout
    mock_keyword_manager.import_from_csv.assert_called_once()

def test_import_keywords_excel(mock_config, mock_logger, mock_db, mock_keyword_manager, mock_file_exists):
    """Excelからのインポートテスト"""
    # コマンド実行
    result = runner.invoke(app, ["import", "--format", "excel", "--file", "test.xlsx"])
    
    # 結果確認
    assert result.exit_code == 0
    assert "成功" in result.stdout
    mock_keyword_manager.import_from_excel.assert_called_once()

def test_import_keywords_google_sheets(mock_config, mock_logger, mock_db, mock_keyword_manager):
    """Google Sheetsからのインポートテスト"""
    # コマンド実行
    result = runner.invoke(app, ["import", "--format", "google_sheets"])
    
    # 結果確認
    assert result.exit_code == 0
    assert "成功" in result.stdout
    mock_keyword_manager.import_from_google_sheets.assert_called_once()

def test_import_keywords_no_file(mock_config, mock_logger, mock_db, mock_keyword_manager):
    """ファイル未指定でのインポートテスト"""
    # コマンド実行
    result = runner.invoke(app, ["import", "--format", "csv"])
    
    # 結果確認
    assert result.exit_code == 1
    assert "エラー" in result.stdout
    assert "--file オプションは必須です" in result.stdout

def test_import_keywords_file_not_exists(mock_config, mock_logger, mock_db, mock_keyword_manager):
    """存在しないファイルでのインポートテスト"""
    # ファイルが存在しないケース
    with patch('pathlib.Path.exists', return_value=False):
        # コマンド実行
        result = runner.invoke(app, ["import", "--format", "csv", "--file", "notexist.csv"])
        
        # 結果確認
        assert result.exit_code == 1
        assert "エラー" in result.stdout
        assert "見つかりません" in result.stdout

def test_import_keywords_unsupported_format(mock_config, mock_logger, mock_db, mock_keyword_manager):
    """サポートされていない形式でのインポートテスト"""
    # コマンド実行
    result = runner.invoke(app, ["import", "--format", "json", "--file", "test.json"])
    
    # 結果確認
    assert result.exit_code == 1
    assert "エラー" in result.stdout
    assert "サポートされていない形式" in result.stdout

def test_import_keywords_exception(mock_config, mock_logger, mock_db, mock_keyword_manager, mock_file_exists):
    """例外発生時のテスト"""
    # 例外を発生させる
    mock_keyword_manager.import_from_csv.side_effect = Exception("テスト例外")
    
    # コマンド実行
    result = runner.invoke(app, ["import", "--format", "csv", "--file", "test.csv"])
    
    # 結果確認
    assert result.exit_code == 1
    assert "エラー" in result.stdout
    assert "問題が発生しました" in result.stdout
    # ロガーが例外を記録したことを確認
    mock_logger.error.assert_called_once()

def test_import_keywords_invalid_csv_format(mock_config, mock_logger, mock_db, mock_keyword_manager, mock_file_exists):
    """不正な形式のCSVファイルでのインポートテスト"""
    # KeywordManagerがCSVパースエラーを発生させるようにモック
    mock_keyword_manager.import_from_csv.side_effect = ValueError("Invalid CSV format")

    # コマンド実行
    result = runner.invoke(app, ["import", "--format", "csv", "--file", "invalid.csv"])

    # 結果確認
    assert result.exit_code == 1
    assert "エラー" in result.stdout
    assert "インポート中に問題が発生しました: Invalid CSV format" in result.stdout
    mock_logger.error.assert_called_once()
    args, kwargs = mock_logger.error.call_args
    assert "キーワードインポート中にエラーが発生しました" in args[0]
    assert kwargs.get('exc_info') is None

def test_import_keywords_empty_csv(mock_config, mock_logger, mock_db, mock_keyword_manager, mock_file_exists):
    """空のCSVファイルでのインポートテスト"""
    # KeywordManagerが0件返すようにモック
    mock_keyword_manager.import_from_csv.return_value = 0

    # コマンド実行
    result = runner.invoke(app, ["import", "--format", "csv", "--file", "empty.csv"])

    # 結果確認
    assert result.exit_code == 0
    assert "成功" in result.stdout
    assert "0個のキーワード" in result.stdout
    mock_keyword_manager.import_from_csv.assert_called_once()

# searchコマンドのテスト
def test_search_keywords(mock_config, mock_logger, mock_db, mock_keyword_manager, mock_scraper, mock_exporter):
    """キーワード検索テスト"""
    # コマンド実行
    result = runner.invoke(app, ["search"])
    
    # 結果確認
    assert result.exit_code == 0
    mock_keyword_manager.get_active_keywords.assert_called_once()
    mock_scraper.search_keyword.assert_called_once()
    mock_exporter.export_results.assert_called_once()
    assert "エクスポート成功" in result.stdout
    assert "10件のレコード" in result.stdout

def test_search_keywords_with_login(mock_config, mock_logger, mock_db, mock_keyword_manager, mock_scraper, mock_exporter):
    """ログイン付きキーワード検索テスト"""
    # コマンド実行
    result = runner.invoke(app, ["search", "--login"])
    
    # 結果確認
    assert result.exit_code == 0
    mock_scraper.login.assert_called_once()
    assert "ログイン成功" in result.stdout

def test_search_keywords_no_keywords(mock_config, mock_logger, mock_db, mock_keyword_manager, mock_scraper, mock_exporter):
    """キーワードがない場合のテスト"""
    # キーワードが空のケース
    mock_keyword_manager.get_active_keywords.return_value = []
    
    # コマンド実行
    result = runner.invoke(app, ["search"])
    
    # 結果確認
    assert result.exit_code == 0
    assert "警告" in result.stdout
    assert "キーワードがありません" in result.stdout

def test_search_keywords_login_failed(mock_config, mock_logger, mock_db, mock_keyword_manager, mock_scraper, mock_exporter):
    """ログイン失敗時のテスト"""
    # ログイン失敗のケース
    mock_scraper.login.return_value = False
    
    # コマンド実行
    result = runner.invoke(app, ["search", "--login"])
    
    # 結果確認
    assert result.exit_code == 0
    assert "警告" in result.stdout
    assert "ログインできませんでした" in result.stdout

def test_search_keywords_search_error(mock_config, mock_logger, mock_db, mock_keyword_manager, mock_scraper, mock_exporter):
    """検索エラー時のテスト"""
    # 検索エラーのケース
    mock_scraper.search_keyword.side_effect = Exception("検索エラー")
    
    # コマンド実行
    result = runner.invoke(app, ["search"])
    
    # 結果確認
    assert result.exit_code == 0
    assert "エラー" in result.stdout
    # エラーログが記録されたことを確認
    mock_logger.error.assert_called_once()
    # 検索ジョブのステータスが更新されたことを確認
    mock_db.update_search_job_status.assert_called()

def test_search_keywords_export_error(mock_config, mock_logger, mock_db, mock_keyword_manager, mock_scraper, mock_exporter):
    """エクスポートエラー時のテスト"""
    # エクスポートエラーのケース
    mock_exporter.export_results.side_effect = Exception("エクスポートエラー")
    
    # コマンド実行
    result = runner.invoke(app, ["search"])
    
    # 結果確認
    assert result.exit_code == 0
    assert "エラー" in result.stdout
    # エラーログが記録されたことを確認
    mock_logger.error.assert_called_once()

# statsコマンドのテスト
def test_show_statistics(mock_config, mock_db):
    """統計表示テスト"""
    # モックデータを設定
    mock_stats = {
        'total_keywords': 10,
        'searched_keywords': 8,
        'total_results': 120,
        'avg_results_per_keyword': 15.0,
        'last_search': '2023-12-15 14:30:45',
        'price_stats': {
            'min': 500.0,
            'max': 15000.0,
            'avg': 3250.5
        },
        'top_sellers': [
            {'seller_name': 'トップセラー1', 'count': 25},
            {'seller_name': 'トップセラー2', 'count': 18}
        ]
    }
    
    # get_search_statsメソッドのモック
    mock_db.get_search_stats.return_value = mock_stats
    
    # コマンド実行
    result = runner.invoke(app, ["stats"])
    
    # 結果確認
    assert result.exit_code == 0
    assert "データベース統計" in result.stdout
    assert "10" in result.stdout  # total_keywords
    assert "120" in result.stdout  # total_results
    assert "15.0" in result.stdout  # avg_results_per_keyword
    assert "トップセラー1" in result.stdout
    assert "トップセラー2" in result.stdout

# list-keywordsコマンドのテスト
def test_list_keywords_with_data(mock_config, mock_db):
    """キーワードリスト表示テスト（データあり）"""
    # キーワードのモックデータ作成
    keyword1 = MagicMock()
    keyword1.id = 1
    keyword1.keyword = "テストキーワード1"
    keyword1.category = "テストカテゴリ"
    keyword1.status = "active"
    keyword1.last_searched_at = None
    
    keyword2 = MagicMock()
    keyword2.id = 2
    keyword2.keyword = "テストキーワード2"
    keyword2.category = None
    keyword2.status = "active"
    keyword2.last_searched_at = None
    
    # get_keywordsメソッドのモック
    mock_db.get_keywords.return_value = [keyword1, keyword2]
    
    # コマンド実行
    result = runner.invoke(app, ["list-keywords"])
    
    # 結果確認
    assert result.exit_code == 0
    assert "キーワード一覧" in result.stdout
    assert "テストキーワード1" in result.stdout
    assert "テストキーワード2" in result.stdout
    assert "テストカテゴリ" in result.stdout
    assert "未検索" in result.stdout

def test_list_keywords_no_data(mock_config, mock_db):
    """キーワードリスト表示テスト（データなし）"""
    # get_keywordsメソッドのモック（空のリストを返す）
    mock_db.get_keywords.return_value = []
    
    # コマンド実行
    result = runner.invoke(app, ["list-keywords"])
    
    # 結果確認
    assert result.exit_code == 0
    assert "該当するキーワードがありません" in result.stdout

# clean-allコマンドのテスト
def test_clean_database_confirmed(mock_config, mock_db):
    """データベースクリーンアップテスト（確認あり）"""
    # clean_databaseメソッドのモック
    mock_db.clean_database.return_value = {
        'keywords': 5,
        'search_results': 75,
        'search_history': 3,
        'export_history': 2
    }
    
    # コマンド実行（確認に「y」と応答）
    result = runner.invoke(app, ["clean-all"], input="y\n")
    
    # 結果確認
    assert result.exit_code == 0
    assert "データベースを初期化しました" in result.stdout
    assert "5件" in result.stdout  # keywords
    assert "75件" in result.stdout  # search_results
    assert "3件" in result.stdout  # search_history
    assert "2件" in result.stdout  # export_history

def test_clean_database_no_confirm(mock_config, mock_db):
    """データベースクリーンアップテスト（確認なし）"""
    # clean_databaseメソッドのモック
    mock_db.clean_database.return_value = {
        'keywords': 5,
        'search_results': 75,
        'search_history': 3,
        'export_history': 2
    }
    
    # コマンド実行（--confirm オプション付き）
    result = runner.invoke(app, ["clean-all", "--confirm"])
    
    # 結果確認
    assert result.exit_code == 0
    assert "データベースを初期化しました" in result.stdout
    assert "5件" in result.stdout  # keywords
    assert "75件" in result.stdout  # search_results
    assert "3件" in result.stdout  # search_history
    assert "2件" in result.stdout  # export_history 