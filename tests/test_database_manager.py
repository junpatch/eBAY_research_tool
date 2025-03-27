# -*- coding: utf-8 -*-

import pytest
import os
import tempfile
from pathlib import Path
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from core.database_manager import DatabaseManager
from models.data_models import Base, Keyword, EbaySearchResult, SearchHistory

@pytest.fixture
def temp_db_path():
    """一時的なSQLiteデータベースファイルを作成するフィクスチャ"""
    with tempfile.NamedTemporaryFile(suffix='.db', delete=False) as tmp:
        tmp_path = tmp.name
    
    db_url = f'sqlite:///{tmp_path}'
    yield db_url
    
    # テスト後にファイルを削除
    os.unlink(tmp_path)

@pytest.fixture
def db_manager(temp_db_path):
    """データベースマネージャーのインスタンスを作成するフィクスチャ"""
    manager = DatabaseManager(temp_db_path)
    manager.create_tables()
    yield manager

def test_database_manager_init(temp_db_path):
    """DatabaseManagerの初期化をテスト"""
    db = DatabaseManager(temp_db_path)
    assert db is not None
    assert db.engine is not None

def test_create_tables(db_manager):
    """テーブル作成機能をテスト"""
    # テーブルが作成されたことを確認
    inspector = db_manager.engine.inspector
    tables = inspector.get_table_names()
    
    # 期待されるテーブルが存在するか確認
    expected_tables = ['keywords', 'ebay_search_results', 'search_history', 'export_history']
    for table in expected_tables:
        assert table in tables

def test_session_scope(db_manager):
    """セッションスコープをテスト"""
    with db_manager.session_scope() as session:
        # セッションが正常に作成されたことを確認
        assert session is not None
        
        # 簡単なクエリを実行してセッションが機能していることを確認
        assert session.query(Keyword).count() == 0

def test_add_keyword(db_manager):
    """キーワード追加機能をテスト"""
    # キーワードを追加
    keyword_id = db_manager.add_keyword("test keyword", "test category")
    assert keyword_id is not None
    
    # キーワードが正しく追加されたことを確認
    with db_manager.session_scope() as session:
        keyword = session.query(Keyword).filter_by(id=keyword_id).first()
        assert keyword is not None
        assert keyword.keyword == "test keyword"
        assert keyword.category == "test category"
        assert keyword.status == "active"  # デフォルトステータス

def test_get_keyword(db_manager):
    """キーワード取得機能をテスト"""
    # キーワードを追加
    keyword_id = db_manager.add_keyword("test keyword", "test category")
    
    # キーワードを取得
    keyword = db_manager.get_keyword(keyword_id)
    assert keyword is not None
    assert keyword.id == keyword_id
    assert keyword.keyword == "test keyword"
    assert keyword.category == "test category"
    
    # 存在しないキーワードIDでテスト
    nonexistent_keyword = db_manager.get_keyword(9999)
    assert nonexistent_keyword is None

def test_update_keyword_status(db_manager):
    """キーワードステータス更新機能をテスト"""
    # キーワードを追加
    keyword_id = db_manager.add_keyword("test keyword")
    
    # ステータスを変更
    db_manager.update_keyword_status(keyword_id, "completed")
    
    # 変更が適用されたことを確認
    with db_manager.session_scope() as session:
        keyword = session.query(Keyword).filter_by(id=keyword_id).first()
        assert keyword.status == "completed"

def test_get_active_keywords(db_manager):
    """アクティブなキーワード取得機能をテスト"""
    # 複数のキーワードを追加
    db_manager.add_keyword("keyword1", "category1")
    db_manager.add_keyword("keyword2", "category2")
    keyword3_id = db_manager.add_keyword("keyword3", "category3")
    
    # キーワード3のステータスをcompletedに変更
    db_manager.update_keyword_status(keyword3_id, "completed")
    
    # アクティブなキーワードを取得
    active_keywords = db_manager.get_active_keywords()
    assert len(active_keywords) == 2  # keyword1とkeyword2のみがアクティブ
    
    # キーワードが正しく取得できたか確認
    keywords = [k.keyword for k in active_keywords]
    assert "keyword1" in keywords
    assert "keyword2" in keywords
    assert "keyword3" not in keywords  # completedなので含まれない

def test_save_search_results(db_manager):
    """検索結果保存機能をテスト"""
    # テスト用のキーワードを追加
    keyword_id = db_manager.add_keyword("test product")
    
    # サンプル検索結果
    results = [
        {
            "title": "Test Product 1",
            "url": "https://www.ebay.com/itm/12345",
            "price": 19.99,
            "currency": "USD",
            "condition": "New",
            "shipping": 5.99,
            "location": "US",
            "sold_date": None,
            "is_auction": False,
            "thumbnail": "https://example.com/thumb1.jpg"
        },
        {
            "title": "Test Product 2",
            "url": "https://www.ebay.com/itm/67890",
            "price": 24.99,
            "currency": "USD",
            "condition": "Used",
            "shipping": 4.99,
            "location": "UK",
            "sold_date": "2023-01-15",
            "is_auction": True,
            "thumbnail": "https://example.com/thumb2.jpg"
        }
    ]
    
    # 検索結果を保存
    count = db_manager.save_search_results(keyword_id, results)
    assert count == 2  # 2つの結果が保存された
    
    # 保存された結果を確認
    with db_manager.session_scope() as session:
        saved_results = session.query(EbaySearchResult).filter_by(keyword_id=keyword_id).all()
        assert len(saved_results) == 2
        
        # 最初の結果が正しく保存されたか確認
        result1 = next((r for r in saved_results if r.title == "Test Product 1"), None)
        assert result1 is not None
        assert result1.price == 19.99
        assert result1.shipping == 5.99
        assert result1.condition == "New"
        
        # 2番目の結果が正しく保存されたか確認
        result2 = next((r for r in saved_results if r.title == "Test Product 2"), None)
        assert result2 is not None
        assert result2.price == 24.99
        assert result2.condition == "Used"
        assert result2.is_auction is True

def test_start_search_job(db_manager):
    """検索ジョブ開始機能をテスト"""
    # 検索ジョブを開始
    job_id = db_manager.start_search_job(10)  # 10個のキーワードを検索予定
    assert job_id is not None
    
    # ジョブが正しく作成されたか確認
    with db_manager.session_scope() as session:
        job = session.query(SearchHistory).filter_by(id=job_id).first()
        assert job is not None
        assert job.total_keywords == 10
        assert job.processed == 0
        assert job.successful == 0
        assert job.failed == 0
        assert job.status == "started"

def test_update_search_job_status(db_manager):
    """検索ジョブステータス更新機能をテスト"""
    # 検索ジョブを開始
    job_id = db_manager.start_search_job(5)
    
    # ジョブステータスを更新
    db_manager.update_search_job_status(
        job_id,
        processed=3,
        successful=2,
        failed=1,
        status="in_progress",
        error="One keyword failed"
    )
    
    # 更新が適用されたか確認
    with db_manager.session_scope() as session:
        job = session.query(SearchHistory).filter_by(id=job_id).first()
        assert job.processed == 3
        assert job.successful == 2
        assert job.failed == 1
        assert job.status == "in_progress"
        assert job.error == "One keyword failed"
