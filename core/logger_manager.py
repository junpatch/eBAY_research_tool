# ロガーマネージャークラス

import logging
import sys
from pathlib import Path
from logging.handlers import RotatingFileHandler
from datetime import datetime

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
        self.log_level = log_level
        
        # ログディレクトリの設定
        if log_dir is None:
            self.log_dir = Path(__file__).parent.parent / 'logs'
        else:
            self.log_dir = Path(log_dir)
            
        # ログディレクトリが存在しない場合は作成
        self.log_dir.mkdir(parents=True, exist_ok=True)
        
        # ルートロガーの設定
        self.root_logger = logging.getLogger()
        self.root_logger.setLevel(log_level)
        
        # すでに設定されているハンドラがあれば削除
        for handler in self.root_logger.handlers[::]:
            self.root_logger.removeHandler(handler)
            
        # ファイルハンドラの設定
        self._setup_file_handler()
        
        # コンソールハンドラの設定
        self._setup_console_handler()
        
        self.logger = logging.getLogger(app_name)
        self.logger.info(f"{app_name} ロガーの初期化が完了しました")
    
    def _setup_file_handler(self):
        """
        ファイルハンドラを設定する
        """
        today = datetime.now().strftime("%Y-%m-%d")
        log_file = self.log_dir / f"{self.app_name}_{today}.log"
        
        file_handler = RotatingFileHandler(
            filename=log_file,
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
    
    def _setup_console_handler(self):
        """
        コンソールハンドラを設定する
        """
        console_handler = logging.StreamHandler(sys.stdout)
        
        formatter = logging.Formatter(
            '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
        )
        console_handler.setFormatter(formatter)
        console_handler.setLevel(self.log_level)
        
        self.root_logger.addHandler(console_handler)
    
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
