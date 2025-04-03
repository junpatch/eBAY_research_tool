# データエクスポートを行うクラス

import csv
import pandas as pd
import logging
from pathlib import Path
from datetime import datetime
from googleapiclient.discovery import build
from google_auth_oauthlib.flow import InstalledAppFlow
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
import os.path
import json
from models.data_models import EbaySearchResult, ExportHistory, Keyword
from interfaces.sheets_interface import GoogleSheetsInterface

logger = logging.getLogger(__name__)

class DataExporter:
    """
    スクレイピングしたデータをCSV、Excel、またはGoogle Sheetsに出力するクラス
    """
    
    def __init__(self, config_manager, database_manager):
        """
        DataExporterの初期化
        
        Args:
            config_manager: 設定マネージャーのインスタンス
            database_manager: データベースマネージャーのインスタンス
        """
        self.config = config_manager
        self.db = database_manager
        
        # 出力ディレクトリの設定
        self.output_dir = self.config.get_path(['export', 'output_dir'])
        if self.output_dir is None:
            self.output_dir = Path(__file__).parent.parent / 'data' / 'exports'
            
        # 出力ディレクトリが存在しない場合は作成
        self.output_dir.mkdir(parents=True, exist_ok=True)
        
        # デフォルトの出力形式
        self.default_format = self.config.get(['export', 'default_format'], 'csv')
        
    def export_results(self, output_format=None, output_path=None, filters=None, results=None, keyword_id=None, job_id=None):
        """
        検索結果をエクスポートする
        
        Args:
            output_format (str, optional): 出力形式（csv, excel, google_sheets）
            output_path (str, optional): 出力ファイルパス
            filters (dict, optional): 結果のフィルタリング条件
            results (list, optional): エクスポートする結果のリスト。指定がなければDBから取得。
            keyword_id (int, optional): 特定のキーワードIDの結果をエクスポートする場合に指定
            job_id (int, optional): 特定のジョブIDの結果をエクスポートする場合に指定
            
        Returns:
            dict: エクスポート結果を含む辞書
                - path: エクスポートされたファイルのパス、またはGoogle SheetのURL
                - is_empty: データが空だった場合はTrue
                - count: エクスポートされたレコード数
        """
        # 出力形式が指定されていない場合はデフォルトを使用
        if output_format is None:
            output_format = self.default_format
        
        # 結果が指定されていない場合はDBから取得
        if results is None:
            try:
                results = self._get_results_from_db(keyword_id, job_id)
            except Exception as e:
                logger.error(f"データベースからの結果取得中にエラーが発生しました: {e}")
                return None
            
        is_empty = not results
        if is_empty:
            logger.warning("エクスポートする結果がありません。空のファイルが作成されます。")
            # 空の結果セットでも処理を続行するために空のリストを設定
            results = []
            
        # DataFrame作成
        df = pd.DataFrame(results)
        
        # 列名の日本語化または整形（必要に応じて）
        # 一旦機能OFF。ONにする場合はexport_to_csv/excel/google_sheetsの中でも実行する
        # df = self._format_columns(df)
        
        # 出力ファイルパスが指定されていない場合は自動生成
        if output_path is None:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            
            if keyword_id:
                filename = f"ebay_results_keyword_{keyword_id}_{timestamp}"
            elif job_id:
                filename = f"ebay_results_job_{job_id}_{timestamp}"
            else:
                filename = f"ebay_results_{timestamp}"
                
            if output_format.lower() == 'csv':
                output_path = self.output_dir / f"{filename}.csv"
            elif output_format.lower() == 'excel':
                output_path = self.output_dir / f"{filename}.xlsx"
            elif output_format.lower() == 'google_sheets':
                output_path = filename
                
        # 形式に応じてエクスポート
        output_file_path = None
        if output_format.lower() == 'csv':
            output_file_path = self.export_to_csv(df, output_path)
        elif output_format.lower() == 'excel':
            output_file_path = self.export_to_excel(df, output_path)
        elif output_format.lower() == 'google_sheets':
            output_file_path = self.export_to_google_sheets(df, output_path)
        else:
            logger.error(f"サポートされていない形式です: {output_format}")
            return None
            
        if output_file_path is None:
            return None
            
        # 結果を辞書として返す
        return {
            "path": output_file_path,
            "is_empty": is_empty,
            "count": len(results)
        }
    
    def export_to_csv(self, data, file_path=None):
        """
        データをCSVファイルにエクスポートする
        
        Args:
            data: DataFrameまたはリスト
            file_path (str, optional): 出力ファイルパス
            
        Returns:
            str: エクスポートされたファイルのパス
        """
        try:
            # DataFrameでない場合はDataFrameに変換
            if not isinstance(data, pd.DataFrame):
                data = pd.DataFrame(data)
                
            # データが空でも処理を続行する
            if data.empty:
                logger.warning("エクスポートするデータが空です。空のCSVファイルを作成します。")
            
            # 出力ファイルパスの設定
            if file_path is None:
                timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                file_path = self.output_dir / f"ebay_results_{timestamp}.csv"
            else:
                if not file_path:
                    logger.error("無効なファイルパスが指定されました")
                    return None
                file_path = Path(file_path)
                
            # 出力ディレクトリが存在するか確認
            if not file_path.parent.exists():
                logger.error(f"出力ディレクトリが存在しません: {file_path.parent}")
                try:
                    # ディレクトリを作成しようとする
                    file_path.parent.mkdir(parents=True, exist_ok=True)
                    logger.info(f"出力ディレクトリを作成しました: {file_path.parent}")
                except Exception as e:
                    logger.error(f"出力ディレクトリの作成に失敗しました: {e}")
                    return None
                
            # CSVに出力
            data.to_csv(file_path, index=False, encoding='utf-8-sig')  # BOM付きUTF-8（Excelでの文字化け対策）
            
            # エクスポート履歴を記録
            self._record_export_history('csv', str(file_path), len(data))
            
            logger.info(f"データをCSVファイルにエクスポートしました: {file_path}")
            return str(file_path)
            
        except Exception as e:
            logger.error(f"CSVエクスポート中にエラーが発生しました: {e}")
            return None
    
    def export_to_excel(self, data, file_path=None):
        """
        データをExcelファイルにエクスポートする
        
        Args:
            data: DataFrameまたはリスト
            file_path (str, optional): 出力ファイルパス
            
        Returns:
            str: エクスポートされたファイルのパス
        """
        try:
            # DataFrameでない場合はDataFrameに変換
            if not isinstance(data, pd.DataFrame):
                data = pd.DataFrame(data)
                
            # データが空でも処理を続行する
            if data.empty:
                logger.warning("エクスポートするデータが空です。空のExcelファイルを作成します。")
            
            # 出力ファイルパスの設定
            if file_path is None:
                timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                file_path = self.output_dir / f"ebay_results_{timestamp}.xlsx"
            else:
                if not file_path:
                    logger.error("無効なファイルパスが指定されました")
                    return None
                file_path = Path(file_path)
            
            # 出力ディレクトリが存在するか確認
            if not file_path.parent.exists():
                logger.error(f"出力ディレクトリが存在しません: {file_path.parent}")
                try:
                    # ディレクトリを作成しようとする
                    file_path.parent.mkdir(parents=True, exist_ok=True)
                    logger.info(f"出力ディレクトリを作成しました: {file_path.parent}")
                except Exception as e:
                    logger.error(f"出力ディレクトリの作成に失敗しました: {e}")
                    return None
                
            # Excelに出力
            writer = pd.ExcelWriter(file_path, engine='openpyxl')
            data.to_excel(writer, sheet_name='eBay検索結果', index=False)
            
            # 列幅の自動調整 - データが空でない場合のみ実行
            if not data.empty:
                worksheet = writer.sheets['eBay検索結果']
                for i, column in enumerate(data.columns):
                    column_width = max(data[column].astype(str).map(len).max(), len(column) + 2)
                    worksheet.column_dimensions[chr(65 + i)].width = min(column_width, 50)  # 最大幅を50に制限
                
            writer.close()
            
            # エクスポート履歴を記録
            self._record_export_history('excel', str(file_path), len(data))
            
            logger.info(f"データをExcelファイルにエクスポートしました: {file_path}")
            return str(file_path)
            
        except Exception as e:
            logger.error(f"Excelエクスポート中にエラーが発生しました: {e}")
            return None
    
    def export_to_google_sheets(self, data, title=None, sheet_name=None):
        """
        データをGoogle Sheetsにエクスポートする
        
        Args:
            data: DataFrameまたはリスト
            title (str, optional): Google Sheets出力ファイル名
            sheet_name (str, optional): シート名
            
        Returns:
            str: スプレッドシートのURL
        """
        google_sheets = GoogleSheetsInterface(self.config)

        try:
            # DataFrameでない場合はDataFrameに変換
            if not isinstance(data, pd.DataFrame):
                data = pd.DataFrame(data)
            
            # データが空でも処理を続行する
            if data.empty:
                logger.warning("エクスポートするデータが空です。空のスプレッドシートを作成します。")
                # 空のデータの場合、少なくとも列名（空の場合はインデックス）を用意する
                if len(data.columns) == 0:
                    data = pd.DataFrame(columns=['item_id', 'title', 'price', 'currency'])
            
            # シート名が指定されていない場合はデフォルト名
            sheet_name = sheet_name or 'eBay検索結果'
            
            # TODO: 任意のフォルダ配下に作成する（Drive APIとの連携が必要）
            # スプレッドシートを新規作成
            spreadsheet_id = google_sheets.create_spreadsheet(title, [sheet_name])
            
            # データの整形（日付型やNoneの処理）
            data_values = data.fillna('').astype(str).values.tolist()
            header_values = data.columns.tolist()
            
            # まずシートをクリア
            google_sheets.clear_range(spreadsheet_id, f"{sheet_name}!A1:Z50000")
            
            # ヘッダーとデータを書き込み
            values = [header_values] + data_values
            result = google_sheets.write_to_spreadsheet(spreadsheet_id, f"{sheet_name}!A1", values)
            
            # エクスポート履歴を記録
            self._record_export_history('google_sheets', f"https://docs.google.com/spreadsheets/d/{spreadsheet_id}", len(data))
            
            logger.info(f"{result.get('updatedCells')}セルをGoogle Sheetsに書き込みました")
            return f"https://docs.google.com/spreadsheets/d/{spreadsheet_id}"
            
        except Exception as e:
            logger.error(f"Google Sheetsエクスポート中にエラーが発生しました: {e}")
            return None
    
    def _get_results_from_db(self, keyword_id=None, job_id=None):
        """
        データベースから検索結果を取得する
        
        Args:
            keyword_id (int, optional): 特定のキーワードIDの結果を取得
            job_id (int, optional): 特定のジョブIDの結果を取得
            
        Returns:
            list: 検索結果のリスト
        """
        results = []
        
        try:
            with self.db.session_scope() as session:
                # EbaySearchResultの全データを取得
                query = session.query(EbaySearchResult)
                
                # クエリ条件の指定
                if keyword_id:
                    logger.debug(f"キーワードID {keyword_id} でフィルタリングします")
                    query = query.filter(EbaySearchResult.keyword_id == keyword_id)
                    
                # ジョブIDの場合は、そのジョブで処理されたキーワードIDを特定する
                if job_id:
                    logger.debug(f"ジョブID {job_id} でフィルタリングします")
                    query = query.filter(EbaySearchResult.search_job_id == job_id)
                
                search_results = query.all()
                result_count = len(search_results)
                logger.info(f"データベースから{result_count}件の結果を取得しました。")
                
                # 結果が0件の場合は詳細なログを出力
                if result_count == 0:
                    if keyword_id:
                        # キーワードの存在確認
                        keyword_exists = session.query(session.query(Keyword).filter(Keyword.id == keyword_id).exists()).scalar()
                        logger.info(f"キーワードID {keyword_id} の存在: {keyword_exists}")
                    
                    # 全体の検索結果数を確認
                    total_results = session.query(EbaySearchResult).count()
                    logger.info(f"データベース内の総検索結果数: {total_results}")
                
                # 結果を辞書のリストに変換
                for result in search_results:
                    result_dict = {}
                    for column in result.__table__.columns:
                        result_dict[column.name] = getattr(result, column.name)
                        
                    # キーワード情報を追加
                    if hasattr(result, 'keyword') and result.keyword:
                        result_dict['keyword'] = result.keyword.keyword
                        result_dict['category'] = result.keyword.category
                    else:
                        # キーワード情報を別途取得
                        keyword = session.query(Keyword).filter(Keyword.id == result.keyword_id).first()
                        if keyword:
                            result_dict['keyword'] = keyword.keyword
                            result_dict['category'] = keyword.category
                        else:
                            logger.warning(f"キーワードID {result.keyword_id} の情報が見つかりません")
                            result_dict['keyword'] = f"ID: {result.keyword_id}"
                            result_dict['category'] = "不明"
                    
                    results.append(result_dict)
                    
            logger.debug(f"変換後の結果数: {len(results)}")
            return results
            
        except Exception as e:
            logger.error(f"データベースからの結果取得中にエラーが発生しました: {e}")
            import traceback
            logger.error(traceback.format_exc())
            return []
    
    def _format_columns(self, df):
        """
        DataFrameの列を整形する
        
        Args:
            df (DataFrame): 整形するDataFrame
            
        Returns:
            DataFrame: 整形されたDataFrame
        """
        # 列名のマッピング（英語→日本語または別の表示名）
        column_mapping = {
            'item_id': '商品ID',
            'title': '商品タイトル',
            'price': '価格',
            'currency': '通貨',
            'shipping_price': '送料',
            'stock_quantity': '在庫数',
            'seller_name': '出品者名',
            'seller_rating': '出品者評価',
            'seller_feedback_count': '評価数',
            'auction_end_time': 'オークション終了時間',
            'listing_type': '出品形式',
            'condition': '商品状態',
            'is_buy_it_now': '即決価格あり',
            'bids_count': '入札数',
            'item_url': '商品URL',
            'image_url': '画像URL',
            'search_timestamp': '検索時刻',
            'keyword_id': 'キーワードID'
        }
        
        # 日付列の整形
        date_columns = ['auction_end_time', 'search_timestamp']
        for col in date_columns:
            if col in df.columns:
                df[col] = pd.to_datetime(df[col]).dt.strftime('%Y-%m-%d %H:%M:%S')
                
        # 列名を変更
        df = df.rename(columns={k: v for k, v in column_mapping.items() if k in df.columns})
        
        return df
    
    def _record_export_history(self, export_type, file_path, record_count):
        """
        エクスポート履歴をデータベースに記録する
        
        Args:
            export_type (str): エクスポート形式
            file_path (str): ファイルパスまたはURL
            record_count (int): エクスポートされたレコード数
        """
        try:
            with self.db.session_scope() as session:
                history = ExportHistory(
                    export_type=export_type,
                    file_path=file_path,
                    record_count=record_count,
                    status='success'
                )
                session.add(history)
                
        except Exception as e:
            logger.error(f"エクスポート履歴の記録中にエラーが発生しました: {e}")
