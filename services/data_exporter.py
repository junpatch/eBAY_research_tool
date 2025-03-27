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
        self.output_dir = self.config.get_path('export', 'output_dir')
        if self.output_dir is None:
            self.output_dir = Path(__file__).parent.parent / 'data' / 'exports'
            
        # 出力ディレクトリが存在しない場合は作成
        self.output_dir.mkdir(parents=True, exist_ok=True)
        
        # デフォルトの出力形式
        self.default_format = self.config.get('export', 'default_format', 'csv')
        
        # Google Spreadsheetの設定
        self.spreadsheet_id = self.config.get('export', 'google_spreadsheet_id', '')
        
    def export_results(self, results=None, keyword_id=None, job_id=None, format=None, file_path=None):
        """
        検索結果をエクスポートする
        
        Args:
            results (list, optional): エクスポートする結果のリスト。指定がなければDBから取得。
            keyword_id (int, optional): 特定のキーワードIDの結果をエクスポートする場合に指定
            job_id (int, optional): 特定のジョブIDの結果をエクスポートする場合に指定
            format (str, optional): 出力形式（csv, excel, google_sheets）
            file_path (str, optional): 出力ファイルパス
            
        Returns:
            str: エクスポートされたファイルのパス、またはGoogle SheetのURL
        """
        # 出力形式が指定されていない場合はデフォルトを使用
        if format is None:
            format = self.default_format
        
        # 結果が指定されておらず、キーワードIDまたはジョブIDが指定されている場合はDBから取得
        if results is None and (keyword_id or job_id):
            results = self._get_results_from_db(keyword_id, job_id)
            
        if not results:
            logger.warning("エクスポートする結果がありません。")
            return None
            
        # DataFrame作成
        df = pd.DataFrame(results)
        
        # 列名の日本語化または整形（必要に応じて）
        df = self._format_columns(df)
        
        # 出力ファイルパスが指定されていない場合は自動生成
        if file_path is None:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            
            if keyword_id:
                filename = f"ebay_results_keyword_{keyword_id}_{timestamp}"
            elif job_id:
                filename = f"ebay_results_job_{job_id}_{timestamp}"
            else:
                filename = f"ebay_results_{timestamp}"
                
            if format.lower() == 'csv':
                file_path = self.output_dir / f"{filename}.csv"
            elif format.lower() == 'excel':
                file_path = self.output_dir / f"{filename}.xlsx"
                
        # 形式に応じてエクスポート
        if format.lower() == 'csv':
            return self.export_to_csv(df, file_path)
        elif format.lower() == 'excel':
            return self.export_to_excel(df, file_path)
        elif format.lower() == 'google_sheets':
            return self.export_to_google_sheets(df, self.spreadsheet_id)
        else:
            logger.error(f"サポートされていない形式です: {format}")
            return None
    
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
                
            # 出力ファイルパスの設定
            if file_path is None:
                timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                file_path = self.output_dir / f"ebay_results_{timestamp}.csv"
            else:
                file_path = Path(file_path)
                
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
                
            # 出力ファイルパスの設定
            if file_path is None:
                timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                file_path = self.output_dir / f"ebay_results_{timestamp}.xlsx"
            else:
                file_path = Path(file_path)
                
            # Excelに出力
            writer = pd.ExcelWriter(file_path, engine='openpyxl')
            data.to_excel(writer, sheet_name='eBay検索結果', index=False)
            
            # 列幅の自動調整
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
    
    def export_to_google_sheets(self, data, spreadsheet_id=None, sheet_name=None):
        """
        データをGoogle Sheetsにエクスポートする
        
        Args:
            data: DataFrameまたはリスト
            spreadsheet_id (str, optional): Google SpreadsheetのID
            sheet_name (str, optional): シート名
            
        Returns:
            str: スプレッドシートのURL
        """
        try:
            # DataFrameでない場合はDataFrameに変換
            if not isinstance(data, pd.DataFrame):
                data = pd.DataFrame(data)
                
            # Google Sheets API認証を準備
            credentials_path = self.config.get_from_env(self.config.get('google_sheets', 'credentials_env'))
            if not credentials_path:
                logger.error("Google Sheets APIの認証情報が設定されていません。")
                return None
                
            # トークンディレクトリ
            token_dir = self.config.get_path('google_sheets', 'token_dir')
            if token_dir is None:
                token_dir = Path(__file__).parent.parent / 'data' / 'google_token'
                
            token_dir.mkdir(parents=True, exist_ok=True)
            token_path = token_dir / 'token.json'
            
            # APIスコープ
            scopes = self.config.get('google_sheets', 'scopes', ['https://www.googleapis.com/auth/spreadsheets'])
            
            # 認証処理
            creds = None
            if os.path.exists(token_path):
                try:
                    creds = Credentials.from_authorized_user_info(
                        json.loads(token_path.read_text()), scopes)
                except Exception as e:
                    logger.warning(f"トークンの読み込み中にエラーが発生しました: {e}")
                    
            # 期限切れまたはトークンが存在しない場合
            if not creds or not creds.valid:
                if creds and creds.expired and creds.refresh_token:
                    creds.refresh(Request())
                else:
                    # 新たに認証を実行
                    flow = InstalledAppFlow.from_client_secrets_file(
                        credentials_path, scopes)
                    creds = flow.run_local_server(port=0)
                    
                # トークンを保存
                token_path.write_text(creds.to_json())
                
            # Google Sheets APIサービスを準備
            service = build('sheets', 'v4', credentials=creds)
            
            # スプレッドシートIDが指定されていない場合は新規作成
            if not spreadsheet_id:
                if not self.spreadsheet_id:
                    # 新規スプレッドシート作成
                    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                    spreadsheet = service.spreadsheets().create(
                        body={
                            'properties': {'title': f'eBay Research Results - {timestamp}'},
                            'sheets': [{'properties': {'title': sheet_name or 'eBay検索結果'}}]
                        }
                    ).execute()
                    spreadsheet_id = spreadsheet['spreadsheetId']
                    logger.info(f"新しいスプレッドシートを作成しました: {spreadsheet_id}")
                else:
                    spreadsheet_id = self.spreadsheet_id
            
            # シート名が指定されていない場合はデフォルト名
            if not sheet_name:
                sheet_name = 'eBay検索結果'
                
            # シートが存在するか確認し、なければ作成
            spreadsheet = service.spreadsheets().get(spreadsheetId=spreadsheet_id).execute()
            sheets = spreadsheet.get('sheets', [])
            sheet_exists = False
            
            for sheet in sheets:
                if sheet['properties']['title'] == sheet_name:
                    sheet_exists = True
                    break
                    
            if not sheet_exists:
                # 新しいシートを追加
                request = service.spreadsheets().batchUpdate(
                    spreadsheetId=spreadsheet_id,
                    body={
                        'requests': [{
                            'addSheet': {
                                'properties': {'title': sheet_name}
                            }
                        }]
                    }
                ).execute()
            
            # データの整形（日付型やNoneの処理）
            data_values = data.fillna('').astype(str).values.tolist()
            header_values = data.columns.tolist()
            
            # まずシートをクリア
            service.spreadsheets().values().clear(
                spreadsheetId=spreadsheet_id,
                range=f"{sheet_name}!A1:Z50000"
            ).execute()
            
            # ヘッダーとデータを書き込み
            values = [header_values] + data_values
            body = {'values': values}
            
            result = service.spreadsheets().values().update(
                spreadsheetId=spreadsheet_id,
                range=f"{sheet_name}!A1",
                valueInputOption='RAW',
                body=body
            ).execute()
            
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
                query = session.query(self.db.models.EbaySearchResult)
                
                if keyword_id:
                    query = query.filter(self.db.models.EbaySearchResult.keyword_id == keyword_id)
                    
                # ジョブIDの場合は、そのジョブで処理されたキーワードIDを特定する必要がある
                # 実装例：この部分は実際のデータベーススキーマに応じて調整が必要
                
                # 結果を辞書のリストに変換
                for result in query.all():
                    result_dict = {}
                    for column in result.__table__.columns:
                        result_dict[column.name] = getattr(result, column.name)
                    results.append(result_dict)
                    
            return results
            
        except Exception as e:
            logger.error(f"データベースからの結果取得中にエラーが発生しました: {e}")
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
                history = self.db.models.ExportHistory(
                    export_type=export_type,
                    file_path=file_path,
                    record_count=record_count,
                    status='success'
                )
                session.add(history)
                
        except Exception as e:
            logger.error(f"エクスポート履歴の記録中にエラーが発生しました: {e}")
