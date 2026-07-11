"""
フィールドマッピングと値変換

独立OCR PoC用: Django/DB/cache依存を除去。
property_type は overview のみ対応。
DBマスター照合はスキップし、エイリアス変換のみ適用する。
"""

from decimal import Decimal, ROUND_DOWN
from typing import Optional, Dict, Any, List
import re
import logging

from ocr_core.field_mapping_utils import (
    parse_date_raw,
    parse_construction_date_raw,
    extract_numeric_with_comma as _extract_numeric_with_comma,
    is_valid_ocr_value as _is_valid_ocr_value,
)

logger = logging.getLogger(__name__)

# =============================================================================
# 定数定義
# =============================================================================

MAX_TRANSPORT_COUNT = 3
MAX_ZONING_COUNT = 3
MAX_ROAD_COUNT = 2

# =============================================================================
# エイリアス定義（表記ゆれ・略称 → 正式名称）
# =============================================================================

USE_DISTRICT_ALIASES = {
    '第1種低層住居専用地域': '第一種低層住居専用地域',
    '第2種低層住居専用地域': '第二種低層住居専用地域',
    '第1種中高層住居専用地域': '第一種中高層住居専用地域',
    '第2種中高層住居専用地域': '第二種中高層住居専用地域',
    '第1種住居地域': '第一種住居地域',
    '第2種住居地域': '第二種住居地域',
    '1低': '第一種低層住居専用地域',
    '2低': '第二種低層住居専用地域',
    '1中高': '第一種中高層住居専用地域',
    '2中高': '第二種中高層住居専用地域',
    '1住': '第一種住居地域',
    '2住': '第二種住居地域',
    '準住': '準住居地域',
    '田住': '田園住居地域',
    '近商': '近隣商業地域',
    '商業': '商業地域',
    '準工': '準工業地域',
    '工業': '工業地域',
    '工専': '工業専用地域',
    '調整': '市街化調整区域',
}

BUILDING_STRUCTURE_ALIASES = {
    '木造': '木造',
    '鉄骨造': '鉄骨造（S造）',
    'S造': '鉄骨造（S造）',
    '鉄筋コンクリート造': '鉄筋コンクリート造（RC造）',
    'RC造': '鉄筋コンクリート造（RC造）',
    '鉄骨鉄筋コンクリート造': '鉄骨鉄筋コンクリート造（SRC造）',
    'SRC造': '鉄骨鉄筋コンクリート造（SRC造）',
}

BUILDING_STRUCTURE_PATTERNS = [
    ('鉄骨鉄筋コンクリート', '鉄骨鉄筋コンクリート造（SRC造）'),
    ('SRC', '鉄骨鉄筋コンクリート造（SRC造）'),
    ('鉄筋コンクリート', '鉄筋コンクリート造（RC造）'),
    ('RC', '鉄筋コンクリート造（RC造）'),
    ('鉄骨', '鉄骨造（S造）'),
    ('S造', '鉄骨造（S造）'),
    ('木造', '木造'),
]

BUILDING_TYPE_ALIASES = {
    '駐車場': '車庫',
    '一棟ビル': '事務所',
    '一棟マンション': '共同住宅',
    '一棟アパート': '共同住宅',
    '一棟店舗': '店舗',
    '一棟倉庫': '倉庫',
    '一棟工場': '工場',
    'ビル': '事務所',
    'マンション': '共同住宅',
    'アパート': '共同住宅',
    '賃貸マンション': '共同住宅',
    '分譲マンション': '共同住宅',
    '戸建て': '居宅',
    '戸建': '居宅',
    '一戸建て': '居宅',
    '一戸建': '居宅',
    '住宅': '居宅',
    '一軒家': '居宅',
    '木造住宅': '居宅',
    '駐輪場': '自転車置場',
    'ガレージ': '車庫',
    '貸倉庫': '倉庫',
    '貸店舗': '店舗',
    '貸事務所': '事務所',
}

INSPECTION_CERTIFICATE_ALIASES = {
    '新築時：有、増築時：無': '有',
    '新築時：有': '有',
    '新築時:有': '有',
    '新築時有': '有',
    '有り': '有',
    'あり': '有',
    '○': '有',
    '新築時：無': '無',
    '新築時:無': '無',
    '新築時無': '無',
    '無し': '無',
    'なし': '無',
    '×': '無',
    '確認中': '不明',
    '未確認': '不明',
}


# =============================================================================
# DBマスター照合（PoCではスタブ：空dictを返す）
# =============================================================================

def _get_master_mapping(category: str) -> dict:
    """
    PoCではDBなし。空dictを返し、マスター照合をスキップする。
    """
    return {}


# =============================================================================
# 値変換関数
# =============================================================================

