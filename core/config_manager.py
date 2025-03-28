# 設定マネージャークラス

import os
import yaml
from pathlib import Path
from dotenv import load_dotenv
from functools import reduce

class ConfigManager:
    """アプリケーション設定を管理するクラス"""
    
    def __init__(self, config_path=None):
        """
        設定マネージャーの初期化
        
        Args:
            config_path (str, optional): 設定ファイルのパス。指定がなければデフォルトパスを使用。
        """
        # 環境変数の読み込み
        load_dotenv()
        
        # 設定ファイルのパスを決定
        if config_path is None:
            base_dir = Path(__file__).parent.parent
            config_path = base_dir / 'config' / 'config.yaml'
        else:
            config_path = Path(config_path)
            
        # 設定ファイルの存在確認
        if not config_path.exists():
            raise FileNotFoundError(f"設定ファイルが見つかりません: {config_path}")
            
        # 設定の読み込み
        with open(config_path, 'r', encoding='utf-8') as file:
            self.config = yaml.safe_load(file)
            
        self.base_dir = base_dir
    
    def get(self, keys, default=None):
        """
        設定値を取得する
        
        Args:
            keys (list): 設定セクションとキーのリスト
            default: キーが存在しない場合のデフォルト値
            
        Returns:
            設定値、またはデフォルト値
        """
        return reduce(lambda dict, key: dict.get(key, default), keys, self.config)
    
    def get_path(self, keys):
        """
        パス設定を絶対パスとして取得する
        
        Args:
            keys (list): 設定セクションとキーのリスト
            
        Returns:
            Path: 絶対パスオブジェクト
        """
        path_str = self.get(keys)
        if not path_str:
            return None
            
        path = Path(path_str)
        if path.is_absolute():
            return path
            
        # 相対パスの場合はベースディレクトリからの相対パスとする
        return (self.base_dir / path_str).resolve()
    
    def get_from_env(self, env_var_name, default=None):
        """
        環境変数から値を取得する
        
        Args:
            env_var_name (str): 環境変数名
            default: 環境変数が存在しない場合のデフォルト値
            
        Returns:
            環境変数の値、またはデフォルト値
        """
        return os.environ.get(env_var_name, default)
    
    def get_db_url(self):
        """
        データベース接続URLを取得する
        
        Returns:
            str: SQLAlchemy接続URL
        """
        db_type = self.get(['database', 'type'], 'sqlite')
        
        if db_type == 'sqlite':
            db_path = self.get_path(['database', 'path'])
            if db_path is None:
                db_path = self.base_dir / 'data' / 'ebay_research.db'
                
            # データベースディレクトリが存在しない場合は作成
            db_path.parent.mkdir(parents=True, exist_ok=True)
            
            return f"sqlite:///{db_path}"
        
        # 将来的に他のデータベースタイプ（PostgreSQL、MySQLなど）に対応可能
        raise ValueError(f"サポートされていないデータベースタイプ: {db_type}")
