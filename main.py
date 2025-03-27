#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
eBay Research Tool - メインアプリケーションエントリーポイント

このスクリプトは、eBayリサーチツールのメインエントリーポイントとして機能します。
CLIからコマンドを実行する際のエントリーポイントとなります。

使用例:
    $ python main.py import --file keywords.csv
    $ python main.py search --limit 10 --format csv --output results.csv
    $ python main.py stats
"""

import sys
import os
import logging
from pathlib import Path

# アプリケーションのルートディレクトリをシステムパスに追加
app_root = Path(__file__).parent
sys.path.append(str(app_root))

from interfaces.cli_interface import app
from core.logger_manager import LoggerManager

def setup_application():
    """
    アプリケーションの初期設定を行います。
    必要なディレクトリの作成や、初期設定ファイルの確認などを行います。
    """
    # 必要なディレクトリの作成
    data_dir = app_root / 'data'
    logs_dir = app_root / 'logs'
    output_dir = app_root / 'output'
    
    for directory in [data_dir, logs_dir, output_dir]:
        directory.mkdir(exist_ok=True)
        
    # ロガーの初期化
    logger = LoggerManager().get_logger()
    logger.info("eBay Research Tool を起動しています...")
    
    # 設定ファイルの存在確認
    config_path = app_root / 'config' / 'config.yaml'
    if not config_path.exists():
        logger.error(f"設定ファイルが見つかりません: {config_path}")
        print(f"エラー: 設定ファイルが見つかりません: {config_path}")
        sys.exit(1)
    
    return logger

def main():
    """
    メインエントリーポイント
    """
    # アプリケーションのセットアップ
    logger = setup_application()
    
    try:
        # Typerアプリを実行
        app()
    except Exception as e:
        logger.exception(f"予期せぬエラーが発生しました: {e}")
        print(f"エラー: {str(e)}")
        sys.exit(1)

if __name__ == "__main__":
    main()
