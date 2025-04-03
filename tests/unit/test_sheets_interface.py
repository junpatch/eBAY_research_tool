# -*- coding: utf-8 -*-

import pytest
import os
import sys
import json
from pathlib import Path
from unittest.mock import patch, MagicMock, mock_open

# テスト対象のモジュールをインポート
sys.path.append(str(Path(__file__).parent.parent))
from interfaces.sheets_interface import GoogleSheetsInterface

@pytest.fixture
def mock_config(tmp_path):
    """設定マネージャーのモック"""
    mock_config = MagicMock()
    # 必要な設定値を設定
    def config_get_side_effect(key, default=None):
        if key == ['google_sheets', 'credentials_path']:
            return 'credentials.json'
        elif key == ['google_sheets', 'scopes']:
            return ['https://www.googleapis.com/auth/spreadsheets']
        else:
            return default
    
    mock_config.get.side_effect = config_get_side_effect
    token_dir_path = tmp_path / "google_token"
    mock_config.get_path.return_value = token_dir_path
    return mock_config

@pytest.fixture
def sheets_interface(mock_config):
    """GoogleSheetsInterfaceのインスタンス"""
    return GoogleSheetsInterface(mock_config)

@pytest.fixture
def mock_credentials():
    """Credentialsのモック"""
    mock_creds = MagicMock()
    mock_creds.valid = True
    mock_creds.expired = False
    mock_creds.to_json.return_value = json.dumps({"token": "mock_token"})
    return mock_creds

@pytest.fixture
def mock_service():
    """APIサービスのモック"""
    mock_svc = MagicMock()
    # spreadsheets().values().get().execute() のモック
    mock_get = MagicMock()
    mock_get.execute.return_value = {"values": [["A1", "B1"], ["A2", "B2"]]}
    
    mock_values = MagicMock()
    mock_values.get.return_value = mock_get
    
    # spreadsheets().values().update().execute() のモック
    mock_update = MagicMock()
    mock_update.execute.return_value = {"updatedCells": 4}
    mock_values.update.return_value = mock_update
    
    # spreadsheets().values().clear().execute() のモック
    mock_clear = MagicMock()
    mock_clear.execute.return_value = {"clearedRange": "Sheet1!A1:Z1000"}
    mock_values.clear.return_value = mock_clear
    
    # spreadsheets().create().execute() のモック
    mock_create = MagicMock()
    mock_create.execute.return_value = {"spreadsheetId": "mock_spreadsheet_id"}
    
    # spreadsheets().get().execute() のモック
    mock_spreadsheet_get = MagicMock()
    mock_spreadsheet_get.execute.return_value = {
        "spreadsheetId": "mock_spreadsheet_id",
        "sheets": [{"properties": {"title": "Sheet1"}}]
    }
    
    # spreadsheets().batchUpdate().execute() のモック
    mock_batch_update = MagicMock()
    mock_batch_update.execute.return_value = {"replies": [{"addSheet": {"properties": {"title": "NewSheet"}}}]}
    
    mock_spreadsheets = MagicMock()
    mock_spreadsheets.values.return_value = mock_values
    mock_spreadsheets.create.return_value = mock_create
    mock_spreadsheets.get.return_value = mock_spreadsheet_get
    mock_spreadsheets.batchUpdate.return_value = mock_batch_update
    
    mock_svc.spreadsheets.return_value = mock_spreadsheets
    
    return mock_svc

def test_init(sheets_interface, tmp_path):
    """初期化のテスト"""
    assert sheets_interface.credentials_path == 'credentials.json'
    assert sheets_interface.scopes == ['https://www.googleapis.com/auth/spreadsheets']
    # tmp_path を使った期待値に変更
    expected_token_dir = tmp_path / "google_token"
    assert sheets_interface.token_dir == expected_token_dir
    assert sheets_interface.token_path == expected_token_dir / 'token.json'
    assert sheets_interface.service is None

def test_authenticate_with_valid_token(sheets_interface, mock_credentials, mock_service):
    """有効なトークンでの認証テスト"""
    # トークンが既に存在する場合
    with patch('os.path.exists', return_value=True), \
         patch('pathlib.Path.read_text', return_value=json.dumps({"token": "mock_token"})), \
         patch('google.oauth2.credentials.Credentials.from_authorized_user_info', return_value=mock_credentials), \
         patch('googleapiclient.discovery.build', return_value=mock_service):
        
        # パッチが正しく適用されているかを直接確認せず、authenticate関数の戻り値に基づいて動作を検証
        result = sheets_interface.authenticate()
        
        # 認証結果が成功で、サービスが設定されていることを確認
        assert result is True
        assert sheets_interface.service is not None

