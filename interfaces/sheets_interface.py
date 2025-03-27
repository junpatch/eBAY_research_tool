# Google Sheetsu3068u306eu30a4u30f3u30bfu30fcu30d5u30a7u30fcu30b9

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
    Google Sheets APIu3092u4f7fu7528u3057u3066u30c7u30fcu30bfu306eu8aadu307fu8fbcu307fu3068u66f8u304du8fbcu307fu3092u884cu3046u30afu30e9u30b9
    """
    
    def __init__(self, config_manager):
        """
        Google Sheetsu30a4u30f3u30bfu30fcu30d5u30a7u30fcu30b9u306eu521du671fu5316
        
        Args:
            config_manager: u8a2du5b9au30deu30cdu30fcu30b8u30e3u30fcu306eu30a4u30f3u30b9u30bfu30f3u30b9
        """
        self.config = config_manager
        self.credentials_path = self.config.get_from_env(self.config.get('google_sheets', 'credentials_env'))
        self.token_dir = self.config.get_path('google_sheets', 'token_dir')
        
        if self.token_dir is None:
            self.token_dir = Path(__file__).parent.parent / 'data' / 'google_token'
            
        self.token_dir.mkdir(parents=True, exist_ok=True)
        self.token_path = self.token_dir / 'token.json'
        
        # APIu30b9u30b3u30fcu30d7
        self.scopes = self.config.get('google_sheets', 'scopes', ['https://www.googleapis.com/auth/spreadsheets'])
        
        # u30b5u30fcu30d3u30b9u30a4u30f3u30b9u30bfu30f3u30b9
        self.service = None
    
    def authenticate(self):
        """
        Google Sheets APIu306bu8a8du8a3cu3059u308b
        
        Returns:
            bool: u8a8du8a3cu306bu6210u529fu3057u305fu304bu3069u3046u304b
        """
        creds = None
        
        if not self.credentials_path:
            logger.error("Google Sheets APIu306eu8a8du8a3cu60c5u5831u304cu8a2du5b9au3055u308cu3066u3044u307eu305bu3093u3002")
            return False
            
        try:
            # u65e2u5b58u306eu30c8u30fcu30afu30f3u304cu3042u308cu3070u8aadu307fu8fbcu307f
            if os.path.exists(self.token_path):
                try:
                    creds = Credentials.from_authorized_user_info(
                        json.loads(self.token_path.read_text()), self.scopes)
                except Exception as e:
                    logger.warning(f"u30c8u30fcu30afu30f3u306eu8aadu307fu8fbcu307fu4e2du306bu30a8u30e9u30fcu304cu767au751fu3057u307eu3057u305f: {e}")
                    
            # u671fu9650u5207u308cu307eu305fu306fu30c8u30fcu30afu30f3u304cu5b58u5728u3057u306au3044u5834u5408
            if not creds or not creds.valid:
                if creds and creds.expired and creds.refresh_token:
                    creds.refresh(Request())
                else:
                    # u65b0u305fu306bu8a8du8a3cu3092u5b9fu884c
                    flow = InstalledAppFlow.from_client_secrets_file(
                        self.credentials_path, self.scopes)
                    creds = flow.run_local_server(port=0)
                    
                # u30c8u30fcu30afu30f3u3092u4fddu5b58
                self.token_path.write_text(creds.to_json())
                
            # APIu30b5u30fcu30d3u30b9u3092u69cbu7bc9
            self.service = build('sheets', 'v4', credentials=creds)
            return True
            
        except Exception as e:
            logger.error(f"Google Sheets APIu8a8du8a3cu30a8u30e9u30fc: {e}")
            return False
    
    def read_spreadsheet(self, spreadsheet_id, range_name):
        """
        u30b9u30d7u30ecu30c3u30c9u30b7u30fcu30c8u304bu3089u30c7u30fcu30bfu3092u8aadu307fu8fbcu3080
        
        Args:
            spreadsheet_id (str): Google Spreadsheet ID
            range_name (str): u8aadu307fu8fbcu3080u7bc4u56f2uff08u4f8b: 'Sheet1!A1:C10'uff09
            
        Returns:
            list: 2u6b21u5143u914du5217u306eu8aadu307fu8fbcu307fu7d50u679cu3001u307eu305fu306fu30a8u30e9u30fcu6642u306fNone
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
            logger.error(f"Google Sheetsu304bu3089u306eu8aadu307fu8fbcu307fu4e2du306bu30a8u30e9u30fcu304cu767au751fu3057u307eu3057u305f: {error}")
            return None
    
    def write_to_spreadsheet(self, spreadsheet_id, range_name, values):
        """
        u30b9u30d7u30ecu30c3u30c9u30b7u30fcu30c8u306bu30c7u30fcu30bfu3092u66f8u304du8fbcu3080
        
        Args:
            spreadsheet_id (str): Google Spreadsheet ID
            range_name (str): u66f8u304du8fbcu3080u7bc4u56f2uff08u4f8b: 'Sheet1!A1'uff09
            values (list): 2u6b21u5143u914du5217u306eu66f8u304du8fbcu307fu30c7u30fcu30bf
            
        Returns:
            dict: APIu30ecu30b9u30ddu30f3u30b9u7d50u679cu3001u307eu305fu306fu30a8u30e9u30fcu6642u306fNone
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
            logger.error(f"Google Sheetsu3078u306eu66f8u304du8fbcu307fu4e2du306bu30a8u30e9u30fcu304cu767au751fu3057u307eu3057u305f: {error}")
            return None
    
    def create_spreadsheet(self, title, sheet_names=None):
        """
        u65b0u3057u3044u30b9u30d7u30ecu30c3u30c9u30b7u30fcu30c8u3092u4f5cu6210u3059u308b
        
        Args:
            title (str): u30b9u30d7u30ecu30c3u30c9u30b7u30fcu30c8u306eu30bfu30a4u30c8u30eb
            sheet_names (list, optional): u4f5cu6210u3059u308bu30b7u30fcu30c8u540du306eu30eau30b9u30c8
            
        Returns:
            str: u4f5cu6210u3055u308cu305fu30b9u30d7u30ecu30c3u30c9u30b7u30fcu30c8u306eIDu3001u307eu305fu306fu30a8u30e9u30fcu6642u306fNone
        """
        if not self.service:
            if not self.authenticate():
                return None
                
        try:
            # u30b7u30fcu30c8u60c5u5831u306eu4f5cu6210
            sheets = []
            if sheet_names:
                for name in sheet_names:
                    sheets.append({'properties': {'title': name}})
            else:
                # u30c7u30d5u30a9u30ebu30c8u30b7u30fcu30c8
                sheets.append({'properties': {'title': 'Sheet1'}})
                
            spreadsheet = {
                'properties': {'title': title},
                'sheets': sheets
            }
            
            # u65b0u898fu30b9u30d7u30ecu30c3u30c9u30b7u30fcu30c8u306eu4f5cu6210
            result = self.service.spreadsheets().create(body=spreadsheet).execute()
            return result['spreadsheetId']
            
        except HttpError as error:
            logger.error(f"u30b9u30d7u30ecu30c3u30c9u30b7u30fcu30c8u306eu4f5cu6210u4e2du306bu30a8u30e9u30fcu304cu767au751fu3057u307eu3057u305f: {error}")
            return None
    
    def clear_range(self, spreadsheet_id, range_name):
        """
        u6307u5b9au3057u305fu7bc4u56f2u306eu30c7u30fcu30bfu3092u30afu30eau30a2u3059u308b
        
        Args:
            spreadsheet_id (str): Google Spreadsheet ID
            range_name (str): u30afu30eau30a2u3059u308bu7bc4u56f2uff08u4f8b: 'Sheet1!A1:Z1000'uff09
            
        Returns:
            dict: APIu30ecu30b9u30ddu30f3u30b9u7d50u679cu3001u307eu305fu306fu30a8u30e9u30fcu6642u306fNone
        """
        if not self.service:
            if not self.authenticate():
                return None
                
        try:
            result = self.service.spreadsheets().values().clear(
                spreadsheetId=spreadsheet_id, range=range_name).execute()
            return result
            
        except HttpError as error:
            logger.error(f"u30c7u30fcu30bfu306eu30afu30eau30a2u4e2du306bu30a8u30e9u30fcu304cu767au751fu3057u307eu3057u305f: {error}")
            return None
    
    def get_spreadsheet_info(self, spreadsheet_id):
        """
        u30b9u30d7u30ecu30c3u30c9u30b7u30fcu30c8u306eu60c5u5831u3092u53d6u5f97u3059u308b
        
        Args:
            spreadsheet_id (str): Google Spreadsheet ID
            
        Returns:
            dict: u30b9u30d7u30ecu30c3u30c9u30b7u30fcu30c8u306eu60c5u5831u3001u307eu305fu306fu30a8u30e9u30fcu6642u306fNone
        """
        if not self.service:
            if not self.authenticate():
                return None
                
        try:
            spreadsheet = self.service.spreadsheets().get(spreadsheetId=spreadsheet_id).execute()
            return spreadsheet
            
        except HttpError as error:
            logger.error(f"u30b9u30d7u30ecu30c3u30c9u30b7u30fcu30c8u60c5u5831u306eu53d6u5f97u4e2du306bu30a8u30e9u30fcu304cu767au751fu3057u307eu3057u305f: {error}")
            return None
    
    def add_sheet(self, spreadsheet_id, sheet_name):
        """
        u65b0u3057u3044u30b7u30fcu30c8u3092u8ffdu52a0u3059u308b
        
        Args:
            spreadsheet_id (str): Google Spreadsheet ID
            sheet_name (str): u65b0u3057u3044u30b7u30fcu30c8u306eu540du524d
            
        Returns:
            dict: APIu30ecu30b9u30ddu30f3u30b9u7d50u679cu3001u307eu305fu306fu30a8u30e9u30fcu6642u306fNone
        """
        if not self.service:
            if not self.authenticate():
                return None
                
        try:
            # u73feu5728u306eu30b7u30fcu30c8u540du3092u78bau8a8du3057u3001u540cu540du306eu30b7u30fcu30c8u304cu3042u308cu3070u30b9u30adu30c3u30d7
            spreadsheet_info = self.get_spreadsheet_info(spreadsheet_id)
            if spreadsheet_info:
                for sheet in spreadsheet_info.get('sheets', []):
                    if sheet['properties']['title'] == sheet_name:
                        logger.info(f"u30b7u30fcu30c8 '{sheet_name}' u306fu3059u3067u306bu5b58u5728u3057u307eu3059u3002")
                        return None
                        
            # u65b0u3057u3044u30b7u30fcu30c8u3092u8ffdu52a0
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
            logger.error(f"u30b7u30fcu30c8u306eu8ffdu52a0u4e2du306bu30a8u30e9u30fcu304cu767au751fu3057u307eu3057u305f: {error}")
            return None
