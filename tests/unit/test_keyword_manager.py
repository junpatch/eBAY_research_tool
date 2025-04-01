import pytest
from unittest.mock import Mock, MagicMock, patch
from pathlib import Path
from services.keyword_manager import KeywordManager
from core.database_manager import DatabaseManager
from core.config_manager import ConfigManager
import pandas as pd

@pytest.fixture
def mock_config():
    config = Mock()
    config.get = Mock(side_effect=lambda path, default=None: {
        ('google_sheets', 'credentials_path'): 'path/to/credentials.json',
        ('google_sheets', 'token_dir'): 'path/to/token'
    }.get(tuple(path), default))
    config.get_path = Mock(return_value=Path('path/to/token'))
    return config

@pytest.fixture
def mock_db():
    db = Mock()
    db.add_keywords_bulk = Mock(return_value=2)
    db.get_keywords = Mock(return_value=[])
    
    # セッションのモック
    mock_session = MagicMock()
    mock_session.commit = Mock()
    mock_session.query = Mock()
    mock_session.query.return_value.filter = Mock()
    mock_session.query.return_value.filter.return_value.first = Mock()
    
    db.session_scope = Mock()
    db.session_scope.return_value.__enter__ = Mock(return_value=mock_session)
    db.session_scope.return_value.__exit__ = Mock()
    return db

@pytest.fixture
def keyword_manager(mock_config, mock_db):
    return KeywordManager(mock_db, mock_config)

def test_import_from_csv(keyword_manager, mock_db, tmp_path):
    """CSVからのキーワードインポート機能のテスト"""
    # テストファイルの作成
    test_file = tmp_path / 'test.csv'
    with open(test_file, 'w') as f:
        f.write('keyword,category\ntest1,cat1\ntest2,cat2')
    
    # テスト実行
    result = keyword_manager.import_from_csv(str(test_file))
    
    # 検証
    mock_db.add_keywords_bulk.assert_called_once()
    assert result == 2

def test_get_active_keywords(keyword_manager, mock_db):
    """アクティブなキーワード取得機能のテスト"""
    # テスト実行
    keyword_manager.get_active_keywords(limit=10)

    # 検証
    mock_db.get_keywords.assert_called_once_with(status='active', limit=10)

def test_import_from_excel(keyword_manager, mock_db, tmp_path):
    """Excelからのキーワードインポート機能のテスト"""
    # テストファイルのパス
    test_file = str(tmp_path / 'test.xlsx')

    # テスト実行
    with patch('pandas.read_excel') as mock_read_excel:
        with patch('pathlib.Path.exists', return_value=True):  # ファイルの存在をモックで True に設定
            mock_read_excel.return_value = pd.DataFrame({
                'keyword': ['test1', 'test2'],
                'category': ['cat1', 'cat2']
            })
            result = keyword_manager.import_from_excel(test_file)

    # 検証
    mock_db.add_keywords_bulk.assert_called_once()
    assert result == 2

def test_import_from_google_sheets(keyword_manager, mock_db):
    """Google Sheetsからのキーワードインポート機能のテスト"""
    # GoogleSheetsInterface のモックを作成
    mock_sheets_instance = Mock()
    mock_sheets_instance.read_spreadsheet.return_value = [
        ['keyword', 'category'],
        ['keyword1', 'category1'],
        ['keyword2', 'category2']
    ]
    
    # インスタンス化をパッチ
    with patch('services.keyword_manager.GoogleSheetsInterface', return_value=mock_sheets_instance):
        # テスト実行
        result = keyword_manager.import_from_google_sheets('test_id', 'Sheet1!A1:B10')
        
        # 検証
        mock_sheets_instance.read_spreadsheet.assert_called_once_with('test_id', 'Sheet1!A1:B10')
        mock_db.add_keywords_bulk.assert_called_once()
        assert result == 2

def test_mark_keyword_as_processed(keyword_manager, mock_db):
    """キーワードステータス更新機能のテスト"""
    # テストデータ
    keyword_id = 1
    
    # モックの設定
    mock_session = MagicMock()
    mock_keyword = MagicMock()
    mock_session.query.return_value.filter.return_value.first.return_value = mock_keyword
    mock_db.session_scope.return_value.__enter__.return_value = mock_session
    
    # テスト実行
    keyword_manager.mark_keyword_as_processed(keyword_id)
    
    # 検証
    assert mock_keyword.status == 'completed'
    mock_session.commit.assert_called_once()
