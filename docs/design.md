# eBay リサーチツール 基本設計書

## 1. システム概要

### 1.1 システムの目的・概要

本システムは、EC販売事業者向けのeBayデータ収集・分析ツールであり、以下の主要目的を持つ:

- eBay上の商品データを自動的に収集
- 大量のキーワードに対する効率的な市場調査
- 販売戦略立案のための価格・在庫情報の自動取得

### 1.2 システム全体のアーキテクチャ概要

- アーキテクチャ：モノリシック + モジュラーアプローチ
- コンポーネント構成：
    1. データインポートモジュール
    2. eBay検索・スクレイピングモジュール
    3. データ抽出・整形モジュール
    4. データエクスポートモジュール

### 1.3 使用する技術・フレームワーク

- プログラミング言語：Python 3.9+
- Web自動化ライブラリ：Playwright
- データ処理：Pandas
- API連携：Google Sheets API
- 追加ライブラリ：Requests

### 1.4 システムデータフロー

1. Googleスプレッドシートからキーワードインポート
2. キーワードを順次処理
3. eBayへ自動ログイン
4. 各キーワードで検索実行
5. 検索結果からデータ抽出
6. データ整形
7. CSV/スプレッドシートへ出力

## 2. システムアーキテクチャ

### 2.1 アーキテクチャ構成

- アーキテクチャパターン：レイヤードアーキテクチャ
- 主要レイヤー：
    1. プレゼンテーション層（UI/設定管理）
    2. ビジネスロジック層（データ処理、検索ロジック）
    3. データアクセス層（Web自動化、API連携）

### 2.2 技術スタック

- 言語: Python 3.9+
- Web自動化: Playwright
- データ処理: Pandas
- 外部サービス:
    - eBay
    - Google Sheets
- ライブラリ:
    - Playwright
    - Pandas
    - Google Sheets API Client

### 2.3 デプロイ戦略

- ローカル実行：Windows/Mac/Linux環境
- コンテナ化：Docker利用可能
- クラウド：将来的にAWS Lambda or Google Cloud Functions検討

## 3. 機能設計

### 3.1 キーワードインポート機能

- 入力形式：Googleスプレッドシート / CSV
- 処理能力：最大1,000キーワード
- データバリデーション：
    - キーワード長さチェック
    - 特殊文字フィルタリング

### 3.2 eBay検索・データ抽出機能

- 抽出項目：
    1. 価格
    2. 在庫数
    3. 出品者評価
    4. 入札数
    5. 送料
    6. 出品終了までの残り時間
- 抽出戦略：
    - Playwrightによる動的スクレイピング
    - 高度なセレクタ・XPath利用
    - エラーハンドリングと自動リトライ
    - リクエスト間隔の動的制御

### 3.3 データ出力機能

- 出力形式：
    1. CSV
    2. Googleスプレッドシート
- データ整形：
    - 不要文字列除去
    - 型変換
    - 数値フォーマット統一

## 4. 非機能要件設計

### 4.1 パフォーマンス

- 目標処理時間：1,000キーワードを60分以内
- 並列処理：Playwrightのコンテキスト並列実行
- リクエスト制御：秒間リクエスト数の動的調整

### 4.2 セキュリティ

### 認証情報管理

1. **認証情報保護**
    - 環境変数による機密情報の隔離
    - 暗号化による安全な保存
    - 認証情報アクセスの厳密な制御
2. **暗号化戦略**
    
    ```python
    python
    コピー
    from cryptography.fernet import Fernet
    
    class CredentialManager:
        def __init__(self, key_path):
            # 暗号化キーの安全な管理
            with open(key_path, 'rb') as key_file:
                self.key = key_file.read()
            self.cipher_suite = Fernet(self.key)
    
        def encrypt_credential(self, credential):
            return self.cipher_suite.encrypt(credential.encode())
    
        def decrypt_credential(self, encrypted_credential):
            return self.cipher_suite.decrypt(encrypted_credential).decode()
    
    ```
    

### 4.3 可用性とエラーハンドリング

### エラーシナリオ対応戦略

1. **具体的なエラーハンドリング**
    - CAPTCHAエラー：
        - 手動介入オプション
        - プロキシ/ユーザーエージェント自動切り替え
    - 一時的アクセス制限：
        - 指数バックオフアルゴリズムによる再試行
        - 詳細なエラーログ記録
2. **リトライ戦略**
    
    ```python
    python
    コピー
    import time
    from tenacity import retry, stop_after_attempt, wait_exponential
    
    class ResearchToolRetryHandler:
        @retry(
            stop=stop_after_attempt(3),
            wait=wait_exponential(multiplier=1, min=4, max=10)
        )
        def execute_search(self, keyword):
            # 検索実行のロジック
            # CAPTCHAや一時的エラーに対応
            pass
    
    ```
    
3. **詳細なログ出力**
    - エラーコンテキストの完全キャプチャ
    - システム状態のスナップショット
    - 修復可能性の評価

### 4.4 拡張性

- モジュラーアーキテクチャ採用
- 他ECプラットフォーム対応を考慮した設計
- 設定ファイルによる柔軟な機能拡張

## 5. インフラ設計

### 5.1 開発環境

- OS: Windows 10/11, macOS, Linux
- Python環境: 3.9以上
- 推奨IDE: PyCharm, VSCode

### 5.2 デプロイ方法

- スタンドアロン実行可能
- Dockerコンテナ対応
- 仮想環境（venv）推奨

### 5.3 ログ管理

- ログレベル: INFO, WARNING, ERROR
- ログ出力先: ローカルファイル
- ログ保持期間: 30日

## 6. テスト計画

### 6.1 ユニットテスト

- pytest利用
- カバレッジ目標: 80%以上
- テスト対象:
    - データインポート機能
    - スクレイピングロジック
    - データ整形・出力機能

### 6.2 統合テスト

- eBayサイト構造変更対応
- API制限・エラーハンドリングテスト
- 大量データ処理テスト

## 7. リスク管理

### 7.1 法的リスク対応

- eBay利用規約の定期的確認
- スクレイピング範囲の適切な制限
- 必要に応じて法務相談

### 7.2 技術的リスク

- eBayサイト構造変更への対応
- CAPTCHA対策
- プロキシ・IP管理戦略

## 8. 開発スケジュール

### 8.1 マイルストーン

1. 要件確定: 2週間
2. 基本設計: 1週間
3. プロトタイプ開発: 4週間
4. テスト: 2週間
5. 最終調整: 1週間

### 8.2 リリーススケジュール

- α版: 開発開始後8週間
- β版: 開発開始後12週間
- 正式リリース: 開発開始後16週間

---

**注意事項**

- 本設計書は初期バージョンであり、継続的な改善が前提
- 実装時に詳細な仕様調整が必要
- ユーザーフィードバックを反映し、柔軟に対応する

実装サンプル:

```python
from playwright.sync_api import sync_playwright
import pandas as pd

class EbayResearchTool:
    def __init__(self, keywords_file):
        self.keywords = pd.read_csv(keywords_file)

    def scrape_ebay(self):
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)
            context = browser.new_context()
            page = context.new_page()

            results = []
            for keyword in self.keywords['keyword']:
                page.goto('https://www.ebay.com')
                page.fill('#search-input', keyword)
                page.click('#search-button')

                # データ抽出ロジック
                items = page.query_selector_all('.s-item')
                for item in items:
                    # 必要な情報を抽出
                    result = {
                        'keyword': keyword,
                        'price': item.inner_text('.s-item__price'),
                        # 他の必要な項目
                    }
                    results.append(result)

            browser.close()
            return pd.DataFrame(results)

```