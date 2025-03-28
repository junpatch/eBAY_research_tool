# -*- coding: utf-8 -*-

import pytest
import os
import tempfile
import yaml
from pathlib import Path
from core.config_manager import ConfigManager

@pytest.fixture
def temp_config_file():
    """一時的な設定ファイルを作成するフィクスチャ"""
    with tempfile.NamedTemporaryFile(suffix='.yaml', delete=False) as tmp:
        config_data = {
            'app': {
                'name': 'eBay Research Tool',
                'version': '1.0.0'
            },
            'database': {
                'url': 'sqlite:///data/ebay_research.db',
                'echo': False
            },
            'ebay': {
                'base_url': 'https://www.ebay.com',
                'username_env': 'EBAY_USERNAME',
                'password_env': 'EBAY_PASSWORD'
            },
            'paths': {
                'data_dir': 'data',
                'output_dir': 'output'
            }
        }
        yaml.dump(config_data, tmp, default_flow_style=False)
        tmp_path = tmp.name
    
    yield tmp_path
    
    # テスト後にファイルを削除
    os.unlink(tmp_path)

def test_config_manager_init(temp_config_file):
    """ConfigManagerの初期化をテスト"""
    config = ConfigManager(config_path=temp_config_file)
    assert config is not None
    assert config.config is not None

def test_config_get(temp_config_file):
    """設定値の取得をテスト"""
    config = ConfigManager(config_path=temp_config_file)
    
    # トップレベルの設定値を取得
    assert config.get(['app', 'name']) == 'eBay Research Tool'
    assert config.get(['app', 'version']) == '1.0.0'
    
    # 階層化された設定値を取得
    assert config.get(['database', 'url']) == 'sqlite:///data/ebay_research.db'
    assert config.get(['database', 'echo']) is False
    
    # デフォルト値をテスト
    assert config.get(['nonexistent', 'key'], 'default') == 'default'

def test_get_from_env(monkeypatch, temp_config_file):
    """環境変数からの設定値取得をテスト"""
    # 環境変数をモック
    monkeypatch.setenv('EBAY_USERNAME', 'testuser')
    monkeypatch.setenv('EBAY_PASSWORD', 'testpass')
    
    config = ConfigManager(config_path=temp_config_file)
    
    # 環境変数から値を取得
    assert config.get_from_env('EBAY_USERNAME') == 'testuser'
    assert config.get_from_env('EBAY_PASSWORD') == 'testpass'
    
    # 存在しない環境変数のデフォルト値をテスト
    assert config.get_from_env('NONEXISTENT_VAR', 'default') == 'default'

def test_get_path(temp_config_file):
    """パス解決をテスト"""
    config = ConfigManager(config_path=temp_config_file)
    
    # 相対パスの解決
    data_path = config.get_path(['paths', 'data_dir'])
    assert isinstance(data_path, Path)
    assert data_path.name == 'data'
    
    # 存在しないパス設定
    assert config.get_path(['nonexistent', 'path']) is None

def test_get_db_url(temp_config_file):
    """データベースURLの取得をテスト"""
    config = ConfigManager(config_path=temp_config_file)
    
    # デフォルトのURL
    db_url = config.get_db_url()
    assert db_url.startswith('sqlite:///')
    assert 'ebay_research.db' in db_url
