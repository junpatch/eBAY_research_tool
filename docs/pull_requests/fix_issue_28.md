# Fix: DataExporter クラスの export_results 関数の引数名を修正

## 問題点

Issue #28 で指摘されている通り、`DataExporter.export_results()`メソッドの引数名が統合テストで期待されているものと一致していませんでした。テストでは`output_format`というパラメータを使用していますが、実装ではこの引数名が`format`として定義されていました。

## 修正内容

`DataExporter`クラスの`export_results`メソッドの引数名を以下のように修正しました:

1. `format` -> `output_format`
2. `file_path` -> `output_path`
3. 新たに`filters`引数を追加

また、関数内部でこれらの変数を参照している箇所もすべて修正しました。

## 影響範囲

- `DataExporter`クラスの`export_results`メソッドのみの変更です
- メソッドの内部実装ロジックは変更していません
- この修正により統合テスト`test_data_export_flow.py`が正常に実行できるようになります

## テスト結果

統合テストが正常に実行できることを確認しました。

## 関連 Issue

- Closes #28
