"""
画像OCR共通フィールドマッピングユーティリティ

パーサー関数・バリデーション関数を集約する。
独立OCR PoC用: Django依存なし。
"""
import re
import logging
from typing import Any, Optional

logger = logging.getLogger(__name__)

# =============================================================================
# 無効値パターン（OCRが返すプレースホルダー）
# =============================================================================

INVALID_OCR_PATTERNS = ['---', '－－－', '−−−', '不明', '未定', '該当なし', 'N/A', 'n/a', '-', '－']


# =============================================================================
# 有効値判定
# =============================================================================

def is_valid_ocr_value(value: Any) -> bool:
    """
    OCR抽出値が有効かどうかを判定する

    None・空文字・プレースホルダー（'---' 等）を無効とみなす。
    bool 型は True/False どちらも有効とみなす。

    Args:
        value: チェックする値

    Returns:
        bool: 有効な値の場合 True
    """
    if value is None:
        return False

    if isinstance(value, bool):
        return True

    if isinstance(value, str):
        stripped = value.strip()
        return stripped != '' and stripped not in INVALID_OCR_PATTERNS

    return True


# =============================================================================
# 数値クリーニング
# =============================================================================

def clean_numeric_value(value: str) -> str:
    """
    数値文字列からカンマ・円記号・スペース等の不要な文字を除去する

    Args:
        value: 変換前の値（例: "1,234,567円"）

    Returns:
        str: クリーンな数値文字列（例: "1234567"）
    """
    if not value:
        return ''

    cleaned = re.sub(r'[,、円\s]', '', str(value))
    match = re.search(r'[\d.]+', cleaned)
    return match.group(0) if match else ''


def extract_numeric_with_comma(raw_value: str) -> Optional[str]:
    """
    カンマ区切りの数値を抽出してカンマを除去する

    Args:
        raw_value: 抽出元の文字列

    Returns:
        Optional[str]: カンマを除去した数値文字列。見つからない場合は None
    """
    if not raw_value:
        return None
    match = re.search(r'([\d,]+)', raw_value)
    return match.group(1).replace(',', '') if match else None


# =============================================================================
# 日付パーサー
# =============================================================================

def parse_date_raw(date_raw: str) -> str:
    """
    日付のraw文字列を YYYY-MM-DD 形式に変換する

    対応フォーマット:
        - 令和5年3月15日 → 2023-03-15
        - 平成10年12月   → 1998-12-01
        - R5.3.15        → 2023-03-15
        - 2023年3月15日  → 2023-03-15
        - 2023/3/15      → 2023-03-15
        - 2023-03-15     → 2023-03-15（そのまま）

    Args:
        date_raw: 日付の原文

    Returns:
        str: YYYY-MM-DD 形式の日付文字列。変換できない場合は空文字列
    """
    if not date_raw:
        return ''

    # すでに YYYY-MM-DD 形式の場合はそのまま返す
    if re.match(r'^\d{4}-\d{2}-\d{2}$', date_raw):
        return date_raw

    # 和暦変換テーブル（元号の開始年 - 1）
    era_map = {
        '令和': 2018,
        'R':   2018,
        '平成': 1988,
        'H':   1988,
        '昭和': 1925,
        'S':   1925,
    }

    year, month, day = None, 1, 1

    # パターン1: 令和5年3月15日
    match = re.search(r'(令和|平成|昭和|R|H|S)\s*(\d+)\s*年\s*(\d+)\s*月\s*(\d+)?\s*日?', date_raw)
    if match:
        era = match.group(1)
        year = era_map.get(era, 0) + int(match.group(2))
        month = int(match.group(3))
        if match.group(4):
            day = int(match.group(4))

    # パターン2: R5.3.15 or R5/3/15
    if not year:
        match = re.search(r'(R|H|S)\s*(\d+)\s*[./]\s*(\d+)\s*[./]?\s*(\d+)?', date_raw)
        if match:
            era = match.group(1)
            year = era_map.get(era, 0) + int(match.group(2))
            month = int(match.group(3))
            if match.group(4):
                day = int(match.group(4))

    # パターン3: 2023年3月15日
    if not year:
        match = re.search(r'(\d{4})\s*年\s*(\d+)\s*月\s*(\d+)?\s*日?', date_raw)
        if match:
            year = int(match.group(1))
            month = int(match.group(2))
            if match.group(3):
                day = int(match.group(3))

    # パターン4: 2023/3/15 or 2023-03-15
    if not year:
        match = re.search(r'(\d{4})\s*[/\-]\s*(\d+)\s*[/\-]?\s*(\d+)?', date_raw)
        if match:
            year = int(match.group(1))
            month = int(match.group(2))
            if match.group(3):
                day = int(match.group(3))

    if year and 1900 <= year <= 2100:
        try:
            return f"{year:04d}-{month:02d}-{day:02d}"
        except Exception:
            return ''

    return ''


def parse_construction_date_raw(date_raw: str) -> str:
    """
    築年月のraw文字列を YYYY-MM 形式に変換する

    Args:
        date_raw: 築年月の原文（例: "平成10年3月"）

    Returns:
        str: YYYY-MM 形式の文字列（例: "1998-03"）
    """
    full_date = parse_date_raw(date_raw)
    return full_date[:7] if full_date else ''


# =============================================================================
# 抽出品質チェック
# =============================================================================

# 最低限必要な抽出フィールド数（デフォルト）
DEFAULT_MIN_EXTRACTED_FIELDS = 3


def validate_extraction_quality(
    data: dict,
    min_fields: int = DEFAULT_MIN_EXTRACTED_FIELDS,
    exclude_internal: bool = False,
) -> bool:
    """
    OCR抽出データの品質をチェックする

    有効なフィールド数が min_fields 以上であれば品質十分と判定する。
    bool型（is_vacantなど）は True/False どちらも有効とみなし、
    数値 0 も有効な値として扱う（例: 敷金0円）。

    Args:
        data: 正規化されたデータ
        min_fields: 最低限必要なフィールド数
        exclude_internal: True の場合、'_' で始まる内部フィールドを除外する

    Returns:
        bool: 品質が十分な場合 True
    """
    filled_count = sum(
        1 for k, v in data.items()
        if (not exclude_internal or not k.startswith('_'))
        and v is not None and v != ''
    )
    return filled_count >= min_fields
