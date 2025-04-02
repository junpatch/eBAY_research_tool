# ロガーマネージャークラス

import logging
import sys
from pathlib import Path
from logging.handlers import RotatingFileHandler
from datetime import datetime
import os

class LoggerManager:
    """
    アプリケーションログを管理するクラス
    """
    
    def __init__(self, log_dir=None, log_level=logging.INFO, app_name="ebay_research_tool"):
        """
        ロガーマネージャーの初期化
        
        Args:
            log_dir (str, optional): ログディレクトリ。指定がなければデフォルトディレクトリを使用。
            log_level (int): ログレベル（例：logging.INFO）
            app_name (str): アプリケーション名
        """
        self.app_name = app_name
        
        # 環境変数からログレベルを取得
        log_level_env = os.environ.get('LOG_LEVEL')
        if log_level_env:
            if log_level_env == 'DEBUG':
                self.log_level = logging.DEBUG
            elif log_level_env == 'INFO':
                self.log_level = logging.INFO
            elif log_level_env == 'WARNING':
                self.log_level = logging.WARNING
            elif log_level_env == 'ERROR':
                self.log_level = logging.ERROR
            elif log_level_env == 'CRITICAL':
                self.log_level = logging.CRITICAL
            else:
                self.log_level = log_level
        else:
            self.log_level = log_level
        
        # 環境変数からログファイルのパスを取得
        log_file_env = os.environ.get('LOG_FILE')
        
        # ログディレクトリの設定
        if log_file_env:
            # 環境変数で指定されたログファイルパスを使用
            log_file_path = Path(log_file_env)
            self.log_dir = log_file_path.parent
            self.log_filename = log_file_path.name
        elif log_dir is None:
            self.log_dir = Path(__file__).parent.parent / 'logs'
            self.log_filename = None  # 標準の命名規則を使用
        else:
            self.log_dir = Path(log_dir)
            self.log_filename = None  # 標準の命名規則を使用
            
        # ログディレクトリが存在しない場合は作成
        self.log_dir.mkdir(parents=True, exist_ok=True)
        
        # ルートロガーの設定
        self.root_logger = logging.getLogger()
        self.root_logger.setLevel(self.log_level)
        
        # すでに設定されているハンドラがあれば削除
        for handler in self.root_logger.handlers[::]:
            handler.close()
            self.root_logger.removeHandler(handler)
            
        # ファイルハンドラの設定
        self.file_handler = self._setup_file_handler()
        
        # コンソールハンドラの設定
        self.console_handler = self._setup_console_handler()
        
        self.logger = logging.getLogger(app_name)
        self.logger.info(f"{app_name} ロガーの初期化が完了しました")
    
    def __del__(self):
        """デストラクタ - ハンドラーリソースの解放"""
        if hasattr(self, 'file_handler') and self.file_handler:
            self.file_handler.close()
        if hasattr(self, 'console_handler') and self.console_handler:
            self.console_handler.close()

    def _setup_file_handler(self):
        """
        ファイルハンドラを設定する
        
        Returns:
            RotatingFileHandler: 設定されたファイルハンドラー
        """
        if self.log_filename:
            # 環境変数で指定されたファイル名を使用
            log_file = self.log_dir / self.log_filename
        else:
            # 標準の命名規則を使用
            today = datetime.now().strftime("%Y-%m-%d")
            log_file = self.log_dir / f"{self.app_name}_{today}.log"
        
        # ログファイルのパスを文字列に変換して渡す
        file_handler = RotatingFileHandler(
            filename=str(log_file),
            maxBytes=10 * 1024 * 1024,  # 10MB
            backupCount=5,
            encoding='utf-8'
        )
        
        formatter = logging.Formatter(
            '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
        )
        file_handler.setFormatter(formatter)
        file_handler.setLevel(self.log_level)
        
        self.root_logger.addHandler(file_handler)
        return file_handler
    
    def _setup_console_handler(self):
        """
        コンソールハンドラを設定する
        
        Returns:
            StreamHandler: 設定されたコンソールハンドラー
        """
        console_handler = logging.StreamHandler(sys.stdout)
        
        formatter = logging.Formatter(
            '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
        )
        console_handler.setFormatter(formatter)
        console_handler.setLevel(self.log_level)
        
        self.root_logger.addHandler(console_handler)
        return console_handler
    
    def get_logger(self, name=None):
        """
        指定された名前のロガーを取得する
        
        Args:
            name (str, optional): ロガー名。Noneの場合はアプリケーション名のロガーを返す。
            
        Returns:
            Logger: 指定された名前のロガー
        """
        if name is None:
            return self.logger
        return logging.getLogger(f"{self.app_name}.{name}")
