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

        self.base_dir = Path(__file__).parent.parent
        
        # 設定ファイルのパスを決定
        if config_path is None:
            config_path = os.environ.get('CONFIG_PATH', str(self.base_dir / 'config' / 'config.yaml'))
        
        config_path = Path(config_path)
            
        # 設定ファイルの存在確認
        if not config_path.exists():
            raise FileNotFoundError(f"設定ファイルが見つかりません: {config_path}")
            
        # 設定の読み込み
        with open(config_path, 'r', encoding='utf-8') as file:
            self.config = yaml.safe_load(file)
            
    def get(self, keys, default=None, value_type=None):
        """
        設定値を取得する
        
        Args:
            keys (list): 設定セクションとキーのリスト
            default: キーが存在しない場合のデフォルト値
            value_type (type, optional): 期待される値の型
            
        Returns:
            設定値、またはデフォルト値
        """
        if not isinstance(keys, (list, tuple)):
            keys = [keys]
            
        result = self.config
        for key in keys:
            if not isinstance(result, dict):
                return default
            if key not in result:
                return default
            result = result[key]
        
        if value_type and result is not None:
            try:
                return value_type(result)
            except (ValueError, TypeError):
                return default
                
        return result
    
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
    
    def get_with_env(self, keys, env_var_name, default=None, value_type=None):
        """
        環境変数と設定ファイルから値を取得する（環境変数が優先）
        
        Args:
            keys (list): 設定セクションとキーのリスト
            env_var_name (str): 環境変数名
            default: デフォルト値
            value_type (type, optional): 期待される値の型
            
        Returns:
            環境変数の値、設定値、またはデフォルト値
        """
        # 環境変数から取得
        env_value = self.get_from_env(env_var_name, None)
        if env_value is not None:
            if value_type:
                try:
                    return value_type(env_value)
                except (ValueError, TypeError):
                    pass
            return env_value
        
        # 設定ファイルから取得
        return self.get(keys, default, value_type)
    
    def get_from_env(self, env_var_name, default=None):
        """
        環境変数から値を取得する
        
        Args:
            env_var_name (str): 環境変数名
            default: 環境変数が存在しない場合のデフォルト値
            
        Returns:
            環境変数の値、またはデフォルト値
        """
        if env_var_name is None:
            return default
        return os.environ.get(env_var_name, default)
    
    def get_db_url(self):
        """
        データベース接続URLを取得する
        
        Returns:
            str: SQLAlchemy接続URL
        """
        # 環境変数または設定ファイルからURLを取得
        db_url = self.get_with_env(['database', 'url'], 'DB_URL', None, str)
        if db_url:
            return db_url
            
        # デフォルトのSQLite設定を使用
        db_type = self.get(['database', 'type'], 'sqlite', str)
        if db_type == 'sqlite':
            db_path = self.get_path(['database', 'path'])
            if db_path is None:
                db_path = self.base_dir / 'data' / 'ebay_research.db'
                
            # データベースディレクトリが存在しない場合は作成
            db_path.parent.mkdir(parents=True, exist_ok=True)
            
            return f"sqlite:///{db_path}"
        
        raise ValueError(f"サポートされていないデータベースタイプ: {db_type}")
