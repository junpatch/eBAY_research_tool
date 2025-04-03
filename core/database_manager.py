# データベースマネージャークラス

import copy
from sqlalchemy import create_engine, func, desc
from sqlalchemy.orm import sessionmaker, scoped_session
from models.data_models import Base, Keyword, EbaySearchResult, SearchHistory, ExportHistory
from contextlib import contextmanager
import logging
from datetime import datetime
import time

logger = logging.getLogger(__name__)

class DatabaseManager:
    """データベースマネージャー"""
    
    def __init__(self, db_url, echo=False):
        """
        データベースの初期化
        
        Args:
            db_url (str): データベースURL
            echo (bool): SQLの出力を有効にするかどうか
        """
        self.engine = create_engine(db_url, echo=echo)
        self.SessionFactory = sessionmaker(bind=self.engine)
        self.Session = scoped_session(self.SessionFactory)
        
    def __enter__(self):
        """コンテキストマネージャーのエントリーポイント"""
        return self
        
    def __exit__(self, exc_type, exc_val, exc_tb):
        """コンテキストマネージャーの終了処理"""
        self.close()
        
    def close(self):
        """データベース接続を閉じる"""
        try:
            # 既存のセッションをすべて削除
            self.Session.remove()
            
            # エンジンのコネクションプールを処理中のコネクションを含めて全て閉じる
            self.engine.dispose()
            
            # Windows環境でのファイルロック解除のための少しの待機
            time.sleep(0.1)
            
            logger.info("データベース接続を閉じました。")
        except Exception as e:
            logger.error(f"データベース接続を閉じる際にエラーが発生しました: {e}")
        
    def create_tables(self):
        """テーブルの作成"""
        Base.metadata.create_all(self.engine)
        logger.info("テーブルを初期化しました。")
    
    @contextmanager
    def session_scope(self):
        """セッションの管理"""
        """
        使用例:
            with db_manager.session_scope() as session:
                session.add(object)
        """
        session = self.Session()
        try:
            yield session
            session.commit()
        except Exception as e:
            session.rollback()
            logger.error(f"セッション管理中にエラーが発生しました: {e}")
            raise
        finally:
            session.close()
    
    # キーワードの管理
    def add_keyword(self, keyword, category=None):
        """
        新しいキーワードを追加する
        
        Args:
            keyword (str): キーワード
            category (str, optional): カテゴリ
            
        Returns:
            int: 新しく追加されたキーワードのID
        """
        with self.session_scope() as session:
            # 既存のキーワードを確認
            existing = session.query(Keyword).filter(Keyword.keyword == keyword).first()
            if existing:
                return existing
                
            new_keyword = Keyword(
                keyword=keyword,
                category=category,
                status='active'
            )
            session.add(new_keyword)
            session.flush()  # IDを取得するためにflush
            return new_keyword.id
    
    def add_keywords_bulk(self, keywords):
        """
        複数のキーワードを一括で追加する
        
        Args:
            keywords (list): 新しく追加するキーワードのリスト
            
        Returns:
            int: 新しく追加されたキーワードの数
        """
        added_count = 0
        with self.session_scope() as session:
            for item in keywords:
                # キーワードとカテゴリを確認
                if isinstance(item, tuple) and len(item) >= 2:
                    keyword, category = item[0], item[1]
                else:
                    keyword, category = item, None
                    
                # 既存のキーワードを確認
                existing = session.query(Keyword).filter(Keyword.keyword == keyword).first()
                if not existing:
                    new_keyword = Keyword(
                        keyword=keyword,
                        category=category,
                        status='active'
                    )
                    session.add(new_keyword)
                    added_count += 1
                    
            return added_count
    
    def get_keywords(self, status='active', limit=None):
        """
        キーワードを取得する
        
        Args:
            status (str, optional): 取得するキーワードの状態 ('active', 'completed', 'failed', None)
                                    Noneまたは'all'の場合は全ステータスを取得
            limit (int, optional): 取得するキーワードの最大数
            
        Returns:
            list: 取得したキーワードのリスト
        """
        with self.session_scope() as session:
            query = session.query(Keyword)
            
            # ステータスが指定されている場合はフィルタする
            if status and status.lower() != 'all':
                query = query.filter(Keyword.status == status)
            
            # 順序付けと件数制限
            query = query.order_by(Keyword.id)
            if limit:
                query = query.limit(limit)
            
            result = copy.deepcopy(query.all())
            return result
    
    # 検索結果の保存
    def save_search_results(self, keyword_id, results):
        """
        検索結果を保存する
        
        Args:
            keyword_id (int): キーワードID
            results (list): 検索結果のリスト
            
        Returns:
            int: 保存した検索結果の数
        """
        if not results:
            return 0
            
        with self.session_scope() as session:
            # 更新日時を更新
            keyword = session.query(Keyword).filter(Keyword.id == keyword_id).first()
            if keyword:
                keyword.last_searched_at = datetime.utcnow()
                
            # 検索結果を保存
            search_results = []
            for result in results:
                item_id = result.get('item_id', '')
                # 既存の検索結果を確認
                if item_id and not session.query(EbaySearchResult).filter(
                    EbaySearchResult.keyword_id == keyword_id,
                    EbaySearchResult.item_id == item_id
                ).first():
                    search_result = EbaySearchResult(
                        keyword_id=keyword_id,
                        item_id=item_id,
                        title=result.get('title', ''),
                        price=result.get('price'),
                        currency=result.get('currency', 'USD'),
                        shipping_price=result.get('shipping_price'),
                        stock_quantity=result.get('stock_quantity'),
                        seller_name=result.get('seller_name', ''),
                        seller_rating=result.get('seller_rating'),
                        seller_feedback_count=result.get('seller_feedback_count'),
                        auction_end_time=result.get('auction_end_time'),
                        listing_type=result.get('listing_type', ''),
                        condition=result.get('condition', ''),
                        is_buy_it_now=result.get('is_buy_it_now', False),
                        bids_count=result.get('bids_count', 0),
                        item_url=result.get('item_url', ''),
                        image_url=result.get('image_url', '')
                    )
                    search_results.append(search_result)
            
            if search_results:
                session.add_all(search_results)
                
            return len(search_results)
    
    # 検索ジョブの開始
    def start_search_job(self, total_keywords):
        """
        検索ジョブを開始する
        
        Args:
            total_keywords (int): 検索するキーワードの総数
            
        Returns:
            int: 検索ジョブID
        """
        with self.session_scope() as session:
            history = SearchHistory(
                total_keywords=total_keywords,
                processed_keywords=0,
                status='in_progress'
            )
            session.add(history)
            session.flush()  # IDを取得
            return history.id
    
    def update_search_job_status(self, job_id, processed=None, successful=None, failed=None, status=None, error=None):
        """
        検索ジョブの状態を更新する
        
        Args:
            job_id (int): 検索ジョブID
            processed (int, optional): 検索したキーワード数
            successful (int, optional): 成功したキーワード数
            failed (int, optional): 失敗したキーワード数
            status (str, optional): 更新する状態 ('in_progress', 'completed', 'failed')
            error (str, optional): エラー情報
        """
        with self.session_scope() as session:
            job = session.query(SearchHistory).filter(SearchHistory.id == job_id).first()
            if not job:
                logger.error(f"検索ジョブID {job_id} が見つかりません")
                return
                
            if processed is not None:
                job.processed_keywords = processed
                
            if successful is not None:
                job.successful_keywords = successful
                
            if failed is not None:
                job.failed_keywords = failed
                
            if status:
                job.status = status
                if status in ['completed', 'failed']:
                    job.end_time = datetime.utcnow()
                    
                    # 実行時間の計算
                    if job.start_time:
                        delta = job.end_time - job.start_time
                        job.execution_time_seconds = delta.total_seconds()
                    
            if error:
                if job.error_log:
                    job.error_log += f"\n{error}"
                else:
                    job.error_log = error

    def get_search_stats(self):
        """
        検索統計情報を取得する
        
        Returns:
            dict: 検索統計情報を含む辞書
        """
        with self.session_scope() as session:
            # 総キーワード数
            total_keywords = session.query(func.count(Keyword.id)).scalar() or 0
            
            # 検索済みキーワード数（last_searched_atが設定されているもの）
            searched_keywords = session.query(func.count(Keyword.id))\
                .filter(Keyword.last_searched_at.isnot(None)).scalar() or 0
            
            # 総検索結果数
            total_results = session.query(func.count(EbaySearchResult.id)).scalar() or 0
            
            # 最終検索日時
            last_search_record = session.query(SearchHistory)\
                .order_by(SearchHistory.end_time.desc()).first()
            last_search = last_search_record.end_time if last_search_record else None
            
            # 平均検索結果数/キーワード
            avg_results = 0
            if searched_keywords > 0:
                avg_results = total_results / searched_keywords
            
            # トップセラー
            top_sellers = session.query(
                EbaySearchResult.seller_name,
                func.count(EbaySearchResult.id).label('count')
            ).group_by(EbaySearchResult.seller_name)\
              .order_by(desc('count'))\
              .limit(5).all()
            
            top_sellers_list = [
                {'seller_name': seller, 'count': count}
                for seller, count in top_sellers if seller
            ]
            
            # 価格統計
            price_min = session.query(func.min(EbaySearchResult.price)).scalar()
            price_max = session.query(func.max(EbaySearchResult.price)).scalar()
            price_avg = session.query(func.avg(EbaySearchResult.price)).scalar()
            
            price_stats = {
                'min': price_min,
                'max': price_max,
                'avg': price_avg
            }
            
            # 統計情報をまとめる
            stats = {
                'total_keywords': total_keywords,
                'searched_keywords': searched_keywords,
                'total_results': total_results,
                'last_search': last_search.strftime('%Y-%m-%d %H:%M:%S') if last_search else None,
                'avg_results_per_keyword': round(avg_results, 2),
                'top_sellers': top_sellers_list,
                'price_stats': price_stats
            }
            
            return stats
    
    def clean_database(self):
        """
        データベースをクリーンアップする
        
        Returns:
            dict: クリーンアップした各テーブルのレコード数
        """
        with self.session_scope() as session:
            # 削除前のレコード数をカウント
            keyword_count = session.query(func.count(Keyword.id)).scalar() or 0
            search_results_count = session.query(func.count(EbaySearchResult.id)).scalar() or 0
            search_history_count = session.query(func.count(SearchHistory.id)).scalar() or 0
            export_history_count = session.query(func.count(ExportHistory.id)).scalar() or 0
            
            # 全テーブルをクリア
            session.query(EbaySearchResult).delete()
            session.query(SearchHistory).delete()
            session.query(ExportHistory).delete()
            session.query(Keyword).delete()
            
            # 削除結果を返す
            result = {
                'keywords': keyword_count,
                'search_results': search_results_count,
                'search_history': search_history_count,
                'export_history': export_history_count
            }
            
            return result
