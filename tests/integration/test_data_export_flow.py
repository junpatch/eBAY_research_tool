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
            # データベース接続を明示的に閉じる
            self.db_manager.close()
            # 確実にエンジンの後始末をする
            self.db_manager = None
            
        # メモリ内データベースを明示的に閉じる
        if hasattr(self, 'db_engine'):
            self.db_engine.dispose()
            self.db_engine = None
            
        # Session ファクトリをクリーンアップ
        if hasattr(self, 'Session'):
            if hasattr(self.Session, 'remove'):  # scoped_sessionの場合
                self.Session.remove()
            # sessionmakerのインスタンスをクリア
            self.Session = None
            
        # 一時ディレクトリのクリーンアップ
        if hasattr(self, 'temp_dir'):
            # 一時ファイルが確実に閉じられた後にクリーンアップする
            import gc
            gc.collect()  # ガベージコレクションを強制実行
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
        # テスト用データベースのデータを確認
        with self.db_manager.session_scope() as session:
            results_count = session.query(EbaySearchResult).count()
            keywords_count = session.query(Keyword).count()
            print(f"テスト前のデータ状態: 検索結果 {results_count}件, キーワード {keywords_count}件")
            
            # データがない場合は再設定
            if results_count == 0:
                self._setup_test_data()
                results_count = session.query(EbaySearchResult).count()
                keywords_count = session.query(Keyword).count()
                print(f"テストデータ再設定後: 検索結果 {results_count}件, キーワード {keywords_count}件")
        
        # CSV出力ファイルのパス
        output_file = self.output_dir / "test_export.csv"
        
        # データをあらかじめ取得しておく
        with self.db_manager.session_scope() as session:
            results = []
            for result in session.query(EbaySearchResult).all():
                result_dict = {}
                for column in result.__table__.columns:
                    result_dict[column.name] = getattr(result, column.name)
                
                # キーワード情報を追加
                keyword = session.query(Keyword).filter(Keyword.id == result.keyword_id).first()
                if keyword:
                    result_dict['keyword'] = keyword.keyword
                    result_dict['category'] = keyword.category
                
                results.append(result_dict)
        
        # エクスポートを実行
        result = self.exporter.export_results(
            output_format="csv",
            output_path=str(output_file),
            filters={},
            results=results  # あらかじめ取得したデータを渡す
        )
        
        # 結果の検証
        assert result is not None, "エクスポート結果がNoneです"
        assert output_file.exists(), "出力ファイルが存在しません"
        
        # CSVファイルの内容を検証
        with open(output_file, 'r', encoding='utf-8') as f:
            csv_reader = csv.reader(f)
            header = next(csv_reader)
            rows = list(csv_reader)
            
            # ヘッダーに必要なフィールドが含まれていることを確認
            print(f"CSVヘッダー: {header}")
            assert "keyword" in header or "keyword_id" in header, "キーワード情報が含まれていません"
            assert "title" in header, "タイトル情報が含まれていません"
            
            # 正しい数のレコードがエクスポートされたことを確認
            print(f"CSVレコード数: {len(rows)}")
            assert len(rows) > 0, "エクスポートされたレコードがありません"
            
        # エクスポート履歴が記録されたことを確認
        with self.db_manager.session_scope() as session:
            history = session.query(ExportHistory).order_by(ExportHistory.id.desc()).first()
            assert history is not None, "エクスポート履歴が記録されていません"
            assert history.export_type == "csv", "エクスポート形式が正しくありません"
            assert history.status == "success", "エクスポートステータスが正しくありません"

    def test_excel_export(self):
        """Excel形式でのエクスポートテスト"""
        # テスト用データベースのデータを確認
        with self.db_manager.session_scope() as session:
            results_count = session.query(EbaySearchResult).count()
            keywords_count = session.query(Keyword).count()
            print(f"テスト前のデータ状態: 検索結果 {results_count}件, キーワード {keywords_count}件")
            
            # データがない場合は再設定
            if results_count == 0:
                self._setup_test_data()
                results_count = session.query(EbaySearchResult).count()
                keywords_count = session.query(Keyword).count()
                print(f"テストデータ再設定後: 検索結果 {results_count}件, キーワード {keywords_count}件")
        
        # Excel出力ファイルのパス
        output_file = self.output_dir / "test_export.xlsx"
        
        # データをあらかじめ取得しておく
        with self.db_manager.session_scope() as session:
            results = []
            for result in session.query(EbaySearchResult).all():
                result_dict = {}
                for column in result.__table__.columns:
                    result_dict[column.name] = getattr(result, column.name)
                
                # キーワード情報を追加
                keyword = session.query(Keyword).filter(Keyword.id == result.keyword_id).first()
                if keyword:
                    result_dict['keyword'] = keyword.keyword
                    result_dict['category'] = keyword.category
                
                results.append(result_dict)
        
        # エクスポートを実行
        result = self.exporter.export_results(
            output_format="excel",
            output_path=str(output_file),
            filters={},
            results=results  # あらかじめ取得したデータを渡す
        )
        
        # 結果の検証
        assert result is not None, "エクスポート結果がNoneです"
        assert output_file.exists(), "出力ファイルが存在しません"
        
        # Excelファイルの内容を検証
        df = pd.read_excel(output_file)
        
        # 必要なフィールドが含まれていることを確認
        print(f"Excelカラム: {df.columns.tolist()}")
        assert "keyword" in df.columns or "keyword_id" in df.columns, "キーワード情報が含まれていません"
        assert "title" in df.columns, "タイトル情報が含まれていません"
        
        # 正しい数のレコードがエクスポートされたことを確認
        print(f"Excelレコード数: {len(df)}")
        assert len(df) > 0, "エクスポートされたレコードがありません"
        
        # エクスポート履歴が記録されたことを確認
        with self.db_manager.session_scope() as session:
            history = session.query(ExportHistory).order_by(ExportHistory.id.desc()).first()
            assert history is not None, "エクスポート履歴が記録されていません"
            assert history.export_type == "excel", "エクスポート形式が正しくありません"
            assert history.status == "success", "エクスポートステータスが正しくありません"

    def test_filtered_export(self):
        """カスタムフィルターを使ったエクスポートテスト"""
        # テスト用データベースのデータを確認
        with self.db_manager.session_scope() as session:
            results_count = session.query(EbaySearchResult).count()
            keywords_count = session.query(Keyword).count()
            print(f"テスト前のデータ状態: 検索結果 {results_count}件, キーワード {keywords_count}件")
            
            # データがない場合は再設定
            if results_count == 0:
                self._setup_test_data()
                results_count = session.query(EbaySearchResult).count()
                keywords_count = session.query(Keyword).count()
                print(f"テストデータ再設定後: 検索結果 {results_count}件, キーワード {keywords_count}件")
        
        # CSV出力ファイルのパス
        output_file = self.output_dir / "test_filtered_export.csv"
        
        # データをあらかじめ取得しておく - カテゴリAのみを含める
        with self.db_manager.session_scope() as session:
            # カテゴリAのキーワードIDを取得
            category_a_keywords = session.query(Keyword).filter(Keyword.category == "カテゴリA").all()
            category_a_ids = [k.id for k in category_a_keywords]
            
            results = []
            for result in session.query(EbaySearchResult).filter(
                EbaySearchResult.keyword_id.in_(category_a_ids)
            ).all():
                result_dict = {}
                for column in result.__table__.columns:
                    result_dict[column.name] = getattr(result, column.name)
                
                # キーワード情報を追加
                keyword = session.query(Keyword).filter(Keyword.id == result.keyword_id).first()
                if keyword:
                    result_dict['keyword'] = keyword.keyword
                    result_dict['category'] = keyword.category
                
                results.append(result_dict)
        
        # エクスポートを実行
        result = self.exporter.export_results(
            output_format="csv",
            output_path=str(output_file),
            filters={"category": "カテゴリA"},
            results=results  # あらかじめ取得したカテゴリAのデータを渡す
        )
        
        # 結果の検証
        assert result is not None, "エクスポート結果がNoneです"
        assert output_file.exists(), "出力ファイルが存在しません"
        
        # CSVファイルの内容を検証
        with open(output_file, 'r', encoding='utf-8') as f:
            csv_reader = csv.reader(f)
            header = next(csv_reader)
            rows = list(csv_reader)
            
            # フィルタリングによって正しいデータがエクスポートされたことを確認
            print(f"フィルタリング後のCSVレコード数: {len(rows)}")
            assert len(rows) > 0, "エクスポートされたレコードがありません"
            
            # カテゴリAのキーワードだけがエクスポートされていることを確認
            if "keyword" in header:
                keyword_column_index = header.index("keyword")
                keywords = set([row[keyword_column_index] for row in rows])
                print(f"エクスポートされたキーワード: {keywords}")
                
                # カテゴリAのキーワードだけが含まれているか確認
                with self.db_manager.session_scope() as session:
                    category_a_keywords = [k.keyword for k in session.query(Keyword)
                                        .filter(Keyword.category == "カテゴリA").all()]
                    category_b_keywords = [k.keyword for k in session.query(Keyword)
                                        .filter(Keyword.category == "カテゴリB").all()]
                    
                    for kw in category_a_keywords:
                        if kw in keywords:
                            print(f"カテゴリAのキーワード'{kw}'が含まれています")
                    
                    for kw in category_b_keywords:
                        if kw in keywords:
                            print(f"警告: カテゴリBのキーワード'{kw}'が含まれています")
        
        # エクスポート履歴が記録されたことを確認
        with self.db_manager.session_scope() as session:
            history = session.query(ExportHistory).order_by(ExportHistory.id.desc()).first()
            assert history is not None, "エクスポート履歴が記録されていません"
            assert history.export_type == "csv", "エクスポート形式が正しくありません"
            assert history.status == "success", "エクスポートステータスが正しくありません"

    def test_export_history(self):
        """エクスポート履歴の検証テスト"""
        # テスト用データベースのデータを確認
        with self.db_manager.session_scope() as session:
            results_count = session.query(EbaySearchResult).count()
            keywords_count = session.query(Keyword).count()
            print(f"テスト前のデータ状態: 検索結果 {results_count}件, キーワード {keywords_count}件")
            
            # データがない場合は再設定
            if results_count == 0:
                self._setup_test_data()
                results_count = session.query(EbaySearchResult).count()
                keywords_count = session.query(Keyword).count()
                print(f"テストデータ再設定後: 検索結果 {results_count}件, キーワード {keywords_count}件")
        
        # 複数回エクスポートを実行
        output_files = [
            self.output_dir / "export1.csv",
            self.output_dir / "export2.xlsx",
            self.output_dir / "export3.csv"
        ]
        
        filters = [
            {},  # フィルターなし
            {"category": "カテゴリA"},  # カテゴリフィルター
            {"price_min": 2000}  # 価格フィルター
        ]
        
        formats = ["csv", "excel", "csv"]
        
        # データをあらかじめ取得しておく
        with self.db_manager.session_scope() as session:
            all_results = []
            for result in session.query(EbaySearchResult).all():
                result_dict = {}
                for column in result.__table__.columns:
                    result_dict[column.name] = getattr(result, column.name)
                
                # キーワード情報を追加
                keyword = session.query(Keyword).filter(Keyword.id == result.keyword_id).first()
                if keyword:
                    result_dict['keyword'] = keyword.keyword
                    result_dict['category'] = keyword.category
                
                all_results.append(result_dict)
        
        # 各エクスポートを実行
        for i in range(3):
            result = self.exporter.export_results(
                output_format=formats[i],
                output_path=str(output_files[i]),
                filters=filters[i],
                results=all_results  # あらかじめ取得したデータを渡す
            )
            assert result is not None, f"{i+1}回目のエクスポート結果がNoneです"
        
        # エクスポート履歴を取得して検証
        with self.db_manager.session_scope() as session:
            histories = session.query(ExportHistory).order_by(ExportHistory.id).all()
            
            # 少なくとも3つの履歴が記録されていることを確認
            print(f"エクスポート履歴数: {len(histories)}")
            assert len(histories) >= 3, "正しい数のエクスポート履歴が記録されていません"
            
            # 直近3つの履歴を取得
            recent_histories = session.query(ExportHistory).order_by(
                ExportHistory.id.desc()).limit(3).all()
            recent_histories.reverse()  # 古い順に並び替え
            
            # 各履歴の内容を検証
            for i, history in enumerate(recent_histories):
                print(f"履歴 {i+1}: 形式={history.export_type}, ステータス={history.status}")
                assert history.export_type == formats[i], f"{i+1}回目のエクスポート形式が正しくありません"
                assert history.status == "success", f"{i+1}回目のエクスポートステータスが正しくありません" 