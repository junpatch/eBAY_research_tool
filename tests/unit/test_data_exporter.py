import pytest
import pandas as pd
import tempfile
from unittest.mock import MagicMock, Mock, patch, PropertyMock
from services.data_exporter import DataExporter
from core.database_manager import DatabaseManager
from core.config_manager import ConfigManager
from pathlib import Path
import os
import shutil
from contextlib import ExitStack
from models.data_models import EbaySearchResult, ExportHistory

@pytest.fixture
def mock_db():
    mock = Mock()
    # テスト用のデータを作成
    sample_results = [
        {
            'id': 1,
            'keyword_id': 1,
            'title': 'Test Item 1',
            'price': '$10.99',
            'condition': 'New',
            'shipping': 'Free',
            'location': 'US',
            'seller': 'Seller1',
            'created_at': '2024-03-20 10:00:00',
            'updated_at': '2024-03-20 10:00:00'
        },
        {
            'id': 2,
            'keyword_id': 1,
            'title': 'Test Item 2',
            'price': '$20.50',
            'condition': 'Used',
            'shipping': '$5.00',
            'location': 'UK',
            'seller': 'Seller2',
            'created_at': '2024-03-20 10:00:00',
            'updated_at': '2024-03-20 10:00:00'
        }
    ]
    mock.get_search_results.return_value = sample_results
    return mock

@pytest.fixture
def mock_config():
    mock = Mock()
    mock.get_path.return_value = Path(os.path.join(os.getcwd(), 'tests', 'test_data'))
    mock.get.return_value = 'csv'
    return mock

@pytest.fixture
def data_exporter(mock_config, mock_db):
    with patch('pathlib.Path.mkdir'):
        return DataExporter(mock_config, mock_db)