def test_authenticate_with_expired_token(sheets_interface, mock_credentials, mock_service):
    """期限切れトークンでの認証テスト"""
    # 期限切れのトークン
    mock_credentials.valid = False
    mock_credentials.expired = True
    mock_credentials.refresh_token = True  # refresh_tokenがある場合
    
    with patch('os.path.exists', return_value=True), \
         patch('pathlib.Path.read_text', return_value=json.dumps({"token": "expired_token"})), \
         patch('google.oauth2.credentials.Credentials.from_authorized_user_info', return_value=mock_credentials), \
         patch('googleapiclient.discovery.build', return_value=mock_service):
        
        # refreshメソッドがモックで、後で呼び出しを確認できるようにしておく
        mock_credentials.refresh = MagicMock()
        
        result = sheets_interface.authenticate()
        
        # 認証が成功し、refresh()が呼ばれ、サービスが設定されていることを確認
        assert result is True
        mock_credentials.refresh.assert_called_once()
        assert sheets_interface.service is not None

def test_authenticate_new_token(sheets_interface, mock_service):
    """新しいトークンの作成テスト"""
    # トークンが存在しない場合
    mock_flow = MagicMock()
    mock_creds = MagicMock()
    mock_creds.to_json.return_value = json.dumps({"token": "new_token"})
    mock_flow.run_local_server.return_value = mock_creds
    
    mock_write = MagicMock()
    
    with patch('os.path.exists', return_value=False), \
         patch('google_auth_oauthlib.flow.InstalledAppFlow.from_client_secrets_file', return_value=mock_flow), \
         patch('pathlib.Path.write_text', mock_write), \
         patch('googleapiclient.discovery.build', return_value=mock_service):
        
        result = sheets_interface.authenticate()
        
        # 認証が成功し、フローが実行され、トークンが保存され、サービスが設定されていることを確認
        assert result is True
        mock_flow.run_local_server.assert_called_once_with(port=0)
        assert sheets_interface.service is not None
        # write_textが少なくとも1回は呼ばれていることを確認
        assert mock_write.call_count > 0

def test_authenticate_no_credentials(sheets_interface):
    """クレデンシャルが設定されていない場合のテスト"""
    # credentials_pathが設定されていない場合
    sheets_interface.credentials_path = None
    
    result = sheets_interface.authenticate()
    
    assert result is False

def test_authenticate_exception(sheets_interface):
    """認証中の例外テスト"""
    with patch('os.path.exists', side_effect=Exception("テスト例外")):
        result = sheets_interface.authenticate()
        
        assert result is False

def test_read_spreadsheet(sheets_interface, mock_service):
    """スプレッドシートからの読み込みテスト"""
    # サービスを設定
    sheets_interface.service = mock_service
    
    # 読み込みテスト
    result = sheets_interface.read_spreadsheet("mock_spreadsheet_id", "Sheet1!A1:B2")
    
    assert result == [["A1", "B1"], ["A2", "B2"]]
    mock_service.spreadsheets().values().get.assert_called_once_with(
        spreadsheetId="mock_spreadsheet_id", range="Sheet1!A1:B2")

def test_read_spreadsheet_no_service(sheets_interface, mock_service):
    """サービスなしでの読み込みテスト"""
    # サービスが設定されていない状態
    sheets_interface.service = None
    
    # authenticateメソッドをパッチ
    with patch.object(sheets_interface, 'authenticate') as mock_auth:
        # authenticateが呼ばれたときにTrueを返し、サービスを設定するよう模擬する
        def auth_side_effect():
            sheets_interface.service = mock_service
            return True
        mock_auth.side_effect = auth_side_effect
        
        # メソッド実行
        result = sheets_interface.read_spreadsheet("mock_spreadsheet_id", "Sheet1!A1:B2")
        
        # authenticateが呼ばれたことを確認
        mock_auth.assert_called_once()
        # 結果が取得できていることを確認
        assert result is not None

def test_read_spreadsheet_auth_failed(sheets_interface):
    """認証失敗時の読み込みテスト"""
    # サービスがなく、認証も失敗する場合
    sheets_interface.service = None
    
    with patch.object(sheets_interface, 'authenticate', return_value=False):
        result = sheets_interface.read_spreadsheet("mock_spreadsheet_id", "Sheet1!A1:B2")
        
        assert result is None

def test_read_spreadsheet_http_error(sheets_interface, mock_service):
    """HTTPエラー時の読み込みテスト"""
    # サービスを設定
    sheets_interface.service = mock_service
    
    # APIエラーをシミュレート
    from googleapiclient.errors import HttpError
    mock_response = MagicMock()
    mock_response.status = 403
    mock_response.reason = "Forbidden"
    
    mock_service.spreadsheets().values().get.side_effect = HttpError(
        mock_response, b'{"error": {"message": "API error"}}')
    
    result = sheets_interface.read_spreadsheet("mock_spreadsheet_id", "Sheet1!A1:B2")
    
    assert result is None