def _apply_alias(value: str, aliases: dict, patterns: list = None) -> str:
    """
    エイリアス変換を適用
    """
    if value in aliases:
        return aliases[value]
    normalized = value.replace('(', '（').replace(')', '）')
    if normalized != value and normalized in aliases:
        return aliases[normalized]
    if patterns:
        for pattern, replacement in patterns:
            if pattern in value:
                return replacement
    return value


def _convert_with_master(value: str, category: str, aliases: dict = None, patterns: list = None) -> str:
    """
    エイリアス変換 + DBマスター照合でIDに変換
    PoCではDBなしのため、エイリアス変換のみ適用する。
    """
    if not value:
        return value
    if aliases or patterns:
        value = _apply_alias(value, aliases or {}, patterns)
    mapping = _get_master_mapping(category)
    return mapping.get(value, value)


def _normalize_orientation(value: str) -> str:
    """開口向の表記ゆれを8方位に正規化"""
    if not value:
        return value
    orientations = ['北東', '南東', '南西', '北西', '北', '東', '南', '西']
    cleaned = value.strip()
    for orientation in orientations:
        if orientation in cleaned:
            return orientation
    return value


def convert_field_value(field_name: str, value: str) -> str:
    """フィールド名に応じて値を変換する"""
    if not value:
        return value

    if field_name.startswith('transport_station'):
        bracket_match = re.search(r'「(.+?)」', value)
        if bracket_match:
            value = bracket_match.group(1)
        if value.endswith('駅'):
            return value[:-1]
        return value

    if field_name.startswith('land_category'):
        return _convert_with_master(value, 'land_category')

    if field_name.startswith('use_district'):
        return _convert_with_master(value, 'use_district', USE_DISTRICT_ALIASES)

    if field_name.startswith('fire_district') or field_name.startswith('fire_zone'):
        return _convert_with_master(value, 'fire_district')

    if field_name == 'building_type' or re.match(r'^building_type_\d+(_\d+)?$', field_name):
        value = _apply_alias(value, BUILDING_TYPE_ALIASES)
        return value

    if field_name == 'building_structure' or field_name == 'planned_building_structure':
        return _convert_with_master(value, 'building_structure', BUILDING_STRUCTURE_ALIASES, BUILDING_STRUCTURE_PATTERNS)

    if field_name == 'inspection_certificate':
        result = _apply_alias(value, INSPECTION_CERTIFICATE_ALIASES)
        if result != value:
            return result
        return _parse_inspection_certificate(value)

    if field_name == 'opening_direction':
        return _normalize_orientation(value)

    return value


def convert_property_data(property_data: dict) -> dict:
    """抽出された物件データをフォームフィールドに適した形式に変換"""
    converted_data = {}
    for field_name, value in property_data.items():
        if value:
            converted_data[field_name] = convert_field_value(field_name, value)
        else:
            converted_data[field_name] = value
    return converted_data


# =============================================================================
# Phase 2: rawデータのパーサー（後処理）
# =============================================================================

def parse_transport_raw(transport_raw: str) -> Dict[str, str]:
    """交通情報のraw文字列を分解"""
    result = {"line": "", "station": "", "minutes": ""}
    if not transport_raw:
        return result

    def clean_station_name(station: str) -> str:
        if not station:
            return station
        if station.endswith('駅'):
            station = station[:-1]
        noise_patterns = [
            r'\s*バス.*$', r'\s*分.*$', r'\s*歩.*$',
            r'\s*徒歩.*$', r'\s*\d+m.*$', r'\s*\d+km.*$', r'\s*車.*$',
        ]
        for pattern in noise_patterns:
            station = re.sub(pattern, '', station)
        return station.strip()

    pattern1 = r'(.+?)「(.+?)」駅?\s*徒歩\s*約?\s*(\d+)\s*分'
    match = re.search(pattern1, transport_raw)
    if match:
        result["line"] = match.group(1).strip()
        result["station"] = clean_station_name(match.group(2).strip())
        result["minutes"] = match.group(3)
        return result

    pattern2 = r'(.+?)\s+(.+?)駅\s*徒歩\s*約?\s*(\d+)\s*分'
    match = re.search(pattern2, transport_raw)
    if match:
        result["line"] = match.group(1).strip()
        result["station"] = clean_station_name(match.group(2).strip())
        result["minutes"] = match.group(3)
        return result

    pattern3 = r'(.+?線)\s+([^\s]+)\s+徒歩\s*約?\s*(\d+)\s*分'
    match = re.search(pattern3, transport_raw)
    if match:
        result["line"] = match.group(1).strip()
        result["station"] = clean_station_name(match.group(2).strip())
        result["minutes"] = match.group(3)
        return result

    pattern5 = r'(.+?)\s+(.+?)\s+徒歩\s*約?\s*(\d+)\s*分'
    match = re.search(pattern5, transport_raw)
    if match:
        result["line"] = match.group(1).strip()
        result["station"] = clean_station_name(match.group(2).strip())
        result["minutes"] = match.group(3)
        return result

    minutes_match = re.search(r'徒歩\s*約?\s*(\d+)\s*分', transport_raw)
    if minutes_match:
        result["minutes"] = minutes_match.group(1)

    station_match = re.search(r'「(.+?)」|(.+?)駅', transport_raw)
    if station_match:
        station = (station_match.group(1) or station_match.group(2) or "").strip()
        result["station"] = clean_station_name(station)

    if not result["line"]:
        line_match = re.search(r'(.+?線)', transport_raw)
        if line_match:
            result["line"] = line_match.group(1).strip()

    return result