def test_export_results(data_exporter, mock_db):
    """export_results機能のテストを実施します"""
    data = mock_db.get_search_results()

    # _get_results_from_dbのモック
    with patch.object(data_exporter, '_get_results_from_db') as mock_get_results:
        mock_get_results.return_value = data

        # 一時ディレクトリの作成
        with tempfile.TemporaryDirectory() as tmp_dir:
            tmp_path = Path(tmp_dir)

            # ケース1: ファイルパス指定ありのエクスポートテスト
            test_formats = [
                {"format": "csv", "file_ext": ".csv"},
                {"format": "excel", "file_ext": ".xlsx"},
            ]
            
            for format_info in test_formats:
                format_type = format_info["format"]
                file_ext = format_info["file_ext"]
                path = tmp_path / f"test_export{file_ext}"
                
                result = data_exporter.export_results(
                    output_format=format_type,
                    output_path=str(path),
                    results=data
                )
                assert result == str(path)
                assert os.path.exists(path)
                
                # ファイル内容の検証
                if format_type == "csv":
                    exported_data = pd.read_csv(path)
                else:  # excel
                    exported_data = pd.read_excel(path)
                    
                assert not exported_data.empty
                assert all(col in exported_data.columns for col in [
                    'title', 'price', 'condition', 'shipping', 'location', 'seller'
                ])

            # ケース2: Google Sheetsエクスポートのテスト
            with patch('services.data_exporter.GoogleSheetsInterface') as mock_sheets:
                mock_sheets_instance = Mock()
                mock_sheets_instance.create_spreadsheet.return_value = 'test_spreadsheet_id'
                mock_sheets_instance.write_to_spreadsheet.return_value = {'updatedCells': 42}
                mock_sheets.return_value = mock_sheets_instance

                result = data_exporter.export_results(
                    output_format="google_sheets",
                    output_path="test_spreadsheet",
                    results=data
                )
                expected_url = "https://docs.google.com/spreadsheets/d/test_spreadsheet_id"
                assert result == expected_url

            # ケース3: keyword_idまたはjob_idを使用したテスト
            id_test_cases = [
                {"param": "keyword_id", "value": 1},
                {"param": "job_id", "value": 2},
            ]
            
            for case in id_test_cases:
                param_name = case["param"]
                param_value = case["value"]
                params = {
                    "output_format": "csv",
                    "output_path": str(tmp_path / "test_id_export.csv"),
                    param_name: param_value
                }
                
                result = data_exporter.export_results(**params)
                assert result == params["output_path"]
                
                # get_results_from_dbの呼び出しパラメータを検証
                keyword_id = param_value if param_name == "keyword_id" else None
                job_id = param_value if param_name == "job_id" else None
                mock_get_results.assert_called_with(keyword_id, job_id)
            
            # ケース4: 自動ファイルパス生成のテスト
            # datetimeをモック化して一定の時刻を返すようにする
            mock_timestamp = "20240401_120000"
            
            auto_path_test_cases = [
                {"format": "csv", "keyword_id": None, "job_id": None, "prefix": "ebay_results_", "ext": ".csv"},
                {"format": "excel", "keyword_id": None, "job_id": None, "prefix": "ebay_results_", "ext": ".xlsx"},
                {"format": "csv", "keyword_id": 123, "job_id": None, "prefix": "ebay_results_keyword_123_", "ext": ".csv"},
                {"format": "excel", "keyword_id": None, "job_id": 456, "prefix": "ebay_results_job_456_", "ext": ".xlsx"},
            ]
            
            with patch('services.data_exporter.datetime') as mock_datetime:
                # 固定の日時を返すようにモック
                mock_datetime.now.return_value.strftime.return_value = mock_timestamp
                
                for case in auto_path_test_cases:
                    format_type = case["format"]
                    keyword_id = case["keyword_id"]
                    job_id = case["job_id"]
                    expected_prefix = case["prefix"]
                    expected_ext = case["ext"]
                    
                    # 各エクスポートメソッドをモック化してファイルパスをキャプチャ
                    with patch.object(data_exporter, f'export_to_{format_type}', return_value=f"mocked_{format_type}_path") as mock_export:
                        data_exporter.export_results(
                            output_format=format_type,
                            keyword_id=keyword_id,
                            job_id=job_id,
                            results=data,
                            output_path=None  # 自動生成させる
                        )
                        
                        mock_export.assert_called_once()
                        file_path = mock_export.call_args[0][1]  # 第2引数がファイルパス
                        
                        # Pathオブジェクト化
                        if not isinstance(file_path, Path):
                            file_path = Path(file_path)
                        
                        # ファイル名を検証
                        filename = file_path.name
                        assert filename.startswith(expected_prefix)
                        assert filename.endswith(f"{mock_timestamp}{expected_ext}")
            
            # ケース5: Google Sheetsの自動タイトル生成テスト
            with patch('services.data_exporter.datetime') as mock_datetime:
                mock_datetime.now.return_value.strftime.return_value = mock_timestamp
                
                with patch.object(data_exporter, 'export_to_google_sheets', return_value="mocked_sheets_url") as mock_export_sheets:
                    data_exporter.export_results(
                        output_format="google_sheets",
                        results=data,
                        output_path=None  # 自動生成させる
                    )
                    
                    mock_export_sheets.assert_called_once()
                    title = mock_export_sheets.call_args[0][1]  # 第2引数がタイトル
                    
                    # タイトルを検証
                    assert title.startswith("ebay_results_")
                    assert title.endswith(mock_timestamp)
            
            # ケース6: formatが指定されていない場合（デフォルト値が使用される）
            result = data_exporter.export_results(
                output_format=None,
                output_path=str(tmp_path / "test_default_format.csv"),
                results=data
            )
            assert result is not None
            # デフォルト形式（mockなので常に'csv'）でエクスポートされたことを確認

            # ケース7: formatが無効の場合
            result = data_exporter.export_results(
                output_format="invalid",
                output_path=str(tmp_path / "test_invalid_format.csv"),
                results=data
            )
            assert result is None

