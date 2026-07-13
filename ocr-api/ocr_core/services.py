"""
画像解析サービス
OpenAI Vision APIを使用して物件画像から情報を抽出する

機能:
- Structured Outputs（JSON Schema）で出力形式を厳密に制約
- detail: original で高精度OCR
- 備考欄の瑕疵情報を重点的に抽出
- 複数画像は個別解析→マージ方式で情報欠落を防止
- 複数画像はThreadPoolExecutorで並列API呼び出しして高速化
"""
import json
import logging
import os
from concurrent.futures import ThreadPoolExecutor
from typing import Any, Dict, List, Optional

from openai import OpenAI

from ocr_core.image_utils import MAX_IMAGE_COUNT, encode_images, build_message_content
from ocr_core.field_mapping_utils import validate_extraction_quality

logger = logging.getLogger(__name__)

# =============================================================================
# 例外クラス
# =============================================================================


class ImageAnalysisUserError(Exception):
    """画像解析でユーザーに表示するエラー"""
    pass


# =============================================================================
# OpenAIクライアント管理
# =============================================================================

API_TIMEOUT_SECONDS = 90.0

_openai_client: Optional[OpenAI] = None


def _get_openai_client() -> OpenAI:
    """環境変数からAPIキーを取得し、OpenAIクライアントを作成する"""
    global _openai_client
    if _openai_client is None:
        api_key = os.getenv("OPENAI_API_KEY")
        if not api_key:
            raise ImageAnalysisUserError(
                "OpenAI APIキーが設定されていません。管理者に連絡してください。"
            )
        _openai_client = OpenAI(api_key=api_key, timeout=API_TIMEOUT_SECONDS)
    return _openai_client


def call_vision_api(
    system_message: str,
    message_content: List[Dict[str, Any]],
    response_format: Dict[str, Any],
) -> str:
    """OpenAI Vision APIを呼び出し、JSON文字列を返す"""
    client = _get_openai_client()
    model_name = os.getenv("OPENAI_VISION_MODEL")
    if not model_name:
        raise RuntimeError("OPENAI_VISION_MODELが設定されていません。")

    response = client.chat.completions.create(
        model=model_name,
        messages=[
            {"role": "system", "content": system_message},
            {"role": "user", "content": message_content},
        ],
        max_completion_tokens=4000,
        response_format=response_format,
    )

    content = response.choices[0].message.content
    if content is None:
        raise RuntimeError("OpenAI APIからレスポンス本文を取得できませんでした。")
    return content


# =============================================================================
# プロンプト・スキーマ取得
# =============================================================================


def _get_prompt(property_type: Optional[str], image_count: int) -> str:
    """物件タイプに応じたプロンプトを取得"""
    from ocr_core.prompts.overview_prompt import get_overview_prompt
    return get_overview_prompt(image_count)


def _get_schema(property_type: Optional[str]) -> Dict[str, Any]:
    """物件タイプに応じたJSON Schemaを取得"""
    from ocr_core.prompts.json_schemas import get_schema
    return get_schema("overview")


# =============================================================================
# エラーハンドリング
# =============================================================================


def handle_analysis_error(e: Exception, content: Optional[str] = None) -> None:
    """画像解析の共通エラーハンドリング"""
    if isinstance(e, json.JSONDecodeError):
        logger.error('画像解析エラー（JSON解析失敗）: %s', str(e))
        raise ImageAnalysisUserError('画像から情報を抽出できませんでした') from e

    if isinstance(e, ImageAnalysisUserError):
        raise

    error_str = str(e)
    if 'insufficient_quota' in error_str:
        logger.error('OpenAI APIクォータ超過: %s', error_str)
        raise ImageAnalysisUserError(
            'OpenAI APIの利用上限に達しました。APIキーの残高・プランをご確認ください。'
        ) from e

    from openai import AuthenticationError as OpenAIAuthError
    if isinstance(e, OpenAIAuthError) or 'invalid_api_key' in error_str:
        global _openai_client
        _openai_client = None
        logger.error('OpenAI APIキーエラー: %s', error_str)
        raise ImageAnalysisUserError(
            'OpenAI APIキーが無効です。正しいAPIキーを設定してください。'
        ) from e

    logger.error('画像解析エラー: %s: %s', type(e).__name__, str(e))
    raise


# =============================================================================
# メイン入口
# =============================================================================


def analyze_property_images(
    image_files: List[Any],
    property_type: Optional[str] = None,
) -> Dict[str, Any]:
    """
    OpenAI Vision APIを使用して複数の物件画像から情報を抽出する（最大3枚）

    複数画像の場合は各画像を並列にAPI解析し、結果をマージする。

    Args:
        image_files: アップロードされた画像ファイルのリスト
        property_type: 物件タイプ

    Returns:
        Dict[str, Any]: 抽出された物件情報
    """
    content: Optional[str] = None
    try:
        image_files = image_files[:MAX_IMAGE_COUNT]
        if not image_files:
            raise ValueError("画像ファイルが指定されていません。")

        if len(image_files) <= 1:
            return _analyze_single_batch(image_files, property_type)
        else:
            return _analyze_and_merge(image_files, property_type)
    except Exception as e:
        handle_analysis_error(e, content)


# =============================================================================
# 単一画像処理
# =============================================================================


