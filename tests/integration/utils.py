"""
結合テスト用のユーティリティ関数
"""

import os
import json
import tempfile
from pathlib import Path
from datetime import datetime
from contextlib import contextmanager
from sqlalchemy import create_engine
from models.data_models import Base
import logging
import time

# プロジェクトのルートパス
ROOT_DIR = Path(__file__).parent.parent.parent

# テスト用フィクスチャのパス
FIXTURES_DIR = Path(__file__).parent / 'fixtures'
EBAY_RESPONSES_DIR = FIXTURES_DIR / 'ebay_responses'

def get_fixture_path(filename):
    """フィクスチャのパスを取得する"""
    return FIXTURES_DIR / filename

def get_ebay_response_fixture(filename):
    """eBay APIレスポンスのフィクスチャを取得し、必要な変換を行う"""
    fixture_path = EBAY_RESPONSES_DIR / filename
    with open(fixture_path, 'r', encoding='utf-8') as f:
        data = json.load(f)
    
    # 日付文字列をdatetimeオブジェクトに変換
    return convert_dates_in_ebay_response(data)

def convert_dates_in_ebay_response(response_data):
    """eBayレスポンスデータの日付文字列をdatetimeオブジェクトに変換する"""
    for item in response_data:
        if 'auction_end_time' in item and item['auction_end_time']:
            try:
                item['auction_end_time'] = datetime.fromisoformat(item['auction_end_time'])
            except ValueError:
                # ISO形式でない場合は別のパースを試みる
                try:
                    item['auction_end_time'] = datetime.strptime(
                        item['auction_end_time'], 
                        "%Y-%m-%dT%H:%M:%S%z"
                    )
                except ValueError:
                    # 他の形式も試す
                    formats = [
                        "%Y-%m-%dT%H:%M:%S.%f%z",
                        "%Y-%m-%d %H:%M:%S",
                        "%Y-%m-%d"
                    ]
                    for fmt in formats:
                        try:
                            item['auction_end_time'] = datetime.strptime(item['auction_end_time'], fmt)
                            break
                        except ValueError:
                            continue
                    else:
                        # 全ての形式が失敗した場合はNoneにする
                        item['auction_end_time'] = None
    return response_data

@contextmanager
def setup_test_database():
    """テスト用インメモリデータベースを作成して提供する"""
    # インメモリSQLiteデータベースエンジンを作成
    engine = create_engine('sqlite:///:memory:', echo=False)
    
    # テーブルを作成
    Base.metadata.create_all(engine)
    
    try:
        yield engine
    finally:
        # エンジンを閉じる（インメモリDBなので自動的にクリーンアップされる）
        try:
            engine.dispose()
            # Windows環境でのファイルロック解除のための少しの待機
            time.sleep(0.1)
        except Exception as e:
            logger = logging.getLogger(__name__)
            logger.error(f"データベースエンジンを閉じる際にエラーが発生しました: {e}")

@contextmanager
def temp_directory():
    """テスト用の一時ディレクトリを提供する"""
    temp_dir = tempfile.TemporaryDirectory()
    try:
        yield Path(temp_dir.name)
    finally:
        temp_dir.cleanup()

@contextmanager
def temp_env_vars(vars_dict):
    """一時的に環境変数を設定し、テスト後に元の値に戻す"""
    # 元の値を保存
    original_values = {}
    for key in vars_dict:
        if key in os.environ:
            original_values[key] = os.environ[key]
        else:
            original_values[key] = None
    
    # 新しい値を設定
    for key, value in vars_dict.items():
        os.environ[key] = value
    
    try:
        yield
    finally:
        # 元の値に戻す
        for key in vars_dict:
            if original_values[key] is not None:
                os.environ[key] = original_values[key]
            else:
                if key in os.environ:
                    del os.environ[key] 