# -*- coding: utf-8 -*-

import pytest
import os
import tempfile
from pathlib import Path
from sqlalchemy import create_engine, inspect
from sqlalchemy.orm import sessionmaker
from core.database_manager import DatabaseManager
from models.data_models import Base, Keyword, EbaySearchResult, SearchHistory, ExportHistory
from datetime import datetime
from unittest.mock import patch

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
    manager.close()  # テスト終了時にエンジンを閉じる

def test_database_manager_init(temp_db_path):
    """DatabaseManagerの初期化をテスト"""
    db_manager = DatabaseManager(temp_db_path)
    assert db_manager is not None
    assert db_manager.engine is not None

def test_create_tables(db_manager):
    """テーブル作成機能をテスト"""
    # テーブルが作成されたことを確認
    inspector = inspect(db_manager.engine)
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

def test_session_scope_with_exception(db_manager):
    """セッションスコープで例外が発生した場合のテスト"""
    # 例外を発生させる
    with pytest.raises(Exception) as exc_info:
        with db_manager.session_scope() as session:
            raise Exception("テスト例外")
    
    assert "テスト例外" in str(exc_info.value)

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

def test_add_keyword_duplicate(db_manager):
    """重複キーワードの追加テスト"""
    # 最初のキーワードを追加
    keyword_id1 = db_manager.add_keyword("duplicate keyword", "test category")
    
    # 同じキーワードをもう一度追加
    keyword_obj = db_manager.add_keyword("duplicate keyword", "another category")
    
    # 実装上、既存のKeywordオブジェクトが返されることを確認
    assert isinstance(keyword_obj, Keyword)
    
    # データベース内のキーワードが1つだけであることを確認（重複は追加されない）
    with db_manager.session_scope() as session:
        count = session.query(Keyword).filter_by(keyword="duplicate keyword").count()
        assert count == 1

def test_add_keywords_bulk(db_manager):
    """一括キーワード追加機能をテスト"""
    # キーワードリストを作成
    keywords = [
        ("bulk keyword1", "category1"),
        ("bulk keyword2", "category2"),
        "bulk keyword3"  # カテゴリなし
    ]
    
    # 一括追加
    added_count = db_manager.add_keywords_bulk(keywords)
    assert added_count == 3
    
    # 追加されたキーワードを確認
    with db_manager.session_scope() as session:
        keywords = session.query(Keyword).all()
        assert len(keywords) == 3
        
        # カテゴリあり/なしが正しく処理されていることを確認
        category_count = session.query(Keyword).filter(Keyword.category != None).count()
        assert category_count == 2
        
        no_category_count = session.query(Keyword).filter(Keyword.category == None).count()
        assert no_category_count == 1

def test_add_keywords_bulk_with_duplicates(db_manager):
    """重複を含む一括キーワード追加のテスト"""
    # まず1つのキーワードを追加
    db_manager.add_keyword("existing keyword", "category")
    
    # 重複を含むキーワードリスト
    keywords = [
        ("existing keyword", "new category"),  # 既存キーワード
        ("new keyword", "category")  # 新規キーワード
    ]
    
    # 一括追加
    added_count = db_manager.add_keywords_bulk(keywords)
    assert added_count == 1  # 新規キーワードのみカウントされる
    
    # 追加されたキーワードを確認
    with db_manager.session_scope() as session:
        keywords = session.query(Keyword).all()
        assert len(keywords) == 2  # 合計で2つのキーワード

def test_get_keywords(db_manager):
    """キーワード取得機能をテスト"""
    # キーワードを追加
    keyword_id1 = db_manager.add_keyword("test keyword1", "test category1")
    keyword_id2 = db_manager.add_keyword("test keyword2", "test category2")
    
    # キーワードを取得
    keywords = db_manager.get_keywords()
    assert keywords is not None
    assert len(keywords) == 2
    assert keywords[0].keyword == "test keyword1"
    assert keywords[0].category == "test category1"
    assert keywords[1].keyword == "test keyword2"
    assert keywords[1].category == "test category2"
    
    # limitの機能を確認
    limited_keywords = db_manager.get_keywords(limit=1)
    assert len(limited_keywords) == 1
    assert limited_keywords[0].keyword == "test keyword1"
    assert limited_keywords[0].category == "test category1"

