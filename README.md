# eBay Research Tool

## 概要

eBay Research Toolは、eBayの商品情報を自動的に収集・分析するためのツールです。キーワードリストからeBayの検索結果を自動的にスクレイピングし、データを収集して分析することができます。

## 主な機能

- キーワードの管理（CSVやExcelからのインポート）
- eBayへの自動ログイン
- キーワードに基づく商品検索と情報収集
- 検索結果のエクスポート（CSV、Excel、Google Sheets）
- データベースによる検索結果の管理
- コマンドラインインターフェース（CLI）

## インストール方法

```bash
# リポジトリをクローン
git clone <リポジトリURL>
cd eBAY_research_tool

# 依存関係のインストール
pip install -r requirements.txt

# Playwrightブラウザのインストール
python -m playwright install
```

## 環境変数の設定

以下の環境変数を設定することで、eBayアカウントの認証情報やGoogle Sheets APIの認証情報を指定できます。

```bash
# Windows PowerShell
$env:EBAY_USERNAME = "あなたのeBayユーザー名"
$env:EBAY_PASSWORD = "あなたのeBayパスワード"
$env:GOOGLE_SHEETS_CREDENTIALS_PATH = "path/to/credentials.json"

# または .env ファイルを作成
```

## 使用方法

### キーワードのインポート

```bash
# CSVファイルからキーワードをインポート
python main.py import --file keywords.csv --format csv

# Excelファイルからキーワードをインポート
python main.py import --file keywords.xlsx --format excel
```

### eBay検索の実行

```bash
# すべてのアクティブなキーワードで検索を実行し、結果をCSVに出力
python main.py search --format csv --output results.csv

# 最初の10個のキーワードのみ検索
python main.py search --limit 10

# eBayにログインして検索を実行
python main.py search --login
```

### 統計情報の表示

```bash
# データベースの統計情報を表示
python main.py stats

# キーワードリストの表示
python main.py list-keywords
```

### データベースの初期化

```bash
# すべてのデータをクリア
python main.py clean-all
```

## 設定ファイル

`config/config.yaml`ファイルを編集することで、アプリケーションの動作をカスタマイズできます。

```yaml
# 例: スクレイピングの待機時間を変更
scraping:
  wait_time: 2  # 秒単位
  max_retries: 3
```

## 構造

```
eBAY_research_tool/
├── config/              # 設定ファイル
├── core/                # コア機能
├── data/                # データファイル
├── interfaces/          # インターフェース
├── logs/                # ログファイル
├── models/              # データモデル
├── output/              # エクスポートファイル
├── services/            # サービス機能
├── tests/               # テスト
├── main.py              # メインエントリーポイント
└── requirements.txt     # 依存関係
```

## トラブルシューティング

### よくある問題

1. **eBayログインに失敗する**
   - 環境変数に正しい認証情報が設定されているか確認してください
   - eBayがログインCAPTCHAを表示している可能性があります

2. **スクレイピングがブロックされる**
   - 設定ファイルでリクエスト間の待機時間を長くしてみてください
   - IPが一時的にブロックされている場合は、しばらく待ってから再試行してください

3. **Google Sheetsへのエクスポートに失敗する**
   - 正しい認証情報ファイルが設定されているか確認してください
   - APIが有効化されているか確認してください

## ライセンス

MIT