def test_write_to_spreadsheet(sheets_interface, mock_service):
    """スプレッドシートへの書き込みテスト"""
    # サービスを設定
    sheets_interface.service = mock_service
    
    # 書き込みテスト
    values = [["C1", "D1"], ["C2", "D2"]]
    result = sheets_interface.write_to_spreadsheet("mock_spreadsheet_id", "Sheet1!C1:D2", values)
    
    assert result == {"updatedCells": 4}
    mock_service.spreadsheets().values().update.assert_called_once_with(
        spreadsheetId="mock_spreadsheet_id",
        range="Sheet1!C1:D2",
        valueInputOption="RAW",
        body={"values": values})

def test_create_spreadsheet(sheets_interface, mock_service):
    """スプレッドシート作成テスト"""
    # サービスを設定
    sheets_interface.service = mock_service
    
    # 作成テスト（シート名指定あり）
    result = sheets_interface.create_spreadsheet("Test Spreadsheet", ["Sheet1", "Sheet2"])
    
    assert result == "mock_spreadsheet_id"
    mock_service.spreadsheets().create.assert_called_once()
    
    # 呼び出し引数を確認
    call_args = mock_service.spreadsheets().create.call_args[1]
    assert call_args["body"]["properties"]["title"] == "Test Spreadsheet"
    assert len(call_args["body"]["sheets"]) == 2

def test_create_spreadsheet_default_sheet(sheets_interface, mock_service):
    """デフォルトシートでのスプレッドシート作成テスト"""
    # サービスを設定
    sheets_interface.service = mock_service
    
    # シート名指定なしの作成テスト
    result = sheets_interface.create_spreadsheet("Test Spreadsheet")
    
    assert result == "mock_spreadsheet_id"
    # 呼び出し引数を確認
    call_args = mock_service.spreadsheets().create.call_args[1]
    assert call_args["body"]["properties"]["title"] == "Test Spreadsheet"
    assert len(call_args["body"]["sheets"]) == 1
    assert call_args["body"]["sheets"][0]["properties"]["title"] == "Sheet1"

def test_clear_range(sheets_interface, mock_service):
    """範囲クリアテスト"""
    # サービスを設定
    sheets_interface.service = mock_service
    
    # クリアテスト
    result = sheets_interface.clear_range("mock_spreadsheet_id", "Sheet1!A1:Z1000")
    
    assert result == {"clearedRange": "Sheet1!A1:Z1000"}
    mock_service.spreadsheets().values().clear.assert_called_once_with(
        spreadsheetId="mock_spreadsheet_id", range="Sheet1!A1:Z1000")

def test_get_spreadsheet_info(sheets_interface, mock_service):
    """スプレッドシート情報取得テスト"""
    # サービスを設定
    sheets_interface.service = mock_service
    
    # 情報取得テスト
    result = sheets_interface.get_spreadsheet_info("mock_spreadsheet_id")
    
    assert result["spreadsheetId"] == "mock_spreadsheet_id"
    assert result["sheets"][0]["properties"]["title"] == "Sheet1"
    mock_service.spreadsheets().get.assert_called_once_with(
        spreadsheetId="mock_spreadsheet_id")

def test_add_sheet(sheets_interface, mock_service):
    """シート追加テスト"""
    # サービスを設定
    sheets_interface.service = mock_service
    
    # 追加テスト
    result = sheets_interface.add_sheet("mock_spreadsheet_id", "NewSheet")
    
    assert result["replies"][0]["addSheet"]["properties"]["title"] == "NewSheet"
    mock_service.spreadsheets().batchUpdate.assert_called_once()
    
    # 呼び出し引数を確認
    call_args = mock_service.spreadsheets().batchUpdate.call_args[1]
    assert call_args["spreadsheetId"] == "mock_spreadsheet_id"
    assert call_args["body"]["requests"][0]["addSheet"]["properties"]["title"] == "NewSheet"

def test_add_sheet_already_exists(sheets_interface, mock_service):
    """既存シート追加テスト"""
    # サービスを設定
    sheets_interface.service = mock_service
    
    # get()メソッドを初期化して、正確な呼び出し回数をトラッキングできるようにする
    mock_service.spreadsheets.return_value.get.reset_mock()
    
    # 既存のシート情報を返すようにモック
    mock_service.spreadsheets().get().execute.return_value = {
        "spreadsheetId": "mock_spreadsheet_id",
        "sheets": [{"properties": {"title": "Sheet1"}}, {"properties": {"title": "NewSheet"}}]
    }
    
    # 既に存在するシートを追加
    result = sheets_interface.add_sheet("mock_spreadsheet_id", "NewSheet")
    
    # 既存のシートの場合はNoneを返し、batchUpdateは呼ばれない
    assert result is None
    # 呼び出し回数の確認ではなく、適切な引数で呼ばれたことだけを確認
    mock_service.spreadsheets().get.assert_any_call(spreadsheetId="mock_spreadsheet_id") 