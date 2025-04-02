"""
データエクスポート統合テスト

このモジュールでは、検索結果のエクスポート機能をテストします。
- CSV形式でのエクスポート
- Excel形式でのエクスポート
- カスタムフィルターを使ったエクスポート
- エクスポート履歴の検証
"""

import os
import csv
import pytest
import tempfile
from pathlib import Path
from datetime import datetime
from unittest.mock import patch, MagicMock

import pandas as pd
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from core.config_manager import ConfigManager
from core.database_manager import DatabaseManager
from services.data_exporter import DataExporter
from models.data_models import Base, Keyword, EbaySearchResult, ExportHistory

from tests.integration.utils import (
    setup_test_database,
    get_fixture_path,
    get_ebay_response_fixture,
    temp_directory
)

class TestDataExportFlow:
    """データエクスポート統合テスト"""

    def setup_method(self):
        """各テストメソッド実行前の準備"""
        # テスト用の設定
        self.config = ConfigManager()
        
        # テスト用データベースの作成
        self.db_engine = create_engine('sqlite:///:memory:', echo=False)
        self.Session = sessionmaker(bind=self.db_engine)
        
        # テーブルの作成
        Base.metadata.create_all(self.db_engine)
        
        # テスト用マネージャーの作成
        self.db_manager = DatabaseManager('sqlite:///:memory:', echo=False)
        self.db_manager.create_tables()
        
        # データエクスポーターの作成
        self.exporter = DataExporter(self.config, self.db_manager)
        
        # テスト用のデータを作成
        self._setup_test_data()
        
        # 一時ディレクトリを作成（出力ファイル用）
        self.temp_dir = tempfile.TemporaryDirectory()
        self.output_dir = Path(self.temp_dir.name)

    def teardown_method(self):
        """各テストメソッド実行後のクリーンアップ"""
        if hasattr(self, 'db_manager'):
            self.db_manager.close()
        if hasattr(self, 'db_engine'):
            self.db_engine.dispose()
        if hasattr(self, 'temp_dir'):
            self.temp_dir.cleanup()

    def _setup_test_data(self):
        """テスト用のデータをセットアップ"""
        # キーワードを追加
        keywords = [
            ("テスト用キーワード1", "カテゴリA"),
            ("テスト用キーワード2", "カテゴリB"),
            ("テスト用キーワード3", "カテゴリA")
        ]
        
        keyword_ids = []
        for kw, cat in keywords:
            keyword_id = self.db_manager.add_keyword(kw, cat)
            keyword_ids.append(keyword_id)
        
        # 検索結果を追加
        mock_results = get_ebay_response_fixture('search_result_sample.json')
        
        # 各キーワードに対して検索結果を保存
        for keyword_id in keyword_ids:
            self.db_manager.save_search_results(keyword_id, mock_results)
    
    def test_csv_export(self):
        """CSV形式でのエクスポートテスト"""
        # CSV出力ファイルのパス
        output_file = self.output_dir / "test_export.csv"
        
        # エクスポートを実行
        result = self.exporter.export_results(
            output_format="csv",
            output_path=str(output_file),
            filters={}
        )
        
        # 結果の検証
        assert result is not None
        assert output_file.exists()
        
        # CSVファイルの内容を検証
        with open(output_file, 'r', encoding='utf-8') as f:
            csv_reader = csv.reader(f)
            header = next(csv_reader)
            rows = list(csv_reader)
            
            # ヘッダーに必要なフィールドが含まれていることを確認
            assert "keyword" in header
            assert "title" in header
            assert "price" in header
            assert "seller_name" in header
            
            # 正しい数のレコードがエクスポートされたことを確認
            assert len(rows) == 9  # 3 keywords * 3 results = 9 records
            
        # エクスポート履歴が記録されたことを確認
        with self.db_manager.session_scope() as session:
            history = session.query(ExportHistory).order_by(ExportHistory.id.desc()).first()
            assert history is not None
            assert history.export_type == "csv"
            assert history.record_count == 9
            assert history.status == "success"

    def test_excel_export(self):
        """Excel形式でのエクスポートテスト"""
        # Excel出力ファイルのパス
        output_file = self.output_dir / "test_export.xlsx"
        
        # エクスポートを実行
        result = self.exporter.export_results(
            output_format="excel",
            output_path=str(output_file),
            filters={}
        )
        
        # 結果の検証
        assert result is not None
        assert output_file.exists()
        
        # Excelファイルの内容を検証
        df = pd.read_excel(output_file)
        
        # 必要なフィールドが含まれていることを確認
        assert "keyword" in df.columns
        assert "title" in df.columns
        assert "price" in df.columns
        assert "seller_name" in df.columns
        
        # 正しい数のレコードがエクスポートされたことを確認
        assert len(df) == 9  # 3 keywords * 3 results = 9 records
        
        # エクスポート履歴が記録されたことを確認
        with self.db_manager.session_scope() as session:
            history = session.query(ExportHistory).order_by(ExportHistory.id.desc()).first()
            assert history is not None
            assert history.export_type == "excel"
            assert history.record_count == 9
            assert history.status == "success"

    def test_filtered_export(self):
        """カスタムフィルターを使ったエクスポートテスト"""
        # CSV出力ファイルのパス
        output_file = self.output_dir / "test_filtered_export.csv"
        
        # カテゴリでフィルタリングした状態でエクスポートを実行
        result = self.exporter.export_results(
            output_format="csv",
            output_path=str(output_file),
            filters={"category": "カテゴリA"}
        )
        
        # 結果の検証
        assert result is not None
        assert output_file.exists()
        
        # CSVファイルの内容を検証
        with open(output_file, 'r', encoding='utf-8') as f:
            csv_reader = csv.reader(f)
            header = next(csv_reader)
            rows = list(csv_reader)
            
            # フィルタリングによって正しい数のレコードがエクスポートされたことを確認
            assert len(rows) == 6  # 2 keywords with category A * 3 results = 6 records
            
            # すべての行がカテゴリAに関連するキーワードであることを確認
            keyword_column_index = header.index("keyword")
            keywords = set([row[keyword_column_index] for row in rows])
            assert "テスト用キーワード1" in keywords
            assert "テスト用キーワード3" in keywords
            assert "テスト用キーワード2" not in keywords  # カテゴリBは除外されるべき
        
        # エクスポート履歴が記録されたことを確認
        with self.db_manager.session_scope() as session:
            history = session.query(ExportHistory).order_by(ExportHistory.id.desc()).first()
            assert history is not None
            assert history.export_type == "csv"
            assert history.record_count == 6
            assert history.status == "success"

    def test_export_history(self):
        """エクスポート履歴の検証テスト"""
        # 複数回エクスポートを実行
        output_files = [
            self.output_dir / "export1.csv",
            self.output_dir / "export2.excel",
            self.output_dir / "export3.csv"
        ]
        
        filters = [
            {},  # フィルターなし
            {"category": "カテゴリA"},  # カテゴリフィルター
            {"price_min": 2000}  # 価格フィルター
        ]
        
        formats = ["csv", "excel", "csv"]
        
        # 各エクスポートを実行
        for i in range(3):
            result = self.exporter.export_results(
                output_format=formats[i],
                output_path=str(output_files[i]),
                filters=filters[i]
            )
            assert result is not None
        
        # エクスポート履歴を取得して検証
        with self.db_manager.session_scope() as session:
            histories = session.query(ExportHistory).order_by(ExportHistory.id).all()
            
            # 正しい数の履歴が記録されていることを確認
            assert len(histories) == 3
            
            # 各履歴の内容を検証
            assert histories[0].export_type == "csv"
            assert histories[0].status == "success"
            
            assert histories[1].export_type == "excel"
            assert histories[1].status == "success"
            
            assert histories[2].export_type == "csv"
            assert histories[2].status == "success"
            
            # 履歴のタイムスタンプが時系列順になっていることを確認
            for i in range(1, 3):
                assert histories[i].export_time > histories[i-1].export_time 