def parse_area_raw(area_raw: str) -> Dict[str, str]:
    """面積情報のraw文字列を分解"""
    result = {"value": "", "type": ""}
    if not area_raw:
        return result
    value_match = re.search(r'([\d,]+\.?\d*)\s*[㎡m²]?', area_raw)
    if value_match:
        result["value"] = value_match.group(1).replace(',', '')
    if '公簿' in area_raw or '登記' in area_raw:
        result["type"] = "official"
    elif '実測' in area_raw:
        result["type"] = "measured"
    return result


def parse_road_raw(road_raw: str) -> Dict[str, str]:
    """道路情報のraw文字列を分解"""
    result = {"direction": "", "width": "", "type": ""}
    if not road_raw:
        return result
    road_raw_nospace = re.sub(r'[\s\u3000]+', '', road_raw)
    road_raw_nospace = re.sub(r'西西', '南西', road_raw_nospace)
    road_raw_nospace = re.sub(r'東東', '北東', road_raw_nospace)
    direction_match = re.search(r'(北東|北西|南東|南西|北|南|東|西)', road_raw_nospace)
    if direction_match:
        result["direction"] = direction_match.group(1)
    range_match = re.search(r'約?\s*[\d.]+\s*[〜~～\-]\s*([\d.]+)\s*[mMｍ]', road_raw)
    if range_match:
        result["width"] = range_match.group(1)
    else:
        width_match = re.search(r'約?\s*([\d.]+)\s*[mMｍ]', road_raw)
        if width_match:
            result["width"] = width_match.group(1)
    if '公道' in road_raw:
        result["type"] = "公道"
    elif '私道' in road_raw:
        result["type"] = "私道"
    elif '位置指定' in road_raw:
        result["type"] = "位置指定道路"
    return result


def parse_price_raw(price_raw: str) -> Dict[str, Any]:
    """価格のraw文字列を分解"""
    result = {
        "value": None,
        "is_consultation": False,
        "is_unknown": False,
        "is_bid": False,
        "is_negotiation": False,
    }
    if not price_raw:
        return result
    if '相談' in price_raw:
        result["is_consultation"] = True
        return result
    if '不明' in price_raw or '未定' in price_raw:
        result["is_unknown"] = True
        return result
    if '入札' in price_raw:
        result["is_bid"] = True
        return result
    if '協議' in price_raw:
        result["is_negotiation"] = True
        return result

    match = re.search(r'(\d+)\s*億\s*([\d,]+)?\s*万?\s*円?', price_raw)
    if match:
        try:
            oku = int(match.group(1)) * 100000000
            man_str = match.group(2)
            man = int(man_str.replace(',', '')) * 10000 if man_str else 0
            result["value"] = oku + man
            return result
        except (ValueError, TypeError):
            return result

    match = re.search(r'([\d,]+)\s*万\s*円?', price_raw)
    if match:
        try:
            result["value"] = int(match.group(1).replace(',', '')) * 10000
            return result
        except (ValueError, TypeError):
            return result

    match = re.search(r'([\d,]+)\s*円?', price_raw)
    if match:
        try:
            result["value"] = int(match.group(1).replace(',', ''))
            return result
        except (ValueError, TypeError):
            return result

    return result


def _extract_numeric_value(raw_value: str, pattern: str = r'(\d+)') -> Optional[str]:
    """文字列から数値を抽出"""
    if not raw_value:
        return None
    match = re.search(pattern, raw_value)
    return match.group(1) if match else None