def test_export_results_error_handling(data_exporter, mock_db):
    """export_resultsのエラーハンドリングをテストします"""

    # データ取得エラー
    mock_db.get_search_results.side_effect = Exception("Database error")
    result = data_exporter.export_results(output_format="csv")
    assert result is None
    mock_db.get_search_results.side_effect = None

    # 無効なファイルパス（CSVの場合）
    result = data_exporter.export_results(output_format="csv", output_path="")
    assert result is None

    # Google Sheetsエラー
    with patch('services.data_exporter.GoogleSheetsInterface') as mock_sheets:
        mock_sheets_instance = Mock()
        mock_sheets_instance.create_spreadsheet.side_effect = Exception("API error")
        mock_sheets.return_value = mock_sheets_instance

        data = mock_db.get_search_results()
        result = data_exporter.export_results(
            output_format="google_sheets",
            output_path="Test Spreadsheet",
            results=data
        )
        assert result is None

    # resultsがNoneで、keyword_idもjob_idも指定されていない場合
    result = data_exporter.export_results(output_format="csv")
    assert result is None

def test_export_to_csv(data_exporter, mock_db, tmp_path):
    """CSVエクスポート機能をテストします"""
    # エクスポート先のパス設定
    export_path = tmp_path / "test_export.csv"
    data = mock_db.get_search_results()

    # エクスポート実行
    output_path = data_exporter.export_to_csv(data,export_path)
    
    # 検証
    assert output_path == str(export_path)
    assert os.path.exists(export_path)
    # assert mock_db.get_search_results.called
    
    # エクスポートされたファイルの内容確認
    exported_data = pd.read_csv(export_path)
    assert not exported_data.empty
    assert all(col in exported_data.columns for col in ['title', 'price', 'condition', 'shipping', 'location', 'seller'])

    # Noneデータの場合のテスト
    output_path = data_exporter.export_to_csv(None, export_path)
    assert output_path is None  # Noneが返されることを確認
    
    # 空のDataFrameの場合のテスト
    empty_df = pd.DataFrame()
    output_path = data_exporter.export_to_csv(empty_df, export_path)
    assert output_path is None  # Noneが返されることを確認

    # 無効なファイルパス
    result = data_exporter.export_to_csv(data, "")
    assert result is None  # None が返されることを確認

def test_export_to_excel(data_exporter, mock_db, tmp_path):
    """Excelエクスポート機能をテストします"""
    # エクスポート先のパス設定
    export_path = tmp_path / "test_export.xlsx"
    data = mock_db.get_search_results()

    # エクスポート実行
    output_path = data_exporter.export_to_excel(data,str(export_path))
    
    # 検証
    assert output_path == str(export_path)
    assert os.path.exists(export_path)
    # assert mock_db.get_search_results.called
    
    # エクスポートされたファイルの内容確認
    exported_data = pd.read_excel(export_path)
    assert not exported_data.empty
    assert all(col in exported_data.columns for col in ['title', 'price', 'condition', 'shipping', 'location', 'seller'])

    # Noneデータの場合のテスト
    output_path = data_exporter.export_to_excel(None, export_path)
    assert output_path is None  # Noneが返されることを確認
    
    # 空のDataFrameの場合のテスト
    empty_df = pd.DataFrame()
    output_path = data_exporter.export_to_excel(empty_df, export_path)
    assert output_path is None  # Noneが返されることを確認
    
    # 無効なファイルパス
    result = data_exporter.export_to_excel(data, "")
    assert result is None  # None が返されることを確認


