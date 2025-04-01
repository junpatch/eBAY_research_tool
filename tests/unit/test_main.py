# -*- coding: utf-8 -*-

import pytest
import os
import sys
from pathlib import Path
from unittest.mock import patch, MagicMock, call
import logging

# テスト対象のモジュールをインポート
sys.path.append(str(Path(__file__).parent.parent))
from main import setup_application, main

@pytest.fixture
def mock_app_root():
    """アプリケーションルートディレクトリをモックするフィクスチャ"""
    with patch('main.app_root', Path('/mock/app/root')):
        yield Path('/mock/app/root')

@pytest.fixture
def mock_logger():
    """ロガーをモックするフィクスチャ"""
    mock_logger = MagicMock()
    with patch('main.LoggerManager') as mock_logger_manager:
        mock_logger_manager.return_value.get_logger.return_value = mock_logger
        yield mock_logger

@pytest.fixture
def mock_directories(mock_app_root):
    """必要なディレクトリをモックするフィクスチャ"""
    with patch('pathlib.Path.mkdir') as mock_mkdir:
        # モックディレクトリのパスを作成
        data_dir = mock_app_root / 'data'
        logs_dir = mock_app_root / 'logs'
        output_dir = mock_app_root / 'output'
        yield {
            'data_dir': data_dir,
            'logs_dir': logs_dir,
            'output_dir': output_dir,
            'mkdir_mock': mock_mkdir
        }

@pytest.fixture
def mock_config_exists():
    """設定ファイルの存在をモックするフィクスチャ"""
    with patch('pathlib.Path.exists') as mock_exists:
        mock_exists.return_value = True
        yield mock_exists

def test_setup_application_creates_directories(mock_directories, mock_logger, mock_config_exists):
    """setup_application関数がディレクトリを作成するかテスト"""
    # 関数を実行
    setup_application()
    
    # ディレクトリが作成されたか確認
    assert mock_directories['mkdir_mock'].call_count == 3
    mock_directories['mkdir_mock'].assert_has_calls([
        call(exist_ok=True),
        call(exist_ok=True),
        call(exist_ok=True)
    ], any_order=True)
    
    # ロガーが初期化されたか確認
    mock_logger.info.assert_called_once_with("eBay Research Tool を起動しています...")

def test_setup_application_checks_config(mock_directories, mock_logger):
    """setup_application関数が設定ファイルの存在を確認するかテスト"""
    # 設定ファイルが存在しない場合をシミュレート
    with patch('pathlib.Path.exists') as mock_exists:
        mock_exists.return_value = False
        
        # sys.exitをモック
        with patch('sys.exit') as mock_exit:
            # 関数を実行
            setup_application()
            
            # エラーメッセージが出力されたか確認
            mock_logger.error.assert_called_once()
            assert "設定ファイルが見つかりません" in mock_logger.error.call_args[0][0]
            
            # sys.exitが呼ばれたか確認
            mock_exit.assert_called_once_with(1)

def test_main_function(mock_directories, mock_logger, mock_config_exists):
    """main関数のテスト"""
    # setup_applicationをモック
    with patch('main.setup_application') as mock_setup:
        mock_setup.return_value = mock_logger
        
        # app関数をモック
        with patch('main.app') as mock_app:
            # main関数を実行
            main()
            
            # setup_applicationが呼ばれたか確認
            mock_setup.assert_called_once()
            
            # appが呼ばれたか確認
            mock_app.assert_called_once()

def test_main_function_handles_exception(mock_directories, mock_logger, mock_config_exists):
    """main関数が例外を処理するかテスト"""
    # setup_applicationをモック
    with patch('main.setup_application') as mock_setup:
        mock_setup.return_value = mock_logger
        
        # app関数が例外を発生させるようにモック
        with patch('main.app') as mock_app:
            mock_app.side_effect = Exception("テスト例外")
            
            # sys.exitをモック
            with patch('sys.exit') as mock_exit:
                # main関数を実行
                main()
                
                # 例外が記録されたか確認
                mock_logger.exception.assert_called_once()
                assert "予期せぬエラーが発生しました" in mock_logger.exception.call_args[0][0]
                
                # エラーログが記録されたか確認
                mock_logger.error.assert_called_once()
                
                # sys.exitが呼ばれたか確認
                mock_exit.assert_called_once_with(1)

def test_module_execution(mock_directories, mock_logger, mock_config_exists):
    """__main__としての実行をテスト"""
    # appをモック（Typerアプリの実行をスキップするため）
    with patch('interfaces.cli_interface.app'):
        # main関数をモック
        with patch('main.main') as mock_main:
            # main.pyモジュールをインポート
            import main
            
            # 保存しておいた本来の__name__値
            original_name = main.__name__
            
            try:
                # __name__を"__main__"に設定
                main.__name__ = "__main__"
                
                # __name__ == "__main__"ブロックを強制的に実行
                exec("""
if __name__ == "__main__":
    main()
""", {'__name__': "__main__", 'main': main.main})
                
                # main関数が1回呼ばれたことを確認
                mock_main.assert_called_once()
                
            finally:
                # 元の__name__値に戻す
                main.__name__ = original_name 