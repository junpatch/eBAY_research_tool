# u30c7u30fcu30bfu30d9u30fcu30b9u30deu30cdu30fcu30b8u30e3u30fcu30afu30e9u30b9

from sqlalchemy import create_engine, func
from sqlalchemy.orm import sessionmaker, scoped_session
from models.data_models import Base, Keyword, EbaySearchResult, SearchHistory, ExportHistory
from contextlib import contextmanager
import logging
from datetime import datetime

logger = logging.getLogger(__name__)

class DatabaseManager:
    """u30c7u30fcu30bfu30d9u30fcu30b9u63a5u7d9au3068u64cdu4f5cu3092u7ba1u7406u3059u308bu30afu30e9u30b9"""
    
    def __init__(self, db_url, echo=False):
        """
        u30c7u30fcu30bfu30d9u30fcu30b9u30deu30cdu30fcu30b8u30e3u30fcu306eu521du671fu5316
        
        Args:
            db_url (str): u30c7u30fcu30bfu30d9u30fcu30b9u63a5u7d9aURL
            echo (bool): SQLu51fau529bu3092u6709u52b9u306bu3059u308bu304bu3069u3046u304buff08u30c7u30d0u30c3u30b0u7528uff09
        """
        self.engine = create_engine(db_url, echo=echo)
        self.SessionFactory = sessionmaker(bind=self.engine)
        self.Session = scoped_session(self.SessionFactory)
        
    def create_tables(self):
        """u30c7u30fcu30bfu30d9u30fcu30b9u30c6u30fcu30d6u30ebu3092u4f5cu6210u3059u308b"""
        Base.metadata.create_all(self.engine)
        logger.info("u30c7u30fcu30bfu30d9u30fcu30b9u30c6u30fcu30d6u30ebu3092u4f5cu6210u3057u307eu3057u305f")
    
    @contextmanager
    def session_scope(self):
        """
        u30bbu30c3u30b7u30e7u30f3u3092u30b3u30f3u30c6u30adu30b9u30c8u30deu30cdu30fcu30b8u30e3u30fcu306bu3088u308au7ba1u7406u3059u308bu6a5fu80fd
        
        u4f8b: 
            with db_manager.session_scope() as session:
                session.add(object)
        """
        session = self.Session()
        try:
            yield session
            session.commit()
        except Exception as e:
            session.rollback()
            logger.error(f"u30c7u30fcu30bfu30d9u30fcu30b9u30bbu30c3u30b7u30e7u30f3u30a8u30e9u30fc: {e}")
            raise
        finally:
            session.close()
    
    # u30adu30fcu30efu30fcu30c9u7ba1u7406u30e1u30bdu30c3u30c9
    def add_keyword(self, keyword, category=None):
        """
        u65b0u3057u3044u30adu30fcu30efu30fcu30c9u3092u8ffdu52a0u3059u308b
        
        Args:
            keyword (str): u691cu7d22u30adu30fcu30efu30fcu30c9
            category (str, optional): u30abu30c6u30b4u30eau306eu6307u5b9auff08u4efbu610fuff09
            
        Returns:
            Keyword: u8ffdu52a0u3055u308cu305fu30adu30fcu30efu30fcu30c9u30aau30d6u30b8u30a7u30afu30c8
        """
        with self.session_scope() as session:
            # u540cu3058u30adu30fcu30efu30fcu30c9u304cu5b58u5728u3059u308bu304bu30c1u30a7u30c3u30af
            existing = session.query(Keyword).filter(Keyword.keyword == keyword).first()
            if existing:
                return existing
                
            new_keyword = Keyword(
                keyword=keyword,
                category=category,
                status='active'
            )
            session.add(new_keyword)
            return new_keyword
    
    def add_keywords_bulk(self, keywords):
        """
        u8907u6570u306eu30adu30fcu30efu30fcu30c9u3092u4e00u62ecu3067u8ffdu52a0u3059u308b
        
        Args:
            keywords (list): u8ffdu52a0u3059u308bu30adu30fcu30efu30fcu30c9u306eu30eau30b9u30c8u3002u5404u8981u7d20u306fu6587u5b57u5217u307eu305fu306f(keyword, category)u306eu30bfu30d7u30eb
            
        Returns:
            int: u8ffdu52a0u3055u308cu305fu30adu30fcu30efu30fcu30c9u306eu6570
        """
        added_count = 0
        with self.session_scope() as session:
            for item in keywords:
                # u30adu30fcu30efu30fcu30c9u304cu6587u5b57u5217u304bu30bfu30d7u30ebu304bu5224u5b9a
                if isinstance(item, tuple) and len(item) >= 2:
                    keyword, category = item[0], item[1]
                else:
                    keyword, category = item, None
                    
                # u540cu3058u30adu30fcu30efu30fcu30c9u304cu5b58u5728u3059u308bu304bu30c1u30a7u30c3u30af
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
        u30adu30fcu30efu30fcu30c9u3092u53d6u5f97u3059u308b
        
        Args:
            status (str): u53d6u5f97u3059u308bu30adu30fcu30efu30fcu30c9u306eu30b9u30c6u30fcu30bfu30b9
            limit (int, optional): u53d6u5f97u3059u308bu30adu30fcu30efu30fcu30c9u306eu6700u5927u6570
            
        Returns:
            list: u30adu30fcu30efu30fcu30c9u30aau30d6u30b8u30a7u30afu30c8u306eu30eau30b9u30c8
        """
        with self.session_scope() as session:
            query = session.query(Keyword).filter(Keyword.status == status)
            if limit:
                query = query.limit(limit)
            return query.all()
    
    # u691cu7d22u7d50u679cu7ba1u7406u30e1u30bdu30c3u30c9
    def save_search_results(self, keyword_id, results):
        """
        u691cu7d22u7d50u679cu3092u4fddu5b58u3059u308b
        
        Args:
            keyword_id (int): u30adu30fcu30efu30fcu30c9ID
            results (list): u691cu7d22u7d50u679cu306eu30c7u30a3u30afu30b7u30e7u30cau30eau30eau30b9u30c8
            
        Returns:
            int: u4fddu5b58u3055u308cu305fu7d50u679cu306eu6570
        """
        if not results:
            return 0
            
        with self.session_scope() as session:
            # u8a72u5f53u30adu30fcu30efu30fcu30c9u306eu6700u7d42u691cu7d22u65e5u6642u3092u66f4u65b0
            keyword = session.query(Keyword).filter(Keyword.id == keyword_id).first()
            if keyword:
                keyword.last_searched_at = datetime.utcnow()
                
            # u691cu7d22u7d50u679cu3092u4fddu5b58
            search_results = []
            for result in results:
                item_id = result.get('item_id', '')
                # u540cu3058item_idu304cu3042u308cu3070u30b9u30adu30c3u30d7uff08u91cdu8907u56deu907fuff09
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
    
    # u691cu7d22u5c65u6b74u7ba1u7406u30e1u30bdu30c3u30c9
    def start_search_job(self, total_keywords):
        """
        u691cu7d22u30b8u30e7u30d6u3092u958bu59cbu3057u3001u5c65u6b74u3092u8a18u9332u3059u308b
        
        Args:
            total_keywords (int): u51e6u7406u3059u308bu30adu30fcu30efu30fcu30c9u306eu7dcfu6570
            
        Returns:
            int: u691cu7d22u5c65u6b74ID
        """
        with self.session_scope() as session:
            history = SearchHistory(
                total_keywords=total_keywords,
                processed_keywords=0,
                status='in_progress'
            )
            session.add(history)
            session.flush()  # IDu3092u53d6u5f97u3059u308bu305fu3081u306bflush
            return history.id
    
    def update_search_job_status(self, job_id, processed=None, successful=None, failed=None, status=None, error=None):
        """
        u691cu7d22u30b8u30e7u30d6u306eu30b9u30c6u30fcu30bfu30b9u3092u66f4u65b0u3059u308b
        
        Args:
            job_id (int): u691cu7d22u5c65u6b74ID
            processed (int, optional): u51e6u7406u3057u305fu30adu30fcu30efu30fcu30c9u6570
            successful (int, optional): u6210u529fu3057u305fu30adu30fcu30efu30fcu30c9u6570
            failed (int, optional): u5931u6557u3057u305fu30adu30fcu30efu30fcu30c9u6570
            status (str, optional): u65b0u3057u3044u30b9u30c6u30fcu30bfu30b9
            error (str, optional): u30a8u30e9u30fcu30e1u30c3u30bbu30fcu30b8
        """
        with self.session_scope() as session:
            job = session.query(SearchHistory).filter(SearchHistory.id == job_id).first()
            if not job:
                logger.error(f"u691cu7d22u30b8u30e7u30d6ID {job_id} u304cu898bu3064u304bu308au307eu305bu3093")
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
                    
                    # u5b9fu884cu6642u9593u3092u8a08u7b97
                    if job.start_time:
                        delta = job.end_time - job.start_time
                        job.execution_time_seconds = delta.total_seconds()
                    
            if error:
                if job.error_log:
                    job.error_log += f"\n{error}"
                else:
                    job.error_log = error