def test_export_to_google_sheets(data_exporter, mock_db):
    """Google Sheetsエクスポート機能をテストします"""
    with patch('services.data_exporter.GoogleSheetsInterface') as mock_sheets:
        # モックの設定
        mock_sheets_instance = Mock()
        mock_sheets_instance.create_spreadsheet.return_value = 'test_created_spreadsheet_id'
        # write_to_spreadsheet の戻り値を設定
        mock_sheets_instance.write_to_spreadsheet.return_value = {
            'updatedCells': 42,  # テスト用の更新セル数
            'updatedRange': 'Sheet1!A1:F10'
        }
        mock_sheets.return_value = mock_sheets_instance
        
        data = mock_db.get_search_results()
        title = "Test Spreadsheet"
        sheet_name = "Sheet1"

        # _record_export_history をモック化
        with patch.object(data_exporter, '_record_export_history') as mock_record_history:
            # エクスポート実行
            result = data_exporter.export_to_google_sheets(data, title=title, sheet_name=sheet_name)
            
            # 検証
            expected_spreadsheet_url = f"https://docs.google.com/spreadsheets/d/test_created_spreadsheet_id"
            assert result == expected_spreadsheet_url
            
            # write_to_spreadsheet の呼び出しを検証
            write_call_args = mock_sheets_instance.write_to_spreadsheet.call_args
            assert write_call_args is not None
            spreadsheet_id, range_name, values = write_call_args[0]
            assert spreadsheet_id == 'test_created_spreadsheet_id'
            assert range_name == f"{sheet_name}!A1"
            assert isinstance(values, list)
            assert len(values) > 1  # ヘッダー行 + データ行
            
            # ヘッダーとデータの検証
            header_row = values[0]
            data_rows = values[1:]
            expected_headers = ['id', 'keyword_id', 'title', 'price', 'condition', 'shipping', 'location', 'seller', 'created_at', 'updated_at']
            assert header_row == expected_headers
            assert len(data_rows) == len(data)  # データフレームの行数と一致することを確認
            
            # エクスポート履歴の記録を検証
            mock_record_history.assert_called_once_with(
                'google_sheets',
                expected_spreadsheet_url,
                len(data)
            )

            # ログ出力の検証（オプション）
            with patch('services.data_exporter.logger') as mock_logger:
                data_exporter.export_to_google_sheets(data, title=title, sheet_name=sheet_name)
                mock_logger.info.assert_called_once_with("42セルをGoogle Sheetsに書き込みました")

def test_output_dir_configuration(mock_db):
    """出力ディレクトリの設定をテストします（実際のファイルシステム操作なし）"""
    # Case 1: configがNoneを返すケース
    mock_config_none = Mock()
    mock_config_none.get_path.return_value = None
    # デフォルト値の処理を模倣するためのモック設定
    mock_config_none.get.side_effect = lambda path, default=None: 'excel' if path == ['export', 'default_format'] else default
    
    # 期待される出力ディレクトリパス
    expected_default_path = Path(__file__).parent.parent.parent / 'data' / 'exports'
    
    # Path.existsとPath.mkdirをモック化
    with patch('pathlib.Path.exists', return_value=False) as mock_exists:
        with patch('pathlib.Path.mkdir') as mock_mkdir:
            # DataExporterのインスタンス化
            exporter = DataExporter(mock_config_none, mock_db)
            
            # 出力ディレクトリが正しく設定されていることを確認
            assert exporter.output_dir == expected_default_path
            # ディレクトリ作成が正しいパラメータで呼び出されたか確認
            mock_mkdir.assert_called_once_with(parents=True, exist_ok=True)
            # デフォルト形式が正しく設定されていることを確認
            assert exporter.default_format == 'excel'
    
    # Case 2: configが具体的なパスを返すケース
    custom_path = Path('/path/to/custom_exports')
    mock_config_path = Mock()
    mock_config_path.get_path.return_value = custom_path
    # デフォルト値の処理を模倣するためのモック設定
    mock_config_path.get.side_effect = lambda path, default=None: 'csv' if path == ['export', 'default_format'] else default
    
    with patch('pathlib.Path.exists', return_value=False) as mock_exists:
        with patch('pathlib.Path.mkdir') as mock_mkdir:
            exporter = DataExporter(mock_config_path, mock_db)
            
            # 出力ディレクトリが設定値に設定されていることを確認
            assert exporter.output_dir == custom_path
            # ディレクトリ作成が正しいパラメータで呼び出されたか確認
            mock_mkdir.assert_called_once_with(parents=True, exist_ok=True)
            # デフォルト形式が正しく設定されていることを確認
            assert exporter.default_format == 'csv'
    
    # Case 3: configからdefault_formatが指定されていない場合（デフォルト値のcsvが使用される）
    temp_path = Path('/path/to/temp/exports')
    mock_config_no_format = Mock()
    mock_config_no_format.get_path.return_value = temp_path
    # getが呼ばれてもNoneを返すがデフォルト値は反映される
    mock_config_no_format.get.side_effect = lambda path, default=None: default
    
    with patch('pathlib.Path.exists', return_value=False) as mock_exists:
        with patch('pathlib.Path.mkdir') as mock_mkdir:
            exporter = DataExporter(mock_config_no_format, mock_db)
            # デフォルト形式がcsvになることを確認（DataExporter側のデフォルト値）
            assert exporter.default_format == 'csv'
            # ディレクトリ作成が正しいパラメータで呼び出されたか確認
            mock_mkdir.assert_called_once_with(parents=True, exist_ok=True)