def parse_floor_area_raw(raw_value: str) -> Optional[List[Dict[str, str]]]:
    """登記簿形式の階数別面積文字列をパースする"""
    if not raw_value:
        return None
    lines = [line.strip() for line in str(raw_value).split('\n') if line.strip()]
    lines = lines[:20]
    if not lines:
        return None

    floor_area_colon_pattern = re.compile(
        r'((?:地下)?\d+階(?:部分)?)\s*([\d]+)[:：]([\d]+)'
    )
    floor_area_dot_pattern = re.compile(
        r'((?:地下)?\d+階(?:部分)?)\s*([\d]+\.[\d]+)'
    )
    numeric_only_pattern = re.compile(r'^[\d]+\.[\d]+$')

    results = []
    for line in lines:
        match = floor_area_colon_pattern.search(line)
        if match:
            floor_number = match.group(1)
            area_value = f'{match.group(2)}.{match.group(3)}'
            results.append({'floor_number': floor_number, 'area_value': area_value})
            continue
        match = floor_area_dot_pattern.search(line)
        if match:
            results.append({'floor_number': match.group(1), 'area_value': match.group(2)})
            continue

    if results:
        return results

    numeric_results = []
    colon_only_pattern = re.compile(r'^([\d]+)[:：]([\d]+)$')
    has_colon = False
    for line in lines:
        if numeric_only_pattern.match(line):
            numeric_results.append({'floor_number': '', 'area_value': line})
        else:
            colon_match = colon_only_pattern.match(line)
            if colon_match:
                area_value = f'{colon_match.group(1)}.{colon_match.group(2)}'
                numeric_results.append({'floor_number': '', 'area_value': area_value})
                has_colon = True

    if len(numeric_results) == len(lines) and (has_colon or len(lines) >= 2):
        return numeric_results

    return None


def _parse_inspection_certificate(value: str) -> str:
    """検査済証の複雑なOCR文字列から有/無/不明を判定"""
    if not value:
        return value
    match = re.search(r'新築時[）\)]?\s*[：:]*\s*(有|無)', value)
    if match:
        return match.group(1)
    if '有' in value and '無' not in value:
        return '有'
    if '無' in value and '有' not in value:
        return '無'
    return value


def _normalize_renovation(value: str) -> str:
    """リノベーション情報を「有」「無」に正規化"""
    if not value:
        return ''
    v = str(value).strip()
    if v in ('有', '無'):
        return v
    negative_keywords = ['無し', 'なし', 'ナシ', '未実施', '未施工', '未改修']
    for keyword in negative_keywords:
        if keyword in v:
            return '無'
    positive_keywords = ['リノベ', 'リフォーム', '改修', '改装', '修繕済']
    for keyword in positive_keywords:
        if keyword in v:
            return '有'
    return v


# 建物種類の分割用デリミタパターン
_BUILDING_TYPE_DELIMITERS = re.compile(r'[・、，,\s　]+')


# =============================================================================
# normalize_ocr_data のヘルパー関数
# =============================================================================

def _normalize_direct_fields(ocr_data: dict, normalized: dict) -> None:
    """直接コピーするフィールドを正規化"""
    direct_fields = [
        'property_name', 'info_source', 'info_source_contact',
        'address_display', 'address_lot',
        'building_structure', 'planned_building_structure',
        'land_rights', 'management_form',
        'remarks', 'inspection_certificate',
        'floor_plan', 'opening_direction',
    ]
    for field in direct_fields:
        if field in ocr_data and ocr_data[field] and _is_valid_ocr_value(ocr_data[field]):
            normalized[field] = ocr_data[field]

    if ocr_data.get('total_units') and _is_valid_ocr_value(ocr_data['total_units']):
        value = _extract_numeric_value(ocr_data['total_units'])
        if value:
            normalized['total_units'] = value

    if ocr_data.get('total_floors') and _is_valid_ocr_value(ocr_data['total_floors']):
        normalized['total_floors'] = ocr_data['total_floors']

    if ocr_data.get('floor_number') and _is_valid_ocr_value(ocr_data['floor_number']):
        normalized['structure_floor'] = ocr_data['floor_number']

    if ocr_data.get('land_category') and _is_valid_ocr_value(ocr_data['land_category']):
        normalized['land_category_1'] = ocr_data['land_category']
    elif ocr_data.get('land_category_1') and _is_valid_ocr_value(ocr_data['land_category_1']):
        normalized['land_category_1'] = ocr_data['land_category_1']

    if ocr_data.get('opening_direction') and _is_valid_ocr_value(ocr_data['opening_direction']):
        normalized['opening_direction'] = ocr_data['opening_direction']

    if ocr_data.get('renovation_raw') and _is_valid_ocr_value(ocr_data['renovation_raw']):
        normalized['renovation'] = _normalize_renovation(ocr_data['renovation_raw'])


def _normalize_dates(ocr_data: dict, normalized: dict) -> None:
    """日付フィールドを正規化"""
    if ocr_data.get('info_date_raw') and _is_valid_ocr_value(ocr_data['info_date_raw']):
        normalized['info_date'] = parse_date_raw(ocr_data['info_date_raw'])
    if ocr_data.get('construction_date_raw') and _is_valid_ocr_value(ocr_data['construction_date_raw']):
        normalized['construction_date'] = parse_construction_date_raw(ocr_data['construction_date_raw'])


