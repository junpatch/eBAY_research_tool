import json
import os
import pytest
from pathlib import Path

# フィクスチャファイルのパスを設定
FIXTURES_DIR = Path(__file__).parent / "fixtures" / "ebay_responses"

def load_fixture(filename):
    """フィクスチャファイルを読み込む"""
    with open(FIXTURES_DIR / filename, "r", encoding="utf-8") as f:
        return json.load(f)

class TestEbayApiResponses:
    def test_search_result_parsing(self):
        """基本的な検索結果のパース処理をテスト"""
        data = load_fixture("search_result_sample.json")
        assert isinstance(data, list)
        assert len(data) == 3
        
        # 最初の商品のデータ構造を検証
        item = data[0]
        assert isinstance(item["item_id"], str)
        assert isinstance(item["price"], (int, float))
        assert isinstance(item["shipping_price"], (int, float))
        assert isinstance(item["seller_rating"], (int, float))
        assert isinstance(item["seller_feedback_count"], int)

    def test_item_details_parsing(self):
        """商品詳細情報のパース処理をテスト"""
        data = load_fixture("item_details_sample.json")
        
        # 基本情報の検証
        assert data["item_id"] == "123456789012"
        assert isinstance(data["price"], dict)
        assert isinstance(data["shipping"], dict)
        assert isinstance(data["seller"], dict)
        
        # ネストされた情報の検証
        assert len(data["categories"]) == 2
        assert len(data["images"]) == 3
        assert isinstance(data["item_specifics"], dict)
        assert isinstance(data["return_policy"], dict)

    def test_paginated_search_result(self):
        """ページネーション付き検索結果のパース処理をテスト"""
        data = load_fixture("paginated_search_result.json")
        
        # ページネーション情報の検証
        assert "pagination" in data
        pagination = data["pagination"]
        assert pagination["total_entries"] > 0
        assert pagination["current_page"] == 1
        assert pagination["has_next_page"] is True
        
        # 商品リストの検証
        assert len(data["items"]) > 0
        
        # フィルター情報の検証
        assert "filters" in data
        assert "applied_filters" in data["filters"]
        assert "available_filters" in data["filters"]

    def test_error_responses(self):
        """エラーレスポンスのパース処理をテスト"""
        data = load_fixture("error_response_samples.json")
        
        # 各種エラーパターンの検証
        assert "invalid_api_key" in data
        assert "rate_limit_exceeded" in data
        assert "invalid_search_params" in data
        assert "service_unavailable" in data
        
        # エラー構造の検証
        for error_type in data.values():
            assert "error" in error_type
            assert "code" in error_type["error"]
            assert "message" in error_type["error"]
            assert "severity" in error_type["error"]
            assert "category" in error_type["error"]

    def test_edge_cases(self):
        """エッジケースのパース処理をテスト"""
        data = load_fixture("edge_cases_sample.json")
        
        # 空の検索結果
        assert len(data["empty_result"]["items"]) == 0
        
        # 欠損フィールド
        missing = data["missing_fields"]
        assert missing["price"] is None
        assert missing["shipping_price"] is None
        
        # 特殊文字
        special = data["special_characters"]
        assert "&<>\"'" in special["title"]
        assert "\n" in special["description"]
        assert "\t" in special["description"]
        
        # 極端な値
        extreme = data["extreme_values"]
        assert extreme["price"] > 999999
        assert extreme["shipping_price"] < 0.1
        assert extreme["stock_quantity"] > 999998
        
        # Unicode文字
        unicode = data["unicode_content"]
        assert "Multi-language" in unicode["title"]
        assert "中文" in unicode["title"]
        assert "日本語" in unicode["description"] 