def test_record_export_history(data_exporter, mock_db):
    """_record_export_historyメソッドのテストを実施します"""
    # モックセッションの設定
    mock_session = MagicMock()
    mock_context_manager = MagicMock()
    mock_context_manager.__enter__.return_value = mock_session
    mock_db.session_scope.return_value = mock_context_manager
    
    # エクスポート履歴記録のテスト
    export_type = 'csv'
    file_path = '/path/to/export.csv'
    record_count = 10
    
    # メソッド呼び出し
    data_exporter._record_export_history(export_type, file_path, record_count)
    
    # 検証: add()が適切なExportHistoryオブジェクトで呼ばれたこと
    mock_session.add.assert_called_once()
    history_obj = mock_session.add.call_args[0][0]
    assert history_obj.export_type == export_type
    assert history_obj.file_path == file_path
    assert history_obj.record_count == record_count
    assert history_obj.status == 'success'

    # 例外ケースのテスト
    mock_db.session_scope.side_effect = Exception("データベースエラー")
    
    # ロガーのモック
    with patch('services.data_exporter.logger') as mock_logger:
        # 例外が発生しても関数は例外を投げないはず
        data_exporter._record_export_history(export_type, file_path, record_count)
        # ロガーのerrorメソッドが呼ばれたことを確認
        mock_logger.error.assert_called_once()
        assert "エラー" in mock_logger.error.call_args[0][0]