def test_get_keywords_with_status(db_manager):
    """ステータス指定でのキーワード取得テスト"""
    # 異なるステータスのキーワードを追加
    db_manager.add_keyword("active keyword", "category")  # デフォルトでactive
    
    # 手動でステータスを変更
    with db_manager.session_scope() as session:
        keyword = Keyword(keyword="completed keyword", category="category", status="completed")
        session.add(keyword)
    
    # ステータスでフィルタリング
    active_keywords = db_manager.get_keywords(status="active")
    assert len(active_keywords) == 1
    assert active_keywords[0].keyword == "active keyword"
    
    completed_keywords = db_manager.get_keywords(status="completed")
    assert len(completed_keywords) == 1
    assert completed_keywords[0].keyword == "completed keyword"

def test_save_search_results(db_manager):
    """検索結果保存機能をテスト"""
    # キーワードを追加
    keyword_id = db_manager.add_keyword("search keyword", "category")
    
    # 検索結果データ
    results = [
        {
            'item_id': 'item1',
            'title': 'Test Item 1',
            'price': 10.99,
            'currency': 'USD',
            'shipping_price': 2.99,
            'seller_name': 'Seller1',
            'item_url': 'http://example.com/item1'
        },
        {
            'item_id': 'item2',
            'title': 'Test Item 2',
            'price': 15.99,
            'currency': 'EUR',
            'item_url': 'http://example.com/item2'
        }
    ]
    
    # 保存
    job_id = 1 # ダミーのジョブID
    saved_count = db_manager.save_search_results(keyword_id, job_id, results)
    assert saved_count == 2
    
    # 保存された結果を確認
    with db_manager.session_scope() as session:
        search_results = session.query(EbaySearchResult).filter_by(keyword_id=keyword_id).all()
        assert len(search_results) == 2
        
        # 保存されたデータが正しいか確認
        assert search_results[0].item_id == 'item1'
        assert search_results[0].title == 'Test Item 1'
        assert search_results[0].price == 10.99
        assert search_results[0].currency == 'USD'
        assert search_results[0].shipping_price == 2.99
        
        assert search_results[1].item_id == 'item2'
        assert search_results[1].title == 'Test Item 2'
        assert search_results[1].price == 15.99
        assert search_results[1].currency == 'EUR'
        
        # キーワードの最終検索日時が更新されたことを確認
        keyword = session.query(Keyword).filter_by(id=keyword_id).first()
        assert keyword.last_searched_at is not None

def test_save_search_results_duplicate_items(db_manager):
    """重複アイテムID保存の回避をテスト"""
    # キーワードを追加
    keyword_id = db_manager.add_keyword("search keyword", "category")
    
    # 最初の検索結果保存
    results1 = [
        {
            'item_id': 'item1',
            'title': 'Test Item 1',
            'price': 10.99
        }
    ]
    job_id = 1 # ダミーのジョブID
    db_manager.save_search_results(keyword_id, job_id, results1)
    
    # 同じitem_idを含む検索結果を保存
    results2 = [
        {
            'item_id': 'item1',  # 既存のitem_id
            'title': 'Updated Item 1',
            'price': 9.99
        },
        {
            'item_id': 'item2',  # 新しいitem_id
            'title': 'Test Item 2',
            'price': 15.99
        }
    ]
    
    # 新しいアイテムだけが保存されるはず
    job_id = 1 # ダミーのジョブID
    saved_count = db_manager.save_search_results(keyword_id, job_id, results2)
    assert saved_count == 1
    
    # 保存された結果を確認
    with db_manager.session_scope() as session:
        search_results = session.query(EbaySearchResult).filter_by(keyword_id=keyword_id).all()
        assert len(search_results) == 2
        
        # item_idでソートして確認
        search_results = sorted(search_results, key=lambda x: x.item_id)
        assert search_results[0].item_id == 'item1'
        assert search_results[0].title == 'Test Item 1'  # 更新されていないことを確認
        assert search_results[1].item_id == 'item2'
        assert search_results[1].title == 'Test Item 2'