def _normalize_price(ocr_data: dict, normalized: dict) -> None:
    """価格フィールドを正規化"""
    price_has_special_flag = False
    if ocr_data.get('price_is_unknown') is True:
        normalized['price_unknown'] = 'true'
        price_has_special_flag = True
    if ocr_data.get('price_is_consultation') is True:
        normalized['price_consultation'] = 'true'
        price_has_special_flag = True
    if ocr_data.get('price_is_bid') is True:
        normalized['price_bid'] = 'true'
        price_has_special_flag = True
    if ocr_data.get('price_is_negotiation') is True:
        normalized['price_negotiation'] = 'true'
        price_has_special_flag = True

    if not price_has_special_flag and ocr_data.get('price_raw'):
        price_info = parse_price_raw(ocr_data['price_raw'])
        if price_info['is_unknown']:
            normalized['price_unknown'] = 'true'
        elif price_info['is_consultation']:
            normalized['price_consultation'] = 'true'
        elif price_info['is_bid']:
            normalized['price_bid'] = 'true'
        elif price_info['is_negotiation']:
            normalized['price_negotiation'] = 'true'
        elif price_info['value']:
            normalized['price'] = str(price_info['value'])


def _normalize_transport(ocr_data: dict, normalized: dict) -> None:
    """交通情報フィールドを正規化（最大3つ）"""
    for i in range(1, MAX_TRANSPORT_COUNT + 1):
        raw_key = f'transport_{i}_raw'
        if ocr_data.get(raw_key):
            transport = parse_transport_raw(ocr_data[raw_key])
            if transport['line']:
                normalized[f'transport_line_{i}'] = transport['line']
            if transport['station']:
                normalized[f'transport_station_{i}'] = transport['station']
            if transport['minutes']:
                normalized[f'transport_minutes_{i}'] = transport['minutes']

        independent_line_key = f'transport_{i}_line'
        if ocr_data.get(independent_line_key):
            normalized[f'transport_line_{i}'] = ocr_data[independent_line_key]

        line_key = f'transport_line_{i}'
        station_key = f'transport_station_{i}'
        minutes_key = f'transport_minutes_{i}'

        if ocr_data.get(line_key) and line_key not in normalized:
            normalized[line_key] = ocr_data[line_key]
        if ocr_data.get(station_key) and station_key not in normalized:
            station_value = ocr_data[station_key]
            if '「' in station_value or '線' in station_value:
                parsed = parse_transport_raw(station_value)
                if parsed['station']:
                    station_value = parsed['station']
                    if parsed['line'] and line_key not in normalized:
                        normalized[line_key] = parsed['line']
                    if parsed['minutes'] and minutes_key not in normalized:
                        normalized[minutes_key] = parsed['minutes']
            normalized[station_key] = station_value
        if ocr_data.get(minutes_key) and minutes_key not in normalized:
            normalized[minutes_key] = ocr_data[minutes_key]


def _normalize_areas(ocr_data: dict, normalized: dict, property_type: str = 'overview') -> None:
    """面積情報フィールドを正規化"""
    if ocr_data.get('land_area_raw'):
        area = parse_area_raw(ocr_data['land_area_raw'])
        if area['value']:
            if property_type == 'overview':
                if area['type'] in ('measured', ''):
                    normalized['land_area_measured'] = area['value']
            elif area['type'] == 'official':
                normalized['land_area_official'] = area['value']
            elif area['type'] == 'measured':
                normalized['land_area_measured'] = area['value']

    area_mappings = [
        ('land_area_official_raw', 'land_area_official'),
        ('land_area_measured_raw', 'land_area_measured'),
        ('effective_land_area_official_raw', 'effective_land_area_official'),
        ('effective_land_area_measured_raw', 'effective_land_area_measured'),
        ('building_area_raw', 'building_area'),
        ('exclusive_area_raw', 'exclusive_area'),
        ('balcony_area_raw', 'balcony_area'),
        ('planned_building_area_raw', 'planned_building_area'),
    ]
    for raw_key, target_key in area_mappings:
        if ocr_data.get(raw_key):
            if raw_key in ('building_area_raw', 'planned_building_area_raw', 'land_area_official_raw'):
                floor_areas = parse_floor_area_raw(ocr_data[raw_key])
                if floor_areas:
                    total = sum(Decimal(fa['area_value']) for fa in floor_areas)
                    normalized[target_key] = str(
                        total.quantize(Decimal('0.01'), rounding=ROUND_DOWN)
                    )
                    if '_ocr_area_breakdowns' not in normalized:
                        normalized['_ocr_area_breakdowns'] = {}
                    normalized['_ocr_area_breakdowns'][target_key] = floor_areas
                    continue
            area = parse_area_raw(ocr_data[raw_key])
            if area['value']:
                normalized[target_key] = area['value']


