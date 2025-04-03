# データベースモデルの定義

from sqlalchemy import Column, Integer, String, Float, DateTime, Text, ForeignKey, Boolean
from sqlalchemy.orm import relationship, declarative_base
from datetime import datetime

Base = declarative_base()

class Keyword(Base):
    """キーワードを管理するモデル"""
    __tablename__ = 'keywords'

    id = Column(Integer, primary_key=True)
    keyword = Column(String, nullable=False)
    category = Column(String)
    last_searched_at = Column(DateTime)
    created_at = Column(DateTime, default=datetime.utcnow)
    status = Column(String, default='active')  # active, inactive, completed

    # リレーションシップ
    search_results = relationship("EbaySearchResult", back_populates="keyword")

    def __repr__(self):
        return f"<Keyword(id={self.id}, keyword='{self.keyword}', status='{self.status}')>"


class EbaySearchResult(Base):
    """eBay検索結果を保存するモデル"""
    __tablename__ = 'ebay_search_results'

    id = Column(Integer, primary_key=True)
    keyword_id = Column(Integer, ForeignKey('keywords.id'))
    search_job_id = Column(Integer, ForeignKey('search_history.id'))
    item_id = Column(String, nullable=False)
    title = Column(String)
    price = Column(Float)
    currency = Column(String, default='USD')
    shipping_price = Column(Float)
    stock_quantity = Column(Integer)
    seller_name = Column(String)
    seller_rating = Column(Float)
    seller_feedback_count = Column(Integer)
    auction_end_time = Column(DateTime)
    listing_type = Column(String)  # auction, fixed_price, etc
    condition = Column(String)
    is_buy_it_now = Column(Boolean, default=False)
    bids_count = Column(Integer, default=0)
    item_url = Column(String)
    image_url = Column(String)
    search_timestamp = Column(DateTime, default=datetime.utcnow)

    # リレーションシップ
    keyword = relationship("Keyword", back_populates="search_results")
    search_history = relationship("SearchHistory", back_populates="search_results")

    def __repr__(self):
        return f"<EbaySearchResult(id={self.id}, item_id='{self.item_id}', price={self.price})>"


class SearchHistory(Base):
    """検索ジョブの履歴を保存するモデル"""
    __tablename__ = 'search_history'

    id = Column(Integer, primary_key=True)
    start_time = Column(DateTime, default=datetime.utcnow)
    end_time = Column(DateTime)
    total_keywords = Column(Integer)
    processed_keywords = Column(Integer, default=0)
    successful_keywords = Column(Integer, default=0)
    failed_keywords = Column(Integer, default=0)
    status = Column(String, default='in_progress')  # in_progress, completed, failed
    error_log = Column(Text)
    execution_time_seconds = Column(Float)

    # リレーションシップ
    search_results = relationship("EbaySearchResult", back_populates="search_history")

    def __repr__(self):
        return f"<SearchHistory(id={self.id}, status='{self.status}', total={self.total_keywords}, processed={self.processed_keywords})>"


class ExportHistory(Base):
    """エクスポート操作の履歴を保存するモデル"""
    __tablename__ = 'export_history'

    id = Column(Integer, primary_key=True)
    export_time = Column(DateTime, default=datetime.utcnow)
    export_type = Column(String)  # csv, excel, google_sheets
    file_path = Column(String)
    record_count = Column(Integer)
    status = Column(String)  # success, failed
    notes = Column(Text)

    def __repr__(self):
        return f"<ExportHistory(id={self.id}, type='{self.export_type}', status='{self.status}')>"
