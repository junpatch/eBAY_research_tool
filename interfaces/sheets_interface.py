# Google Sheets

import os
import logging
import json
from pathlib import Path
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from google.auth.transport.requests import Request
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError

logger = logging.getLogger(__name__)

class GoogleSheetsInterface:
    """
    Google Sheets API
    """
    
    def __init__(self, config_manager):
        """
        Google Sheets API
        
        Args:
            config_manager: 設定管理サービスのインスタンス
        """
        self.config = config_manager
        self.credentials_path = self.config.get_from_env(self.config.get('google_sheets', 'credentials_env'))
        self.token_dir = self.config.get_path('google_sheets', 'token_dir')
        
        if self.token_dir is None:
            self.token_dir = Path(__file__).parent.parent / 'data' / 'google_token'
            
        self.token_dir.mkdir(parents=True, exist_ok=True)
        self.token_path = self.token_dir / 'token.json'
        
        # APIスコープ
        self.scopes = self.config.get('google_sheets', 'scopes', ['https://www.googleapis.com/auth/spreadsheets'])
        
        # APIサービス
        self.service = None
    
    def authenticate(self):
        """
        Google Sheets API認証
        
        Returns:
            bool: 認証成功/失敗
        """
        creds = None
        
        if not self.credentials_path:
            logger.error("Google Sheets API認証に必要なクレデンシャルが設定されていません。")
            return False
            
        try:
            # 既存のトークンの復元
            if os.path.exists(self.token_path):
                try:
                    creds = Credentials.from_authorized_user_info(
                        json.loads(self.token_path.read_text()), self.scopes)
                except Exception as e:
                    logger.warning(f"トークンの復元に失敗しました: {e}")
                    
            # トークンの存在チェック
            if not creds or not creds.valid:
                if creds and creds.expired and creds.refresh_token:
                    creds.refresh(Request())
                else:
                    # 新しいトークンの生成
                    flow = InstalledAppFlow.from_client_secrets_file(
                        self.credentials_path, self.scopes)
                    creds = flow.run_local_server(port=0)
                    
                # トークンの保存
                self.token_path.write_text(creds.to_json())
                
            # APIサービスの初期化
            self.service = build('sheets', 'v4', credentials=creds)
            return True
            
        except Exception as e:
            logger.error(f"Google Sheets API認証に失敗しました: {e}")
            return False
    
    def read_spreadsheet(self, spreadsheet_id, range_name):
        """
        Google Spreadsheetからデータを読み込みます
        
        Args:
            spreadsheet_id (str): Google Spreadsheet ID
            range_name (str): 読み込む範囲 (例: 'Sheet1!A1:C10')
            
        Returns:
            list: 2次元配列
        """
        if not self.service:
            if not self.authenticate():
                return None
                
        try:
            result = self.service.spreadsheets().values().get(
                spreadsheetId=spreadsheet_id, range=range_name).execute()
            values = result.get('values', [])
            return values
            
        except HttpError as error:
            logger.error(f"Google Sheets認証に失敗しました: {error}")
            return None
    
    def write_to_spreadsheet(self, spreadsheet_id, range_name, values):
        """
        Google Spreadsheetにデータを書き込みます
        
        Args:
            spreadsheet_id (str): Google Spreadsheet ID
            range_name (str): 書き込む範囲 (例: 'Sheet1!A1')
            values (list): 書き込む値
            
        Returns:
            dict: APIレスポンス
        """
        if not self.service:
            if not self.authenticate():
                return None
                
        try:
            body = {'values': values}
            result = self.service.spreadsheets().values().update(
                spreadsheetId=spreadsheet_id, range=range_name,
                valueInputOption='RAW', body=body).execute()
            return result
            
        except HttpError as error:
            logger.error(f"Google Sheets認証に失敗しました: {error}")
            return None
    
    def create_spreadsheet(self, title, sheet_names=None):
        """
        新しいGoogle Spreadsheetを作成します
        
        Args:
            title (str): Spreadsheetのタイトル
            sheet_names (list, optional): Spreadsheetのシート名一覧
            
        Returns:
            str: 新しいSpreadsheetのID
        """
        if not self.service:
            if not self.authenticate():
                return None
                
        try:
            # 新しいSpreadsheetの作成
            sheets = []
            if sheet_names:
                for name in sheet_names:
                    sheets.append({'properties': {'title': name}})
            else:
                # 新しいシート
                sheets.append({'properties': {'title': 'Sheet1'}})
                
            spreadsheet = {
                'properties': {'title': title},
                'sheets': sheets
            }
            
            # 新しいSpreadsheetの作成
            result = self.service.spreadsheets().create(body=spreadsheet).execute()
            return result['spreadsheetId']
            
        except HttpError as error:
            logger.error(f"Google Spreadsheetの作成に失敗しました: {error}")
            return None
    
    def clear_range(self, spreadsheet_id, range_name):
        """
        指定範囲をクリアします
        
        Args:
            spreadsheet_id (str): Google Spreadsheet ID
            range_name (str): 清除する範囲 (例: 'Sheet1!A1:Z1000')
            
        Returns:
            dict: APIレスポンス
        """
        if not self.service:
            if not self.authenticate():
                return None
                
        try:
            result = self.service.spreadsheets().values().clear(
                spreadsheetId=spreadsheet_id, range=range_name).execute()
            return result
            
        except HttpError as error:
            logger.error(f"Google Spreadsheetの範囲クリアに失敗しました: {error}")
            return None
    
    def get_spreadsheet_info(self, spreadsheet_id):
        """
        Google Spreadsheetの情報を取得します
        
        Args:
            spreadsheet_id (str): Google Spreadsheet ID
            
        Returns:
            dict: Spreadsheetの情報
        """
        if not self.service:
            if not self.authenticate():
                return None
                
        try:
            spreadsheet = self.service.spreadsheets().get(spreadsheetId=spreadsheet_id).execute()
            return spreadsheet
            
        except HttpError as error:
            logger.error(f"Google Spreadsheetの情報取得に失敗しました: {error}")
            return None
    
    def add_sheet(self, spreadsheet_id, sheet_name):
        """
        新しいシートを追加します
        
        Args:
            spreadsheet_id (str): Google Spreadsheet ID
            sheet_name (str): 新しいシートの名前
            
        Returns:
            dict: APIレスポンス
        """
        if not self.service:
            if not self.authenticate():
                return None
                
        try:
            # シートが既に存在する場合はスキップ
            spreadsheet_info = self.get_spreadsheet_info(spreadsheet_id)
            if spreadsheet_info:
                for sheet in spreadsheet_info.get('sheets', []):
                    if sheet['properties']['title'] == sheet_name:
                        logger.info(f"シート '{sheet_name}' は既に存在します。")
                        return None
                        
            # 新しいシートを追加
            request = {
                'requests': [{
                    'addSheet': {
                        'properties': {'title': sheet_name}
                    }
                }]
            }
            
            result = self.service.spreadsheets().batchUpdate(
                spreadsheetId=spreadsheet_id, body=request).execute()
            return result
            
        except HttpError as error:
            logger.error(f"Google Spreadsheetの範囲クリアに失敗しました: {error}")
            return None