def _normalize_roads(ocr_data: dict, normalized: dict) -> None:
    """道路情報フィールドを正規化（最大2つ）"""
    for i in range(1, MAX_ROAD_COUNT + 1):
        raw_key = f'road_{i}_raw'
        if i == 1 and raw_key not in ocr_data and 'road_raw' in ocr_data:
            raw_key = 'road_raw'
        if ocr_data.get(raw_key):
            road = parse_road_raw(ocr_data[raw_key])
            if road['direction']:
                normalized[f'road_direction_{i}'] = road['direction']
            if road['width']:
                normalized[f'road_width_{i}'] = road['width']


def _extract_first_use_district(raw_value: str) -> str:
    """複数用途地域が含まれる文字列から最初の1件を抽出する"""
    parts = re.split(r'[,、\n]', raw_value)
    first = ''
    for part in parts:
        candidate = part.strip()
        if candidate:
            first = candidate
            break
    if not first:
        first = raw_value.strip()
    first = re.sub(r'^[①-⑳\d]+\s*', '', first).strip()
    first = re.sub(r'[（(].*?[）)]', '', first).strip()
    first = re.sub(r'[（(].*$', '', first).strip()
    first = first.replace('第1種', '第一種').replace('第2種', '第二種')
    return first if first else raw_value.strip()


def _normalize_zoning(ocr_data: dict, normalized: dict) -> None:
    """用途地域情報フィールドを正規化（最大3つ）"""
    for i in range(1, MAX_ZONING_COUNT + 1):
        use_district_raw_key = f'use_district_{i}_raw'
        if ocr_data.get(use_district_raw_key) and _is_valid_ocr_value(ocr_data[use_district_raw_key]):
            normalized[f'use_district_{i}'] = ocr_data[use_district_raw_key]
        coverage_raw_key = f'building_coverage_ratio_{i}_raw'
        if ocr_data.get(coverage_raw_key) and _is_valid_ocr_value(ocr_data[coverage_raw_key]):
            value = _extract_numeric_value(ocr_data[coverage_raw_key])
            if value:
                normalized[f'building_coverage_ratio_{i}'] = f'{value}%'
        floor_ratio_raw_key = f'floor_area_ratio_{i}_raw'
        if ocr_data.get(floor_ratio_raw_key) and _is_valid_ocr_value(ocr_data[floor_ratio_raw_key]):
            value = _extract_numeric_value(ocr_data[floor_ratio_raw_key])
            if value:
                normalized[f'floor_area_ratio_{i}'] = f'{value}%'

    if ocr_data.get('use_district_raw') and 'use_district_1' not in normalized:
        raw_value = ocr_data['use_district_raw']
        if _is_valid_ocr_value(raw_value):
            first_district = _extract_first_use_district(raw_value)
            if first_district:
                normalized['use_district'] = first_district

    if ocr_data.get('building_coverage_ratio_raw') and 'building_coverage_ratio_1' not in normalized:
        value = _extract_numeric_value(ocr_data['building_coverage_ratio_raw'])
        if value:
            normalized['building_coverage_ratio_1'] = f'{value}%'
    if ocr_data.get('floor_area_ratio_raw') and 'floor_area_ratio_1' not in normalized:
        value = _extract_numeric_value(ocr_data['floor_area_ratio_raw'])
        if value:
            normalized['floor_area_ratio_1'] = f'{value}%'


def _normalize_districts(ocr_data: dict, normalized: dict) -> None:
    """高度指定・防火指定フィールドを正規化"""
    has_use_district = any(
        ocr_data.get(f'use_district_{i}_raw') and _is_valid_ocr_value(ocr_data[f'use_district_{i}_raw'])
        for i in range(1, 4)
    ) or normalized.get('use_district_1')

    for i in range(1, 3):
        raw_key = f'height_district_{i}_raw'
        target_key = f'height_district_{i}'
        if ocr_data.get(raw_key) and _is_valid_ocr_value(ocr_data[raw_key]):
            normalized[target_key] = ocr_data[raw_key].strip()
        else:
            if i == 1 and has_use_district:
                normalized[target_key] = '指定なし'

    for i in range(1, 3):
        raw_key = f'fire_district_{i}_raw'
        target_key = f'fire_district_{i}'
        if ocr_data.get(raw_key) and _is_valid_ocr_value(ocr_data[raw_key]):
            raw_value = ocr_data[raw_key]
            converted_value = _convert_with_master(raw_value, 'fire_district')
            if converted_value and converted_value != raw_value:
                normalized[target_key] = converted_value
            elif raw_value and raw_value.isdigit():
                normalized[target_key] = raw_value
            else:
                normalized[target_key] = raw_value
        else:
            if i == 1 and has_use_district:
                normalized[target_key] = '指定なし'


