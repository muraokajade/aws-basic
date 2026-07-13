"""
マージロジックの単体テスト

テスト対象:
- _is_valid_value
- _merge_ocr_results
- _merge_existing_buildings
"""
import pytest
from ocr_core.services import _is_valid_value, _merge_ocr_results, _merge_existing_buildings


# =============================================================================
# _is_valid_value テスト
# =============================================================================


class TestIsValidValue:
    def test_none_は無効(self):
        assert _is_valid_value(None) is False

    def test_空文字は無効(self):
        assert _is_valid_value("") is False
        assert _is_valid_value("   ") is False

    def test_プレースホルダーは無効(self):
        assert _is_valid_value("---") is False
        assert _is_valid_value("－－－") is False
        assert _is_valid_value("記載なし") is False
        assert _is_valid_value("確認できない") is False
        assert _is_valid_value("不明") is False

    def test_有効な文字列(self):
        assert _is_valid_value("東京都") is True
        assert _is_valid_value("RC造") is True

    def test_bool_trueは有効(self):
        assert _is_valid_value(True) is True

    def test_bool_falseは無効(self):
        assert _is_valid_value(False) is False

    def test_空リストは無効(self):
        assert _is_valid_value([]) is False

    def test_要素ありリストは有効(self):
        assert _is_valid_value(["item"]) is True

    def test_数値は有効(self):
        assert _is_valid_value(0) is True
        assert _is_valid_value(123) is True


# =============================================================================
# _merge_ocr_results テスト
# =============================================================================


class TestMergeOcrResults:
    def test_単一結果はそのまま返す(self):
        single = {"property_name": "テスト物件", "price_raw": "5000万円"}
        result = _merge_ocr_results([single])
        assert result is single

    def test_通常文字列は長い方を優先(self):
        results = [
            {"address_display": "東京都"},
            {"address_display": "東京都渋谷区神宮前1-2-3"},
        ]
        merged = _merge_ocr_results(results)
        assert merged["address_display"] == "東京都渋谷区神宮前1-2-3"

    def test_先に見つかった有効値を基本採用_文字列以外(self):
        results = [
            {"price_is_consultation": True},
            {"price_is_consultation": True},
        ]
        merged = _merge_ocr_results(results)
        assert merged["price_is_consultation"] is True

    def test_null値はスキップして有効値を採用(self):
        results = [
            {"property_name": None, "price_raw": "5000万円"},
            {"property_name": "テスト物件", "price_raw": None},
        ]
        merged = _merge_ocr_results(results)
        assert merged["property_name"] == "テスト物件"
        assert merged["price_raw"] == "5000万円"

    def test_remarks_は重複除去して改行結合(self):
        results = [
            {"remarks": "備考A"},
            {"remarks": "備考B"},
            {"remarks": "備考A"},  # 重複
        ]
        merged = _merge_ocr_results(results)
        assert merged["remarks"] == "備考A\n備考B"

    def test_remarks_全てnullならNone(self):
        results = [
            {"remarks": None},
            {"remarks": ""},
        ]
        merged = _merge_ocr_results(results)
        assert merged["remarks"] is None

    def test_unreadable_segments_は重複除去してリスト結合(self):
        results = [
            {"unreadable_segments": ["セグメントA", "セグメントB"]},
            {"unreadable_segments": ["セグメントB", "セグメントC"]},
        ]
        merged = _merge_ocr_results(results)
        assert merged["unreadable_segments"] == ["セグメントA", "セグメントB", "セグメントC"]

    def test_extraction_notes_は結合(self):
        results = [
            {"extraction_notes": "ノート1"},
            {"extraction_notes": "ノート2"},
        ]
        merged = _merge_ocr_results(results)
        assert merged["extraction_notes"] == "ノート1。ノート2"

    def test_extraction_notes_全て無効ならデフォルトメッセージ(self):
        results = [
            {"extraction_notes": None},
            {"extraction_notes": ""},
        ]
        merged = _merge_ocr_results(results)
        assert merged["extraction_notes"] == "複数画像を並列解析して統合"

    def test_existing_buildings_は全画像分結合して最大5件(self):
        results = [
            {"existing_buildings": [{"type": "A"}, {"type": "B"}, {"type": "C"}]},
            {"existing_buildings": [{"type": "D"}, {"type": "E"}, {"type": "F"}]},
        ]
        merged = _merge_ocr_results(results)
        assert len(merged["existing_buildings"]) == 5
        assert merged["existing_buildings"][0] == {"type": "A"}
        assert merged["existing_buildings"][4] == {"type": "E"}

    def test_プレースホルダー値はスキップ(self):
        results = [
            {"building_structure": "---"},
            {"building_structure": "RC造"},
        ]
        merged = _merge_ocr_results(results)
        assert merged["building_structure"] == "RC造"

    def test_3結果のマージ(self):
        results = [
            {"property_name": "物件A", "transport_1_raw": "短い"},
            {"property_name": None, "transport_1_raw": "JR山手線 渋谷駅 徒歩5分"},
            {"property_name": "物件A長い名前", "transport_1_raw": None},
        ]
        merged = _merge_ocr_results(results)
        # 文字列は長い方を優先
        assert merged["property_name"] == "物件A長い名前"
        assert merged["transport_1_raw"] == "JR山手線 渋谷駅 徒歩5分"


# =============================================================================
# _merge_existing_buildings テスト
# =============================================================================


class TestMergeExistingBuildings:
    def test_空リスト(self):
        result = _merge_existing_buildings([{"existing_buildings": []}])
        assert result == []

    def test_キーなし(self):
        result = _merge_existing_buildings([{"other_key": "value"}])
        assert result == []

    def test_最大5件で切り詰め(self):
        buildings = [{"id": i} for i in range(10)]
        result = _merge_existing_buildings([{"existing_buildings": buildings}])
        assert len(result) == 5

    def test_複数結果から結合(self):
        results = [
            {"existing_buildings": [{"id": 1}, {"id": 2}]},
            {"existing_buildings": [{"id": 3}]},
        ]
        result = _merge_existing_buildings(results)
        assert len(result) == 3
        assert result[0] == {"id": 1}
        assert result[2] == {"id": 3}

    def test_dict以外の要素は除外(self):
        results = [
            {"existing_buildings": [{"id": 1}, "invalid", None, {"id": 2}]},
        ]
        result = _merge_existing_buildings(results)
        assert len(result) == 2
