# u30adu30fcu30efu30fcu30c9u7ba1u7406u30afu30e9u30b9

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
    u691cu7d22u30adu30fcu30efu30fcu30c9u306eu7ba1u7406u3092u884cu3046u30afu30e9u30b9
    CSV, Excelu30d5u30a1u30a4u30eb, Google Spreadsheetsu304bu3089u306eu30adu30fcu30efu30fcu30c9u53d6u5f97u3092u30b5u30ddu30fcu30c8
    """
    
    def __init__(self, database_manager, config_manager):
        """
        u30adu30fcu30efu30fcu30c9u30deu30cdu30fcu30b8u30e3u30fcu306eu521du671fu5316
        
        Args:
            database_manager: u30c7u30fcu30bfu30d9u30fcu30b9u30deu30cdu30fcu30b8u30e3u30fcinstanceu
            config_manager: u8a2du5b9au30deu30cdu30fcu30b8u30e3u30fcinstance
        """
        self.db = database_manager
        self.config = config_manager
        
    def import_from_csv(self, file_path, keyword_column="keyword", category_column=None, has_header=True):
        """
        CSVu30d5u30a1u30a4u30ebu304bu3089u30adu30fcu30efu30fcu30c9u3092u30a4u30f3u30ddu30fcu30c8u3059u308b
        
        Args:
            file_path (str): CSVu30d5u30a1u30a4u30ebu30d1u30b9
            keyword_column (str): u30adu30fcu30efu30fcu30c9u304cu683cu7d0du3055u308cu3066u3044u308bu30abu30e9u30e0u540du307eu305fu306fu30a4u30f3u30c7u30c3u30afu30b9
            category_column (str, optional): u30abu30c6u30b4u30eau304cu683cu7d0du3055u308cu3066u3044u308bu30abu30e9u30e0u540du307eu305fu306fu30a4u30f3u30c7u30c3u30afu30b9
            has_header (bool): CSVu30d5u30a1u30a4u30ebu306bu30d8u30c3u30c0u30fcu884cu304cu3042u308bu304bu3069u3046u304b
            
        Returns:
            int: u8ffdu52a0u3055u308cu305fu30adu30fcu30efu30fcu30c9u306eu6570
        """
        file_path = Path(file_path)
        if not file_path.exists():
            logger.error(f"u30d5u30a1u30a4u30ebu304cu898bu3064u304bu308au307eu305bu3093: {file_path}")
            return 0
            
        try:
            logger.info(f"CSVu30d5u30a1u30a4u30ebu304bu3089u30adu30fcu30efu30fcu30c9u3092u8aadu307fu8fcmu3093u3067u3044u307eu3059: {file_path}")
            
            # pandasu3092u4f7fu7528u3057u3066CSVu30d5u30a1u30a4u30ebu3092u8aadu307fu8fbcu3080
            df = pd.read_csv(file_path, header=0 if has_header else None)
            
            # u5217u540du307eu305fu306fu30a4u30f3u30c7u30c3u30afu30b9u3067u30c7u30fcu30bfu3092u53d6u5f97
            if has_header:
                if keyword_column not in df.columns:
                    logger.error(f"u6307u5b9au3055u308cu305fu5217u540du304cu898bu3064u304bu308au307eu305bu3093: {keyword_column}")
                    return 0
                keywords = df[keyword_column].tolist()
                categories = df[category_column].tolist() if category_column and category_column in df.columns else None
            else:
                # headeru304cu306au3044u5834u5408u306fu30a4u30f3u30c7u30c3u30afu30b9u3067u5217u3092u6307u5b9a
                try:
                    keywords = df.iloc[:, int(keyword_column)].tolist()
                    categories = df.iloc[:, int(category_column)].tolist() if category_column is not None else None
                except (IndexError, ValueError):
                    logger.error(f"u7121u52b9u306au5217u30a4u30f3u30c7u30c3u30afu30b9: {keyword_column}")
                    return 0
            
            # u7a7au306eu30adu30fcu30efu30fcu30c9u3092u9664u5916
            keywords = [k for k in keywords if k and not pd.isna(k)]
            
            # u30c7u30fcu30bfu30d9u30fcu30b9u306bu4e00u62ecu8ffdu52a0
            keyword_data = []
            if categories:
                for i, keyword in enumerate(keywords):
                    category = categories[i] if i < len(categories) and not pd.isna(categories[i]) else None
                    keyword_data.append((keyword, category))
            else:
                keyword_data = keywords
                
            added_count = self.db.add_keywords_bulk(keyword_data)
            logger.info(f"{added_count} u500bu306eu30adu30fcu30efu30fcu30c9u3092u8ffdu52a0u3057u307eu3057u305f")
            return added_count
            
        except Exception as e:
            logger.error(f"CSVu30d5u30a1u30a4u30ebu306eu8aadu307fu8fcbu307fu4e2du306bu30a8u30e9u30fcu304cu767au751fu3057u307eu3057u305f: {e}")
            return 0
    
    def import_from_excel(self, file_path, sheet_name=0, keyword_column="keyword", category_column=None):
        """
        Excelu30d5u30a1u30a4u30ebu304bu3089u30adu30fcu30efu30fcu30c9u3092u30a4u30f3u30ddu30fcu30c8u3059u308b
        
        Args:
            file_path (str): Excelu30d5u30a1u30a4u30ebu30d1u30b9
            sheet_name (str or int): u30b7u30fcu30c8u540du307eu305fu306fu30a4u30f3u30c7u30c3u30afu30b9
            keyword_column (str): u30adu30fcu30efu30fcu30c9u304cu683cu7d0du3055u308cu3066u3044u308bu30abu30e9u30e0u540d
            category_column (str, optional): u30abu30c6u30b4u30eau304cu683cu7d0du3055u308cu3066u3044u308bu30abu30e9u30e0u540d
            
        Returns:
            int: u8ffdu52a0u3055u308cu305fu30adu30fcu30efu30fcu30c9u306eu6570
        """
        file_path = Path(file_path)
        if not file_path.exists():
            logger.error(f"u30d5u30a1u30a4u30ebu304cu898bu3064u304bu308au307eu305bu3093: {file_path}")
            return 0
            
        try:
            logger.info(f"Excelu30d5u30a1u30a4u30ebu304bu3089u30adu30fcu30efu30fcu30c9u3092u8aadu307fu8fcmu3093u3067u3044u307eu3059: {file_path}")
            
            # pandasu3092u4f7fu7528u3057u3066Excelu30d5u30a1u30a4u30ebu3092u8aadu307fu8fbcu3080
            df = pd.read_excel(file_path, sheet_name=sheet_name)
            
            if keyword_column not in df.columns:
                logger.error(f"u6307u5b9au3055u308cu305fu5217u540du304cu898bu3064u304bu308au307eu305bu3093: {keyword_column}")
                return 0
                
            keywords = df[keyword_column].tolist()
            categories = df[category_column].tolist() if category_column and category_column in df.columns else None
            
            # u7a7au306eu30adu30fcu30efu30fcu30c9u3092u9664u5916
            keywords = [k for k in keywords if k and not pd.isna(k)]
            
            # u30c7u30fcu30bfu30d9u30fcu30b9u306bu4e00u62ecu8ffdu52a0
            keyword_data = []
            if categories:
                for i, keyword in enumerate(keywords):
                    category = categories[i] if i < len(categories) and not pd.isna(categories[i]) else None
                    keyword_data.append((keyword, category))
            else:
                keyword_data = keywords
                
            added_count = self.db.add_keywords_bulk(keyword_data)
            logger.info(f"{added_count} u500bu306eu30adu30fcu30efu30fcu30c9u3092u8ffdu52a0u3057u307eu3057u305f")
            return added_count
            
        except Exception as e:
            logger.error(f"Excelu30d5u30a1u30a4u30ebu306eu8aadu307fu8fcbu307fu4e2du306bu30a8u30e9u30fcu304cu767au751fu3057u307eu3057u305f: {e}")
            return 0
    
    def import_from_google_sheets(self, spreadsheet_id, range_name, keyword_column="keyword", category_column=None):
        """
        Google Spreadsheetsu304bu3089u30adu30fcu30efu30fcu30c9u3092u30a4u30f3u30ddu30fcu30c8u3059u308b
        
        Args:
            spreadsheet_id (str): Google Spreadsheets ID
            range_name (str): u30c7u30fcu30bfu5bfeu8c61u7bc4u56f2uff08u4f8b: 'Sheet1!A1:B100'uff09
            keyword_column (str): u30adu30fcu30efu30fcu30c9u304cu683cu7d0du3055u308cu3066u3044u308bu30abu30e9u30e0u540du307eu305fu306fu30a4u30f3u30c7u30c3u30afu30b9
            category_column (str, optional): u30abu30c6u30b4u30eau304cu683cu7d0du3055u308cu3066u3044u308bu30abu30e9u30e0u540du307eu305fu306fu30a4u30f3u30c7u30c3u30afu30b9
            
        Returns:
            int: u8ffdu52a0u3055u308cu305fu30adu30fcu30efu30fcu30c9u306eu6500
        """
        try:
            logger.info(f"Google Spreadsheetsu304bu3089u30adu30fcu30efu30fcu30c9u3092u8aadu307fu8fcmu3093u3067u3044u307eu3059: {spreadsheet_id}")
            
            # Google Sheets APIu8a8du8a3cu3092u6e96u5099
            credentials_path = self.config.get_from_env(self.config.get('google_sheets', 'credentials_env'))
            if not credentials_path:
                logger.error("Google Sheets APIu306eu8a8du8a3cu60c5u5831u304cu8a2du5b9au3055u308cu3066u3044u307eu305bu3093u3002")
                return 0
                
            # u30c8u30fcu30afu30f3u30c7u30a3u30ecu30afu30c8u30ea
            token_dir = self.config.get_path('google_sheets', 'token_dir')
            if token_dir is None:
                token_dir = Path(__file__).parent.parent / 'data' / 'google_token'
                
            token_dir.mkdir(parents=True, exist_ok=True)
            token_path = token_dir / 'token.json'
            
            # APIu30b9u30b3u30fcu30d7
            scopes = self.config.get('google_sheets', 'scopes', ['https://www.googleapis.com/auth/spreadsheets.readonly'])
            
            # u8a8du8a3cu51e6u7406
            creds = None
            if os.path.exists(token_path):
                try:
                    creds = Credentials.from_authorized_user_info(
                        json.loads(token_path.read_text()), scopes)
                except Exception as e:
                    logger.warning(f"u30c8u30fcu30afu30f3u306eu8aadu307fu8fbcu307fu4e2du306bu30a8u30e9u30fcu304cu767au751fu3057u307eu3057u305f: {e}")
                    
            # u671fu9650u5207u308cu307eu305fu306fu30c8u30fcu30afu30f3u304cu5b58u5728u3057u306au3044u5834u5408
            if not creds or not creds.valid:
                if creds and creds.expired and creds.refresh_token:
                    creds.refresh(Request())
                else:
                    # u65b0u305fu306bu8a8du8a3cu3092u5b9fu884c
                    flow = InstalledAppFlow.from_client_secrets_file(
                        credentials_path, scopes)
                    creds = flow.run_local_server(port=0)
                    
                # u30c8u30fcu30afu30f3u3092u4fddu5b58
                token_path.write_text(creds.to_json())
                
            # Google Sheets APIu30b5u30fcu30d3u30b9u3092u6e96u5099
            service = build('sheets', 'v4', credentials=creds)
            sheet = service.spreadsheets()
            
            # u30c7u30fcu30bfu306eu53d6u5f97
            result = sheet.values().get(spreadsheetId=spreadsheet_id, range=range_name).execute()
            values = result.get('values', [])
            
            if not values:
                logger.warning("u30c7u30fcu30bfu304cu898bu3064u304bu308au307eu305bu3093u3067u3057u305fu3002")
                return 0
                
            # u30c7u30fcu30bfu3092DataFrameu306bu5909u63db
            header = values[0]
            data = values[1:] if len(values) > 1 else []
            
            # u7a7au306eu5217u3092u8ffdu52a0u3057u3066u3059u3079u3066u306eu884cu304cu540cu3058u9577u3055u306bu306au308bu3088u3046u306bu3059u308b
            max_cols = max(len(row) for row in values)
            data = [row + [''] * (max_cols - len(row)) for row in data]
            
            df = pd.DataFrame(data, columns=header)
            
            # u5217u540du307eu305fu306fu30a4u30f3u30c7u30c3u30afu30b9u3067u30c7u30fcu30bfu3092u53d6u5f97
            try:
                if isinstance(keyword_column, int):
                    keywords = df.iloc[:, keyword_column].tolist()
                else:
                    if keyword_column not in df.columns:
                        logger.error(f"u6307u5b9au3055u308cu305fu5217u540du304cu898bu3064u304bu308au307eu305bu3093: {keyword_column}")
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
                logger.error(f"u5217u30c7u30fcu30bfu306eu53d6u5f97u4e2du306bu30a8u30e9u30fcu304cu767au751fu3057u307eu3057u305f: {e}")
                return 0
                
            # u7a7au306eu30adu30fcu30efu30fcu30c9u3092u9664u5916
            keywords = [k for k in keywords if k and not pd.isna(k)]
            
            # u30c7u30fcu30bfu30d9u30fcu30b9u306bu4e00u62ecu8ffdu52a0
            keyword_data = []
            if categories:
                for i, keyword in enumerate(keywords):
                    category = categories[i] if i < len(categories) and not pd.isna(categories[i]) else None
                    keyword_data.append((keyword, category))
            else:
                keyword_data = keywords
                
            added_count = self.db.add_keywords_bulk(keyword_data)
            logger.info(f"{added_count} u500bu306eu30adu30fcu30efu30fcu30c9u3092u8ffdu52a0u3057u307eu3057u305f")
            return added_count
            
        except Exception as e:
            logger.error(f"Google Sheetsu304bu3089u306eu30c7u30fcu30bfu53d6u5f97u4e2du306bu30a8u30e9u30fcu304cu767au751fu3057u307eu3057u305f: {e}")
            return 0
            
    def get_active_keywords(self, limit=None):
        """
        u30a2u30afu30c6u30a3u30d6u306au30adu30fcu30efu30fcu30c9u3092u53d6u5f97u3059u308b
        
        Args:
            limit (int, optional): u53d6u5f97u3059u308bu30adu30fcu30efu30fcu30c9u306eu6700u5927u6570
            
        Returns:
            list: u30adu30fcu30efu30fcu30c9u30aau30d6u30b8u30a7u30afu30c8u306eu30eau30b9u30c8
        """
        return self.db.get_keywords(status='active', limit=limit)
    
    def mark_keyword_as_processed(self, keyword_id, status='completed'):
        """
        u30adu30fcu30efu30fcu30c9u306eu30b9u30c6u30fcu30bfu30b9u3092u66f4u65b0u3059u308b
        
        Args:
            keyword_id (int): u30adu30fcu30efu30fcu30c9ID
            status (str): u65b0u3057u3044u30b9u30c6u30fcu30bfu30b9 ('completed', 'failed', 'active')
        """
        with self.db.session_scope() as session:
            keyword = session.query(self.db.models.Keyword).filter(
                self.db.models.Keyword.id == keyword_id).first()
            if keyword:
                keyword.status = status
                keyword.last_searched_at = datetime.utcnow() if status == 'completed' else keyword.last_searched_at
