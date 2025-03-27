# Command Line Interface for eBay Research Tool

import typer
import logging
from typing import Optional, List
from pathlib import Path
import rich
from rich.console import Console
from rich.progress import Progress, TextColumn, BarColumn, TaskProgressColumn
from rich.table import Table
import time
from datetime import datetime

app = typer.Typer(help="eBay Research Tool - データ収集・分析ツール")
console = Console()

@app.command("import")
def import_keywords(
    file: Path = typer.Option(..., "--file", "-f", help="インポートするCSV/Excelファイルパス"),
    format: str = typer.Option("csv", "--format", "-t", help="ファイル形式（csv または excel）"),
    keyword_column: str = typer.Option("keyword", "--keyword-column", "-k", help="キーワードが含まれる列名"),
    category_column: Optional[str] = typer.Option(None, "--category-column", "-c", help="カテゴリが含まれる列名（任意）"),
    has_header: bool = typer.Option(True, "--header/--no-header", help="ヘッダー行の有無")
):
    """CSVまたはExcelファイルからキーワードをインポートします"""
    from core.config_manager import ConfigManager
    from core.database_manager import DatabaseManager
    from core.logger_manager import LoggerManager
    from services.keyword_manager import KeywordManager
    
    # 初期化
    config = ConfigManager()
    logger = LoggerManager().get_logger()
    db = DatabaseManager(config.get_db_url())
    db.create_tables()
    keyword_manager = KeywordManager(db, config)
    
    # ファイル形式のチェック
    if not file.exists():
        console.print(f"[bold red]エラー:[/] ファイル '{file}' が見つかりません。", style="red")
        raise typer.Exit(1)
        
    # インポート処理
    with console.status(f"[bold green]キーワードをインポート中...[/]") as status:
        try:
            if format.lower() == "csv":
                added_count = keyword_manager.import_from_csv(
                    file, keyword_column, category_column, has_header)
            elif format.lower() == "excel":
                added_count = keyword_manager.import_from_excel(
                    file, 0, keyword_column, category_column)
            else:
                console.print(f"[bold red]エラー:[/] サポートされていない形式です: {format}", style="red")
                raise typer.Exit(1)
                
            console.print(f"[bold green]成功:[/] {added_count}個のキーワードをインポートしました。")
            
        except Exception as e:
            console.print(f"[bold red]エラー:[/] インポート中に問題が発生しました: {str(e)}", style="red")
            logger.error(f"キーワードインポート中にエラーが発生しました: {e}")
            raise typer.Exit(1)