def _normalize_fees(ocr_data: dict, normalized: dict) -> None:
    """管理費・修繕積立金フィールドを正規化"""
    if ocr_data.get('management_fee_raw'):
        value = _extract_numeric_with_comma(ocr_data['management_fee_raw'])
        if value:
            normalized['management_fee'] = value
    if ocr_data.get('repair_reserve_fund_raw'):
        value = _extract_numeric_with_comma(ocr_data['repair_reserve_fund_raw'])
        if value:
            normalized['repair_reserve_fund'] = value


def _normalize_income_info(ocr_data: dict, normalized: dict) -> None:
    """収益情報フィールドを正規化"""
    if ocr_data.get('current_rent_income_raw'):
        price_info = parse_price_raw(ocr_data['current_rent_income_raw'])
        if price_info['value']:
            normalized['current_rent_income'] = str(price_info['value'])
    if ocr_data.get('current_occupancy_rate'):
        value = _extract_numeric_value(ocr_data['current_occupancy_rate'], r'([\d.]+)')
        if value:
            normalized['current_occupancy_rate'] = value


def _normalize_building_types(ocr_data: dict, normalized: dict, property_type: str = 'overview') -> None:
    """建物種類を正規化する"""
    raw_value = ocr_data.get('building_type', '')
    if not raw_value or not _is_valid_ocr_value(raw_value):
        return
    if property_type == 'overview':
        normalized['building_type'] = raw_value
        return
    types = [t.strip() for t in _BUILDING_TYPE_DELIMITERS.split(raw_value) if t.strip()]
    if not types:
        return
    for i, building_type in enumerate(types[:5], start=1):
        normalized[f'building_type_{i}'] = building_type


def _parse_road_price(raw_value: str) -> Optional[str]:
    """路線価のraw文字列から円/㎡の数値を抽出"""
    if not raw_value:
        return None
    match = re.search(r'([\d,]+)\s*千円\s*[／/]\s*[㎡m²]', raw_value)
    if match:
        value = int(match.group(1).replace(',', '')) * 1000
        return str(value)
    match = re.search(r'([\d,]+)\s*円\s*[／/]\s*[㎡m²]', raw_value)
    if match:
        return match.group(1).replace(',', '')
    match = re.search(r'^([\d,]+)$', raw_value.strip())
    if match:
        return match.group(1).replace(',', '')
    return None


def _normalize_development_fields(ocr_data: dict, normalized: dict) -> None:
    """開発物件用の追加フィールドを正規化"""
    if ocr_data.get('land_price_per_sqm_raw') and _is_valid_ocr_value(ocr_data['land_price_per_sqm_raw']):
        road_price = _parse_road_price(ocr_data['land_price_per_sqm_raw'])
        if road_price:
            normalized['road_price'] = road_price


def _clean_current_status(value: str) -> str:
    """現況の値から「現況：」等のプレフィックスを除去"""
    if not value:
        return value
    cleaned = re.sub(r'^現況\s*[：:]\s*', '', value).strip()
    return cleaned if cleaned else value


def _normalize_current_status(ocr_data: dict, normalized: dict, property_type: str) -> None:
    """現況フィールドを正規化"""
    current_status_map = {
        'development': 'current_status_development',
        'unit': 'current_status_unit',
        'income': 'current_status_income',
        'land': 'current_status_land',
    }
    for prop_type, field_name in current_status_map.items():
        if ocr_data.get(field_name) and _is_valid_ocr_value(ocr_data[field_name]):
            normalized[field_name] = _clean_current_status(ocr_data[field_name])
    if ocr_data.get('current_status') and property_type in current_status_map:
        target_field = current_status_map[property_type]
        if target_field not in normalized and _is_valid_ocr_value(ocr_data['current_status']):
            normalized[target_field] = _clean_current_status(ocr_data['current_status'])


def _normalize_debug_info(ocr_data: dict, normalized: dict) -> None:
    """診断情報を保持"""
    if ocr_data.get('extraction_notes'):
        normalized['_extraction_notes'] = ocr_data['extraction_notes']
    if ocr_data.get('unreadable_segments'):
        normalized['_unreadable_segments'] = ocr_data['unreadable_segments']


# =============================================================================
# 消費フィールド定義（備考追記で使用）
# =============================================================================