def _analyze_single_batch(
    image_files: List[Any],
    property_type: Optional[str],
) -> Dict[str, Any]:
    """画像を一括でAPI解析する（1枚の場合に使用）"""
    content: Optional[str] = None
    try:
        image_data_list = encode_images(image_files, apply_preprocessing=True)

        prompt = _get_prompt(property_type, len(image_data_list))
        schema = _get_schema(property_type)
        message_content = build_message_content(prompt, image_data_list)

        from ocr_core.prompts.base_prompt import get_system_message
        content = call_vision_api(
            system_message=get_system_message(len(image_data_list) > 1),
            message_content=message_content,
            response_format=schema,
        )

        ocr_data = json.loads(content)

        from ocr_core.field_mapping import normalize_ocr_data
        property_data = normalize_ocr_data(ocr_data, property_type or 'overview')

        if not validate_extraction_quality(property_data, exclude_internal=True):
            raise ImageAnalysisUserError(
                '画像から物件情報を読み取れませんでした。'
                '不動産資料の画像を選択してください。'
            )

        return property_data
    except Exception as e:
        handle_analysis_error(e, content)


# =============================================================================
# 複数画像処理（並列解析→マージ）
# =============================================================================


def _analyze_and_merge(
    image_files: List[Any],
    property_type: Optional[str],
) -> Dict[str, Any]:
    """
    複数画像を並列にAPI解析し、結果をマージする

    ThreadPoolExecutor.mapを使用して各画像を並列で解析する。
    入力順序を保持してマージの決定性を維持する。
    """
    from ocr_core.prompts.base_prompt import get_system_message

    schema = _get_schema(property_type)

    def _analyze_one(image_file: Any) -> Optional[Dict[str, Any]]:
        """1枚の画像を解析してOCRデータを返す（失敗時はNone）"""
        try:
            image_data_list = encode_images([image_file], apply_preprocessing=True)
            prompt = _get_prompt(property_type, 1)
            message_content = build_message_content(prompt, image_data_list)
            content = call_vision_api(
                system_message=get_system_message(False),
                message_content=message_content,
                response_format=schema,
            )
            return json.loads(content)
        except Exception as e:
            logger.error('個別画像の解析に失敗しました', extra={
                'error': str(e),
                'image_filename': getattr(image_file, 'name', 'unknown'),
            })
            return None

    # ThreadPoolExecutor.map は入力順序を保持する
    with ThreadPoolExecutor(max_workers=3) as executor:
        results = list(executor.map(_analyze_one, image_files))

    # Noneを除外（解析失敗をスキップ）
    ocr_results = [r for r in results if r is not None]

    if not ocr_results:
        raise ImageAnalysisUserError(
            '画像から物件情報を読み取れませんでした。'
            '不動産資料の画像を選択してください。'
        )

    # OCR結果をマージ
    merged_ocr = _merge_ocr_results(ocr_results)

    # 正規化
    from ocr_core.field_mapping import normalize_ocr_data
    property_data = normalize_ocr_data(merged_ocr, property_type or 'overview')

    if not validate_extraction_quality(property_data, exclude_internal=True):
        raise ImageAnalysisUserError(
            '画像から物件情報を読み取れませんでした。'
            '不動産資料の画像を選択してください。'
        )

    return property_data


# =============================================================================
# マージロジック
# =============================================================================


def _is_valid_value(value: Any) -> bool:
    """OCR値が有効（非null・非空・非プレースホルダー）かを判定"""
    if value is None:
        return False
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        stripped = value.strip()
        if not stripped:
            return False
        if stripped in ('---', '－－－', '記載なし', '確認できない', '不明'):
            return False
        return True
    if isinstance(value, list):
        return len(value) > 0
    return True


def _merge_existing_buildings(ocr_results: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """
    複数OCR結果からexisting_buildings配列を結合する
    全画像から結合し最大5件で切り詰めて返す。
    """
    all_buildings = []
    for result in ocr_results:
        buildings = result.get('existing_buildings')
        if isinstance(buildings, list):
            for b in buildings:
                if isinstance(b, dict):
                    all_buildings.append(b)
    return all_buildings[:5]


def _merge_ocr_results(ocr_results: List[Dict[str, Any]]) -> Dict[str, Any]:
    """
    複数のOCR結果をマージする

    マージルール:
    1. 非nullの値を優先（先に見つかった有効値を採用）
    2. 文字列は長い方を優先（より詳細な情報を保持）
    3. remarks（備考）は全結果を重複除去して改行結合
    4. unreadable_segments は全結果を重複除去してリスト結合
    5. extraction_notes は全結果を結合
    6. existing_buildings は全画像から結合（最大5件）
    """
    if len(ocr_results) == 1:
        return ocr_results[0]

    merged = {}

    all_keys = set()
    for result in ocr_results:
        all_keys.update(result.keys())

    concat_fields = {'remarks'}
    list_concat_fields = {'unreadable_segments'}
    notes_fields = {'extraction_notes'}
    object_array_merge_fields = {'existing_buildings'}

    for key in all_keys:
        if key in concat_fields:
            parts = []
            seen = set()
            for result in ocr_results:
                val = result.get(key)
                if _is_valid_value(val) and val not in seen:
                    parts.append(val)
                    seen.add(val)
            merged[key] = '\n'.join(parts) if parts else None

        elif key in list_concat_fields:
            items = []
            seen = set()
            for result in ocr_results:
                val = result.get(key)
                if isinstance(val, list):
                    for item in val:
                        if item and item not in seen:
                            items.append(item)
                            seen.add(item)
            merged[key] = items if items else []

        elif key in notes_fields:
            parts = []
            for result in ocr_results:
                val = result.get(key)
                if _is_valid_value(val):
                    parts.append(val)
            merged[key] = '。'.join(parts) if parts else '複数画像を並列解析して統合'

        elif key in object_array_merge_fields:
            merged[key] = _merge_existing_buildings(ocr_results)

        else:
            best_value = None
            for result in ocr_results:
                val = result.get(key)
                if _is_valid_value(val):
                    if best_value is None:
                        best_value = val
                    elif isinstance(val, str) and isinstance(best_value, str):
                        if len(val) > len(best_value):
                            best_value = val
            merged[key] = best_value

    return merged