@app.command("search")
def search_keywords(
    limit: int = typer.Option(None, "--limit", "-l", help="処理するキーワード数の上限"),
    output_format: str = typer.Option("csv", "--format", "-f", help="出力形式（csv, excel, google_sheets）"),
    output_file: Optional[Path] = typer.Option(None, "--output", "-o", help="出力ファイルパス"),
    login: bool = typer.Option(False, "--login/--no-login", help="eBayにログインするかどうか")
):
    """保存されたキーワードでeBay検索を実行し、結果を出力します"""
    from core.config_manager import ConfigManager
    from core.database_manager import DatabaseManager
    from core.logger_manager import LoggerManager
    from services.keyword_manager import KeywordManager
    from services.ebay_scraper import EbayScraper
    from services.data_exporter import DataExporter
    
    # 初期化
    config = ConfigManager()
    logger = LoggerManager().get_logger()
    db = DatabaseManager(config.get_db_url())
    keyword_manager = KeywordManager(db, config)
    exporter = DataExporter(config, db)
    
    # アクティブなキーワードを取得
    keywords = keyword_manager.get_active_keywords(limit=limit)
    if not keywords:
        console.print("[bold yellow]警告:[/] 処理対象のキーワードがありません。先にインポートしてください。")
        raise typer.Exit(0)
        
    console.print(f"[bold]検索対象キーワード:[/] {len(keywords)}個", style="blue")
    
    # 検索処理開始
    with EbayScraper(config) as scraper:
        # ログイン（オプション）
        if login:
            with console.status("[bold green]eBayにログイン中...[/]") as status:
                if scraper.login():
                    console.print("[bold green]ログイン成功[/]")
                else:
                    console.print("[bold yellow]警告:[/] ログインできませんでした。ログインなしで続行します。")
        
        # 検索履歴を記録開始
        job_id = db.start_search_job(len(keywords))
        
        # 進捗バーを表示
        total_results = 0
        with Progress(
            TextColumn("[bold blue]{task.description}"),
            BarColumn(bar_width=None),
            "[progress.percentage]{task.percentage:>3.0f}%",
            "•",
            TaskProgressColumn(),
            "•",
            TextColumn("残り時間: [bold]{task.fields[remaining]}"),
            console=console,
            transient=True
        ) as progress:
            task = progress.add_task("[green]キーワード検索中...", total=len(keywords), remaining="計算中")
            start_time = time.time()
            
            for i, keyword in enumerate(keywords):
                progress.update(task, description=f"[green]検索中: {keyword.keyword}")
                
                # 残り時間を計算
                elapsed = time.time() - start_time
                if i > 0:  # 最初のキーワード以降で残り時間を計算
                    items_per_sec = i / elapsed
                    remaining_items = len(keywords) - i
                    remaining_seconds = remaining_items / items_per_sec if items_per_sec > 0 else 0
                    
                    # 残り時間の表示形式を整形
                    if remaining_seconds < 60:
                        remaining_str = f"{int(remaining_seconds)}秒"
                    elif remaining_seconds < 3600:
                        remaining_str = f"{int(remaining_seconds / 60)}分{int(remaining_seconds % 60)}秒"
                    else:
                        hours = int(remaining_seconds / 3600)
                        minutes = int((remaining_seconds % 3600) / 60)
                        remaining_str = f"{hours}時間{minutes}分"
                        
                    progress.update(task, remaining=remaining_str)
                
                # 検索実行
                try:
                    results = scraper.search_keyword(keyword.keyword)
                    
                    # 結果をDBに保存
                    if results:
                        saved_count = db.save_search_results(keyword.id, results)
                        total_results += saved_count
                        
                        # 検索履歴を更新
                        db.update_search_job_status(
                            job_id, 
                            processed=i+1,
                            successful=i+1,
                            status='in_progress'
                        )
                        
                        console.print(f"  キーワード '[bold]{keyword.keyword}[/]': {saved_count}件の結果を保存")
                    else:
                        console.print(f"  キーワード '[bold]{keyword.keyword}[/]': 結果なし", style="yellow")
                        
                except Exception as e:
                    logger.error(f"キーワード '{keyword.keyword}' の検索中にエラーが発生しました: {e}")
                    console.print(f"  キーワード '[bold]{keyword.keyword}[/]': エラー - {str(e)}", style="red")
                    
                    # 検索履歴を更新
                    db.update_search_job_status(
                        job_id, 
                        processed=i+1,
                        failed=(i+1 - (i+1-1)),  # 失敗カウントを更新
                        status='in_progress',
                        error=f"キーワード '{keyword.keyword}': {str(e)}"
                    )
                    
                # 進捗を更新
                progress.update(task, advance=1)
                
        # 検索履歴を完了状態に更新
        db.update_search_job_status(job_id, status='completed')
            
        # 結果をエクスポート
        if total_results > 0:
            with console.status(f"[bold green]結果をエクスポート中... ({output_format}形式)[/]") as status:
                try:
                    output_path = exporter.export_results(
                        job_id=job_id,
                        format=output_format,
                        file_path=output_file
                    )
                    
                    if output_path:
                        console.print(f"[bold green]エクスポート成功:[/] {output_path}")
                    else:
                        console.print("[bold yellow]警告:[/] エクスポートに失敗しました。")
                        
                except Exception as e:
                    logger.error(f"エクスポート中にエラーが発生しました: {e}")
                    console.print(f"[bold red]エラー:[/] エクスポート中に問題が発生しました: {str(e)}", style="red")

