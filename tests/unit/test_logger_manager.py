# -*- coding: utf-8 -*-

import pytest
import os
import sys
import tempfile
import logging
from pathlib import Path
from unittest.mock import patch, MagicMock
from core.logger_manager import LoggerManager

@pytest.fixture
def temp_log_dir():
    """一時的なログディレクトリを作成するフィクスチャ"""
    with tempfile.TemporaryDirectory() as tmp_dir:
        yield tmp_dir

@pytest.fixture
def logger_manager(temp_log_dir):
    """ロガーマネージャーのインスタンスを作成するフィクスチャ"""
    # テスト用のログレベルを設定
    log_level = logging.DEBUG
    app_name = "test_app"
    
    # ロガーマネージャーのインスタンスを作成
    logger_manager = LoggerManager(
        log_dir=temp_log_dir,
        log_level=log_level,
        app_name=app_name
    )
    
    yield logger_manager
    
    # テスト後に全てのハンドラをクリア
    root_logger = logging.getLogger()
    for handler in root_logger.handlers[:]:
        handler.close()
        root_logger.removeHandler(handler)

def test_init(logger_manager, temp_log_dir):
    """初期化のテスト"""
    # 検証
    assert logger_manager.app_name == "test_app"
    assert logger_manager.log_level == logging.DEBUG
    assert Path(logger_manager.log_dir) == Path(temp_log_dir)
    
    # ログディレクトリが作成されたことを確認
    assert os.path.exists(temp_log_dir)
    
    # ルートロガーが設定されていることを確認
    assert logger_manager.root_logger.level == logging.DEBUG
    
    # ファイルハンドラとコンソールハンドラが設定されていることを確認
    # pytest のためにハンドラー数ではなく、必要なハンドラータイプが存在することを確認
    handlers = logger_manager.root_logger.handlers
    assert any(isinstance(h, logging.handlers.RotatingFileHandler) for h in handlers)
    assert any(isinstance(h, logging.StreamHandler) and not isinstance(h, logging.handlers.RotatingFileHandler) for h in handlers)

def test_default_log_dir():
    """デフォルトのログディレクトリが正しく設定されるかテスト"""
    # ハンドラ設定メソッドと mkdir をモック
    with patch('core.logger_manager.LoggerManager._setup_file_handler') as mock_setup_file, \
         patch('core.logger_manager.LoggerManager._setup_console_handler') as mock_setup_console, \
         patch('pathlib.Path.mkdir') as mock_mkdir:
        
        # log_dir を指定せずに初期化
        logger_manager = LoggerManager()
        
        # デフォルトのログディレクトリはcore/logger_manager.pyの親ディレクトリ/logsになるはず
        expected_log_dir = Path(__file__).parent.parent.parent / 'logs'
        assert logger_manager.log_dir == expected_log_dir
        
        # ディレクトリが作成されたこと（mkdirが呼ばれたこと）を確認
        mock_mkdir.assert_called_once_with(parents=True, exist_ok=True)
        
        # ハンドラ設定が呼ばれていないことを確認（モックしたため）
        mock_setup_file.assert_not_called()
        mock_setup_console.assert_not_called()

def test_file_handler_setup(logger_manager, temp_log_dir):
    """ファイルハンドラの設定テスト"""
    # ファイルハンドラを持つハンドラを探す
    file_handlers = [h for h in logger_manager.root_logger.handlers 
                    if isinstance(h, logging.handlers.RotatingFileHandler)]
    assert len(file_handlers) == 1
    
    file_handler = file_handlers[0]
    # ファイルパスの確認
    assert file_handler.baseFilename.startswith(temp_log_dir)
    assert "test_app_" in file_handler.baseFilename
    assert file_handler.baseFilename.endswith(".log")
    
    # ログレベルの確認
    assert file_handler.level == logging.DEBUG
    
    # フォーマッターの確認
    formatter = file_handler.formatter
    assert "%(asctime)s" in formatter._fmt
    assert "%(name)s" in formatter._fmt
    assert "%(levelname)s" in formatter._fmt
    assert "%(message)s" in formatter._fmt
    
    # ローテーション設定の確認
    assert file_handler.maxBytes == 10 * 1024 * 1024  # 10MB
    assert file_handler.backupCount == 5
    assert file_handler.encoding == 'utf-8'