def test_get_results_from_db(data_exporter, mock_db):
    """_get_results_from_dbメソッドのテストを実施します"""
    # モックセッションの設定
    mock_session = MagicMock()
    mock_context_manager = MagicMock()
    mock_context_manager.__enter__.return_value = mock_session
    mock_db.session_scope.return_value = mock_context_manager
    
    # モッククエリの設定
    mock_query = MagicMock()
    mock_session.query.return_value = mock_query
    
    # テスト用の結果データ
    test_results = [
        {
            'id': 1,
            'title': 'テスト商品1',
            'price': '$10.99',
            'condition': 'New',
        },
        {
            'id': 2,
            'title': 'テスト商品2',
            'price': '$20.50',
            'condition': 'Used',
        }
    ]
    
    # SQLAlchemyのクエリ結果オブジェクトをモックする代わりに、
    # 最終的に返される結果を直接モックする方法に変更
    # _get_results_from_dbメソッド内のquery.all()の結果をモック
    mock_result_objects = []
    for item in test_results:
        mock_result = MagicMock()
        # 各結果オブジェクトが辞書変換ループで参照される属性を追加
        for key, value in item.items():
            setattr(mock_result, key, value)
        mock_result_objects.append(mock_result)
    
    # モック結果オブジェクトの__table__.columnsを設定
    for mock_result in mock_result_objects:
        # 各属性名をカラム名としてモック化
        columns = []
        for key in test_results[0].keys():
            mock_column = MagicMock()
            mock_column.name = key
            columns.append(mock_column)
        
        # __table__属性をモック化
        mock_table = MagicMock()
        mock_table.columns = columns
        type(mock_result).__table__ = PropertyMock(return_value=mock_table)
    
    # query.all()が結果オブジェクトのリストを返すようにモック
    mock_query.all.return_value = mock_result_objects
    mock_query.filter.return_value = mock_query
    
    # ケース1: keyword_idを指定してDBから結果を取得
    keyword_id = 123
    results = data_exporter._get_results_from_db(keyword_id=keyword_id)
    
    # 検証
    mock_session.query.assert_called_with(EbaySearchResult)
    mock_query.filter.assert_called_once()
    
    # 結果の検証
    assert len(results) == 2
    assert results[0]['id'] == 1
    assert results[0]['title'] == 'テスト商品1'
    assert results[1]['id'] == 2
    assert results[1]['title'] == 'テスト商品2'
    
    # ケース2: 例外ケース
    mock_db.session_scope.side_effect = Exception("データベースエラー")
    
    # ロガーのモック
    with patch('services.data_exporter.logger') as mock_logger:
        results = data_exporter._get_results_from_db(keyword_id=keyword_id)
        # 空のリストが返されることを確認
        assert results == []
        # ロガーのerrorメソッドが呼ばれたことを確認
        assert mock_logger.error.call_count == 2  # 2回呼び出されることを期待
        assert "エラー" in mock_logger.error.call_args_list[0][0][0]  # 最初の呼び出しのメッセージを確認
        assert "Traceback" in mock_logger.error.call_args_list[1][0][0]  # 2回目の呼び出しはトレースバック

def test_format_columns(data_exporter):
    """_format_columnsメソッドのテストを実施します"""
    # テスト用のデータフレーム作成
    data = {
        'title': ['商品A', '商品B'],
        'price': ['100', '200'],
        'condition': ['新品', '中古'],
        'item_id': ['ID001', 'ID002'],
        'auction_end_time': ['2024-03-01 10:00:00', '2024-03-02 15:30:00'],
        'search_timestamp': ['2024-03-15 12:00:00', '2024-03-15 12:01:00']
    }
    df = pd.DataFrame(data)
    
    # テスト対象メソッド実行
    formatted_df = data_exporter._format_columns(df)
    
    # 列名が正しく変換されているか検証
    assert '商品タイトル' in formatted_df.columns  # 'title' -> '商品タイトル'
    assert '商品ID' in formatted_df.columns  # 'item_id' -> '商品ID'
    assert 'オークション終了時間' in formatted_df.columns  # 'auction_end_time' -> 'オークション終了時間'
    assert '検索時刻' in formatted_df.columns  # 'search_timestamp' -> '検索時刻'

    # 日付フォーマットが正しく変換されているか検証
    # 既に正しいフォーマットの場合は変換後も同じ形式のままであるべき
    assert formatted_df['オークション終了時間'][0] == '2024-03-01 10:00:00'
    assert formatted_df['検索時刻'][1] == '2024-03-15 12:01:00'
    
    # 元のDataFrameに存在しない列が追加されていないことを確認
    assert len(formatted_df.columns) == len(df.columns)
    
    # カラムのデータが変更されていないことを確認（日付列以外）
    assert formatted_df['商品タイトル'][0] == '商品A'
    assert formatted_df['価格'][1] == '200'
    
    # 無効なデータフォーマットや空のDataFrameのテストも追加可能
    empty_df = pd.DataFrame()
    formatted_empty_df = data_exporter._format_columns(empty_df)
    assert formatted_empty_df.empty
