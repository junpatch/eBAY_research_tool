# キーワード管理サービス

import pandas as pd
import csv
import logging
from pathlib import Path
from googleapiclient.discovery import build
from google_auth_oauthlib.flow import InstalledAppFlow
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
import os.path
import json

logger = logging.getLogger(__name__)

class KeywordManager:
    """
    キーワード管理サービス
    CSV, Excel, Google Spreadsheetsからキーワードをインポート
    """
    
    def __init__(self, database_manager, config_manager):
        """
        キーワード管理サービスの初期化
        
        Args:
            database_manager: データベース管理サービスのインスタンス
            config_manager: 設定管理サービスのインスタンス
        """
        self.db = database_manager
        self.config = config_manager
        
    def import_from_csv(self, file_path, keyword_column="keyword", category_column=None, has_header=True):
        """
        CSVファイルからキーワードをインポート
        
        Args:
            file_path (str): CSVファイルのパス
            keyword_column (str): キーワードが含まれる列名
            category_column (str, optional): カテゴリが含まれる列名（任意）
            has_header (bool): CSVファイルにヘッダー行があるかどうか
            
        Returns:
            int: インポートしたキーワードの数
        """
        file_path = Path(file_path)
        if not file_path.exists():
            logger.error(f"ファイルが見つかりません: {file_path}")
            return 0
            
        try:
            logger.info(f"CSVファイルをインポート: {file_path}")
            
            # pandasを用いてCSVファイルを読み込み
            df = pd.read_csv(file_path, header=0 if has_header else None)
            
            # カラム名を用いてキーワードを取得
            if has_header:
                if keyword_column not in df.columns:
                    logger.error(f"キーワード列名が見つかりません: {keyword_column}")
                    return 0
                keywords = df[keyword_column].tolist()
                categories = df[category_column].tolist() if category_column and category_column in df.columns else None
            else:
                # headerがない場合は列番号を用いてキーワードを取得
                try:
                    keywords = df.iloc[:, int(keyword_column)].tolist()
                    categories = df.iloc[:, int(category_column)].tolist() if category_column is not None else None
                except (IndexError, ValueError):
                    logger.error(f"キーワード列番号が不正です: {keyword_column}")
                    return 0
            
            # TODO: 除外されるとキーワードとカテゴリーの関係性が崩れる可能性がある
            # 空またはNaNのキーワードを除外
            keywords = [k for k in keywords if k and not pd.isna(k)]
            
            # カテゴリーを追加
            keyword_data = []
            if categories:
                for i, keyword in enumerate(keywords):
                    category = categories[i] if i < len(categories) and not pd.isna(categories[i]) else None
                    keyword_data.append((keyword, category))
            else:
                keyword_data = keywords
                
            added_count = self.db.add_keywords_bulk(keyword_data)
            logger.info(f"{added_count} キーワードを追加しました")
            return added_count
            
        except Exception as e:
            logger.error(f"CSVファイルのインポートに失敗しました: {e}")
            return 0
    
    def import_from_excel(self, file_path, sheet_name=0, keyword_column="keyword", category_column=None):
        """
        Excelファイルからキーワードをインポートします
        
        Args:
            file_path (str): Excelファイルのパス
            sheet_name (str or int): シート名またはシート番号
            keyword_column (str): キーワード列名
            category_column (str, optional): カテゴリー列名（任意）
            
        Returns:
            int: 追加されたキーワード数
        """
        file_path = Path(file_path)
        if not file_path.exists():
            logger.error(f"ファイルが見つかりません: {file_path}")
            return 0
            
        try:
            logger.info(f"Excelファイルをインポート: {file_path}")
            
            # pandasを用いてExcelファイルを読み込み
            df = pd.read_excel(file_path, sheet_name=sheet_name)
            
            if keyword_column not in df.columns:
                logger.error(f"キーワード列名が見つかりません: {keyword_column}")
                return 0
                
            keywords = df[keyword_column].tolist()
            categories = df[category_column].tolist() if category_column and category_column in df.columns else None
            
            # 空またはNaNのキーワードを除外
            keywords = [k for k in keywords if k and not pd.isna(k)]
            
            # カテゴリーを追加
            keyword_data = []
            if categories:
                for i, keyword in enumerate(keywords):
                    category = categories[i] if i < len(categories) and not pd.isna(categories[i]) else None
                    keyword_data.append((keyword, category))
            else:
                keyword_data = keywords
                
            added_count = self.db.add_keywords_bulk(keyword_data)
            logger.info(f"{added_count} キーワードを追加しました")
            return added_count
            
        except Exception as e:
            logger.error(f"Excelファイルのインポートに失敗しました: {e}")
            return 0
    
    def import_from_google_sheets(self, spreadsheet_id, range_name, keyword_column="keyword", category_column=None):
        """
        Google Spreadsheetsからキーワードをインポートします
        
        Args:
            spreadsheet_id (str): Google Spreadsheets ID
            range_name (str): シート範囲 (例: 'Sheet1!A1:B100')
            keyword_column (str): キーワード列名
            category_column (str, optional): カテゴリー列名（任意）
            
        Returns:
            int: 追加されたキーワード数
        """
        try:
            logger.info(f"Google Spreadsheetsからキーワードをインポート: {spreadsheet_id}")
            
            # Google Sheets APIを用いて
            credentials_path = self.config.get_from_env(self.config.get(['google_sheets', 'credentials_env']))
            if not credentials_path:
                logger.error("Google Sheets API認証情報が見つかりませんでした")
                return 0
                
            # 認証トークンの保存先
            token_dir = self.config.get_path(['google_sheets', 'token_dir'])
            if token_dir is None:
                token_dir = Path(__file__).parent.parent / 'data' / 'google_token'
                
            token_dir.mkdir(parents=True, exist_ok=True)
            token_path = token_dir / 'token.json'
            
            # Google Sheets APIのスコープ
            scopes = self.config.get(['google_sheets', 'scopes'], ['https://www.googleapis.com/auth/spreadsheets.readonly'])
            
            # 認証トークンの取得
            creds = None
            if os.path.exists(token_path):
                try:
                    creds = Credentials.from_authorized_user_info(
                        json.loads(token_path.read_text()), scopes)
                except Exception as e:
                    logger.warning(f"Google Sheets API認証に失敗しました: {e}")
                    
            # 認証トークンの更新
            if not creds or not creds.valid:
                if creds and creds.expired and creds.refresh_token:
                    creds.refresh(Request())
                else:
                    # 認証トークンの生成
                    flow = InstalledAppFlow.from_client_secrets_file(
                        credentials_path, scopes)
                    creds = flow.run_local_server(port=0)
                    
                # 認証トークンの保存
                token_path.write_text(creds.to_json())
                
            # Google Sheets APIのサービス
            service = build('sheets', 'v4', credentials=creds)
            sheet = service.spreadsheets()
            
            # キーワードを取得
            result = sheet.values().get(spreadsheetId=spreadsheet_id, range=range_name).execute()
            values = result.get('values', [])
            
            if not values:
                logger.warning("Google Spreadsheetsからキーワードを取得できませんでした")
                return 0
                
            # キーワードをDataFrameに変換
            header = values[0]
            data = values[1:] if len(values) > 1 else []
            
            # カンマ区切りのキーワードを展開
            max_cols = max(len(row) for row in values)
            data = [row + [''] * (max_cols - len(row)) for row in data]
            
            df = pd.DataFrame(data, columns=header)
            
            # キーワードを取得
            try:
                if isinstance(keyword_column, int):
                    keywords = df.iloc[:, keyword_column].tolist()
                else:
                    if keyword_column not in df.columns:
                        logger.error(f"キーワード列名が見つかりません: {keyword_column}")
                        return 0
                    keywords = df[keyword_column].tolist()
                    
                if category_column:
                    if isinstance(category_column, int):
                        categories = df.iloc[:, category_column].tolist()
                    else:
                        categories = df[category_column].tolist() if category_column in df.columns else None
                else:
                    categories = None
            except Exception as e:
                logger.error(f"キーワードとカテゴリを取得する際にエラーが発生しました: {e}")
                return 0
                
            # キーワードを重複していませんか
            keywords = [k for k in keywords if k and not pd.isna(k)]
            
            # キーワードとカテゴリを組み立てる
            keyword_data = []
            if categories:
                for i, keyword in enumerate(keywords):
                    category = categories[i] if i < len(categories) and not pd.isna(categories[i]) else None
                    keyword_data.append((keyword, category))
            else:
                keyword_data = keywords
                
            added_count = self.db.add_keywords_bulk(keyword_data)
            logger.info(f"{added_count} キーワードを追加しました")
            return added_count
            
        except Exception as e:
            logger.error(f"Google Sheetsからキーワードを取得する際にエラーが発生しました: {e}")
            return 0
            
    def get_active_keywords(self, limit=None):
        """
        キーワードを取得します
        
        Args:
            limit (int, optional): 取得するキーワードの最大数
            
        Returns:
            list: 取得したキーワードのリスト
        """
        return self.db.get_keywords(status='active', limit=limit)
    
    def mark_keyword_as_processed(self, keyword_id, status='completed'):
        """
        キーワードの状態を更新します
        
        Args:
            keyword_id (int): キーワードID
            status (str): 更新する状態 ('completed', 'failed', 'active')
        """
        with self.db.session_scope() as session:
            keyword = session.query(self.db.models.Keyword).filter(
                self.db.models.Keyword.id == keyword_id).first()
            if keyword:
                keyword.status = status
                keyword.last_searched_at = datetime.utcnow() if status == 'completed' else keyword.last_searched_at