def test_save_search_results_empty_list(db_manager):
    """空リストでの検索結果保存テスト"""
    # キーワードを追加
    keyword_id = db_manager.add_keyword("search keyword", "category")
    
    # 空リスト保存
    job_id = 1 # ダミーのジョブID
    saved_count = db_manager.save_search_results(keyword_id, job_id, [])
    assert saved_count == 0

def test_start_search_job(db_manager):
    """検索ジョブ開始機能をテスト"""
    # 検索ジョブを開始
    job_id = db_manager.start_search_job(10)
    assert job_id is not None
    
    # ジョブが正しく作成されたことを確認
    with db_manager.session_scope() as session:
        job = session.query(SearchHistory).filter_by(id=job_id).first()
        assert job is not None
        assert job.total_keywords == 10
        assert job.processed_keywords == 0
        assert job.status == 'in_progress'
        assert job.start_time is not None

def test_update_search_job_status(db_manager):
    """検索ジョブ状態更新機能をテスト"""
    # 検索ジョブを開始
    job_id = db_manager.start_search_job(10)
    
    # 進捗更新
    db_manager.update_search_job_status(
        job_id, 
        processed=5, 
        successful=4, 
        failed=1
    )
    
    # 更新された状態を確認
    with db_manager.session_scope() as session:
        job = session.query(SearchHistory).filter_by(id=job_id).first()
        assert job.processed_keywords == 5
        assert job.successful_keywords == 4
        assert job.failed_keywords == 1
        assert job.status == 'in_progress'  # まだ進行中

def test_update_search_job_status_completion(db_manager):
    """検索ジョブ完了状態更新機能をテスト"""
    # 検索ジョブを開始
    job_id = db_manager.start_search_job(10)
    
    # 完了状態に更新
    db_manager.update_search_job_status(
        job_id, 
        processed=10, 
        successful=8, 
        failed=2, 
        status='completed'
    )
    
    # 更新された状態を確認
    with db_manager.session_scope() as session:
        job = session.query(SearchHistory).filter_by(id=job_id).first()
        assert job.processed_keywords == 10
        assert job.successful_keywords == 8
        assert job.failed_keywords == 2
        assert job.status == 'completed'
        assert job.end_time is not None
        assert job.execution_time_seconds > 0  # 実行時間が記録されている

def test_update_search_job_status_error(db_manager):
    """検索ジョブエラー記録機能をテスト"""
    # 検索ジョブを開始
    job_id = db_manager.start_search_job(5)
    
    # エラーを記録
    error_msg = "テストエラーメッセージ"
    db_manager.update_search_job_status(job_id, error=error_msg)
    
    # エラーログを確認
    with db_manager.session_scope() as session:
        job = session.query(SearchHistory).filter_by(id=job_id).first()
        assert error_msg in job.error_log
        
    # 追加のエラーを記録
    additional_error = "追加エラーメッセージ"
    db_manager.update_search_job_status(job_id, error=additional_error)
    
    # 複数のエラーログが結合されていることを確認
    with db_manager.session_scope() as session:
        job = session.query(SearchHistory).filter_by(id=job_id).first()
        assert error_msg in job.error_log
        assert additional_error in job.error_log

def test_update_search_job_status_nonexistent_job(db_manager):
    """存在しない検索ジョブの更新テスト"""
    # 存在しないジョブIDを指定
    nonexistent_id = 9999
    
    # エラーなく処理されることを確認
    db_manager.update_search_job_status(nonexistent_id, processed=5)
    
    # ジョブが存在しないことを確認
    with db_manager.session_scope() as session:
        job = session.query(SearchHistory).filter_by(id=nonexistent_id).first()
        assert job is None

def test_close(temp_db_path):
    """データベース接続の閉じる機能をテスト"""
    db_manager = DatabaseManager(temp_db_path)
    
    # engineとSessionをモック
    with patch.object(db_manager.Session, 'remove') as mock_remove, \
         patch.object(db_manager.engine, 'dispose') as mock_dispose:
        
        # closeメソッドを呼び出し
        db_manager.close()
        
        # 正しいメソッドが呼ばれたか確認
        mock_remove.assert_called_once()
        mock_dispose.assert_called_once()