def test_console_handler_setup(logger_manager):
    """コンソールハンドラの設定テスト"""
    # コンソールハンドラを持つハンドラを探す
    console_handlers = [h for h in logger_manager.root_logger.handlers 
                       if isinstance(h, logging.StreamHandler) and not 
                       isinstance(h, logging.handlers.RotatingFileHandler)]
    
    # pytest が追加するハンドラがあるため、少なくとも1つ以上存在することを確認
    assert len(console_handlers) >= 1
    
    # LoggerManagerが追加したStreamHandlerを特定（通常は最初のものと予想）
    console_handler = None
    for handler in console_handlers:
        if hasattr(handler, 'stream') and handler.stream == sys.stdout:
            console_handler = handler
            break
    
    assert console_handler is not None, "コンソールハンドラが見つかりません"
    
    # ログレベルの確認
    assert console_handler.level == logging.DEBUG
    
    # フォーマッターの確認
    formatter = console_handler.formatter
    assert "%(asctime)s" in formatter._fmt
    assert "%(name)s" in formatter._fmt
    assert "%(levelname)s" in formatter._fmt
    assert "%(message)s" in formatter._fmt

def test_get_logger(logger_manager):
    """ロガー取得機能のテスト"""
    # アプリケーション名のロガーを取得
    app_logger = logger_manager.get_logger()
    assert app_logger.name == "test_app"
    
    # 子ロガーを取得
    child_logger = logger_manager.get_logger("child")
    assert child_logger.name == "test_app.child"
    
    # 別の子ロガーを取得
    another_logger = logger_manager.get_logger("another")
    assert another_logger.name == "test_app.another"

def test_logging_functionality(logger_manager, temp_log_dir):
    """ロギング機能の実際の動作テスト"""
    # テスト用のメッセージ
    test_message = "これはテストログメッセージです"
    
    # ロガーを取得してメッセージをログ
    logger = logger_manager.get_logger()
    logger.info(test_message)
    
    # ログファイルが作成されたことを確認
    log_files = list(Path(temp_log_dir).glob("*.log"))
    assert len(log_files) == 1
    
    # ログファイルの内容を確認
    with open(log_files[0], 'r', encoding='utf-8') as f:
        log_content = f.read()
        assert test_message in log_content
        assert "INFO" in log_content
        assert logger.name in log_content

def test_multiple_instances():
    """複数のロガーマネージャーインスタンスが互いに影響しないことをテスト"""
    with tempfile.TemporaryDirectory() as tmp_dir1, \
         tempfile.TemporaryDirectory() as tmp_dir2:
        
        # 2つの異なるロガーマネージャーインスタンスを作成
        logger_manager1 = LoggerManager(
            log_dir=tmp_dir1,
            log_level=logging.DEBUG,
            app_name="app1"
        )
        
        logger_manager2 = LoggerManager(
            log_dir=tmp_dir2,
            log_level=logging.INFO,
            app_name="app2"
        )
        
        # それぞれのロガーが異なる名前を持つことを確認
        assert logger_manager1.get_logger().name == "app1"
        assert logger_manager2.get_logger().name == "app2"
        
        # それぞれのログディレクトリが異なることを確認
        assert logger_manager1.log_dir == Path(tmp_dir1)
        assert logger_manager2.log_dir == Path(tmp_dir2)
        
        # それぞれのログレベルが異なることを確認
        assert logger_manager1.log_level == logging.DEBUG
        assert logger_manager2.log_level == logging.INFO
        
        # テスト後にクリーンアップ
        root_logger = logging.getLogger()
        for handler in root_logger.handlers[:]:
            handler.close()
            root_logger.removeHandler(handler) 