_CONSUMED_FIELDS_COMMON = {
    'property_name', 'info_source', 'info_source_contact',
    'address_display', 'address_lot',
    'building_structure', 'planned_building_structure',
    'land_rights', 'management_form',
    'remarks', 'inspection_certificate',
    'floor_plan', 'opening_direction',
    'renovation_raw',
    'total_units', 'total_floors', 'floor_number',
    'land_category', 'land_category_1',
    'info_date_raw', 'construction_date_raw',
    'price_raw', 'price_is_consultation', 'price_is_unknown',
    'price_is_bid', 'price_is_negotiation',
    'transport_1_raw', 'transport_2_raw', 'transport_3_raw',
    'transport_1_line', 'transport_2_line', 'transport_3_line',
    'land_area_raw', 'land_area_official_raw', 'land_area_measured_raw',
    'effective_land_area_official_raw', 'effective_land_area_measured_raw',
    'building_area_raw', 'exclusive_area_raw', 'balcony_area_raw',
    'planned_building_area_raw',
    'road_raw', 'road_1_raw', 'road_2_raw',
    'use_district_raw',
    'use_district_1_raw', 'use_district_2_raw', 'use_district_3_raw',
    'building_coverage_ratio_raw',
    'building_coverage_ratio_1_raw', 'building_coverage_ratio_2_raw',
    'floor_area_ratio_raw',
    'floor_area_ratio_1_raw', 'floor_area_ratio_2_raw',
    'height_district_1_raw', 'height_district_2_raw',
    'fire_district_1_raw', 'fire_district_2_raw',
    'management_fee_raw', 'repair_reserve_fund_raw',
    'current_rent_income_raw', 'current_occupancy_rate',
    'building_type',
    'land_price_per_sqm_raw',
    'current_status',
    'current_status_development', 'current_status_unit',
    'current_status_income', 'current_status_land',
    'extraction_notes', 'unreadable_segments',
}


_OCR_FIELD_LABELS = {
    'property_name': '物件名',
    'price_raw': '価格',
    'info_date_raw': '情報入手日',
    'info_source': '情報入手先',
    'address_display': '住居表示',
    'address_lot': '地番',
    'transport_1_raw': '交通1',
    'transport_2_raw': '交通2',
    'land_area_raw': '地積',
    'building_area_raw': '延べ床面積',
    'construction_date_raw': '築年月',
    'building_type': '建物種類',
    'building_structure': '建物構造',
    'use_district_raw': '用途地域',
    'remarks': '備考',
}


def _append_unmapped_fields_to_remarks(ocr_data: dict, normalized: dict) -> None:
    """マッピングされなかった有効な読取値を備考欄に追記する"""
    unmapped_lines = []
    for key, value in ocr_data.items():
        if key in _CONSUMED_FIELDS_COMMON:
            continue
        if not _is_valid_ocr_value(value):
            continue
        if isinstance(value, bool) and not value:
            continue
        if isinstance(value, list):
            continue
        label = _OCR_FIELD_LABELS.get(key, key)
        unmapped_lines.append(f'{label}: {value}')

    if not unmapped_lines:
        return

    extra_text = '\n'.join(unmapped_lines)
    existing_remarks = normalized.get('remarks', '')
    if existing_remarks:
        normalized['remarks'] = f'{existing_remarks}\n{extra_text}'
    else:
        normalized['remarks'] = extra_text


# =============================================================================
# メイン関数
# =============================================================================

def normalize_ocr_data(ocr_data: dict, property_type: str) -> dict:
    """
    OCR抽出データ（raw形式）を正規化してフォームフィールド形式に変換

    Args:
        ocr_data: OCR抽出データ（json_schemas.pyのスキーマに準拠）
        property_type: 物件タイプ（overview, development, unit, income, land）

    Returns:
        dict: フォームフィールドにマッピング可能な正規化データ
    """
    normalized = {}

    _normalize_direct_fields(ocr_data, normalized)
    _normalize_dates(ocr_data, normalized)
    _normalize_price(ocr_data, normalized)
    _normalize_transport(ocr_data, normalized)
    _normalize_areas(ocr_data, normalized, property_type)
    _normalize_roads(ocr_data, normalized)
    _normalize_zoning(ocr_data, normalized)
    _normalize_districts(ocr_data, normalized)
    _normalize_fees(ocr_data, normalized)
    _normalize_income_info(ocr_data, normalized)
    _normalize_building_types(ocr_data, normalized, property_type)
    _normalize_development_fields(ocr_data, normalized)
    _normalize_current_status(ocr_data, normalized, property_type)
    _normalize_debug_info(ocr_data, normalized)

    # フォームにマッピングされなかった有効な読取値を備考欄に追記
    _append_unmapped_fields_to_remarks(ocr_data, normalized)

    # 最後にエイリアス変換を適用
    return convert_property_data(normalized)