@app.command("stats")
def show_statistics():
    """データベースの統計情報を表示します"""
    from core.config_manager import ConfigManager
    from core.database_manager import DatabaseManager
    from sqlalchemy import func
    from models.data_models import Keyword, EbaySearchResult, SearchHistory
    
    # 初期化
    config = ConfigManager()
    db = DatabaseManager(config.get_db_url())
    
    with db.session_scope() as session:
        # キーワード統計
        keyword_count = session.query(func.count(Keyword.id)).scalar()
        active_keywords = session.query(func.count(Keyword.id)).filter(Keyword.status == 'active').scalar()
        completed_keywords = session.query(func.count(Keyword.id)).filter(Keyword.status == 'completed').scalar()
        
        # 検索結果統計
        result_count = session.query(func.count(EbaySearchResult.id)).scalar()
        avg_price = session.query(func.avg(EbaySearchResult.price)).scalar()
        min_price = session.query(func.min(EbaySearchResult.price)).scalar()
        max_price = session.query(func.max(EbaySearchResult.price)).scalar()
        
        # ジョブ履歴
        job_count = session.query(func.count(SearchHistory.id)).scalar()
        completed_jobs = session.query(func.count(SearchHistory.id)).filter(SearchHistory.status == 'completed').scalar()
        failed_jobs = session.query(func.count(SearchHistory.id)).filter(SearchHistory.status == 'failed').scalar()
        
        # 表の作成と表示
        table = Table(title="eBay Research Tool - データベース統計")
        
        table.add_column("カテゴリ", style="cyan")
        table.add_column("項目", style="magenta")
        table.add_column("値", justify="right", style="green")
        
        # キーワード情報
        table.add_row("キーワード", "総数", str(keyword_count))
        table.add_row("キーワード", "アクティブ", str(active_keywords))
        table.add_row("キーワード", "完了", str(completed_keywords))
        
        # 検索結果情報
        table.add_row("検索結果", "総数", str(result_count))
        table.add_row("検索結果", "平均価格", f"${avg_price:.2f}" if avg_price else "N/A")
        table.add_row("検索結果", "最低価格", f"${min_price:.2f}" if min_price else "N/A")
        table.add_row("検索結果", "最高価格", f"${max_price:.2f}" if max_price else "N/A")
        
        # ジョブ情報
        table.add_row("ジョブ", "総数", str(job_count))
        table.add_row("ジョブ", "完了", str(completed_jobs))
        table.add_row("ジョブ", "失敗", str(failed_jobs))
        
        console.print(table)

@app.command("list-keywords")
def list_keywords(
    status: str = typer.Option("active", "--status", "-s", help="表示するキーワードのステータス（active, completed, all）"),
    limit: int = typer.Option(20, "--limit", "-l", help="表示するキーワードの最大数")
):
    """保存されているキーワードの一覧を表示します"""
    from core.config_manager import ConfigManager
    from core.database_manager import DatabaseManager
    from models.data_models import Keyword
    
    # 初期化
    config = ConfigManager()
    db = DatabaseManager(config.get_db_url())
    
    with db.session_scope() as session:
        # クエリ構築
        query = session.query(Keyword)
        
        if status.lower() != "all":
            query = query.filter(Keyword.status == status)
            
        query = query.order_by(Keyword.id).limit(limit)
        keywords = query.all()
        
        if not keywords:
            console.print(f"[bold yellow]該当するキーワードがありません。(ステータス: {status})[/]")
            return
            
        # 表の作成と表示
        table = Table(title=f"キーワード一覧 (ステータス: {status})")
        table.add_column("ID", justify="right", style="cyan")
        table.add_column("キーワード", style="green")
        table.add_column("カテゴリ", style="magenta")
        table.add_column("ステータス", style="blue")
        table.add_column("最終検索日時", style="yellow")
        
        for keyword in keywords:
            last_searched = keyword.last_searched_at.strftime("%Y-%m-%d %H:%M") if keyword.last_searched_at else "未検索"
            table.add_row(
                str(keyword.id),
                keyword.keyword,
                keyword.category or "-",
                keyword.status,
                last_searched
            )
            
        console.print(table)

@app.command("clean-all")
def clean_database(
    confirm: bool = typer.Option(False, "--confirm", "-y", help="確認なしで実行")
):
    """データベースをクリーンアップします（すべてのデータを削除）"""
    from core.config_manager import ConfigManager
    from core.database_manager import DatabaseManager
    from models.data_models import Base
    
    if not confirm:
        sure = typer.confirm("すべてのデータが削除されます。本当に続行しますか？")
        if not sure:
            console.print("キャンセルしました。")
            raise typer.Exit(0)
    
    # 初期化
    config = ConfigManager()
    db = DatabaseManager(config.get_db_url())
    
    with console.status("[bold red]データベースを初期化中...[/]") as status:
        # テーブルをすべて削除して再作成
        Base.metadata.drop_all(db.engine)
        Base.metadata.create_all(db.engine)
        
        console.print("[bold green]データベースを初期化しました。[/]")

def main():
    app()

if __name__ == "__main__":
    main()
