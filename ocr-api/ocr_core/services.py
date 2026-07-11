"""
画像解析サービス
OpenAI Vision APIを使用して物件画像から情報を抽出する

最適化:
- Structured Outputs（JSON Schema）で出力形式を厳密に制約
- detail: original で高精度OCR
- 備考欄の瑕疵情報を重点的に抽出
- 複数画像は個別解析→マージ方式で情報欠落を防止
- 複数画像はThreadPoolExecutorで並列API呼び出しして高速化
"""
import json
import os
from typing import Any, Optional

from openai import OpenAI

from ocr_core.image_utils import encode_images, build_message_content
from ocr_core.field_mapping_utils import validate_extraction_quality


# OpenAIクライアントを再利用するための変数
_openai_client: Optional[OpenAI] = None


class ImageAnalysisUserError(Exception):
    """画像解析でユーザーに表示するエラー"""
    pass

def analyze_property_images(
    image_files: list[Any], 
    property_type: Optional[str] = None
) -> dict[str, Any]:
    """
    独立OCR PoC用の入口関数。

    run_ocr.pyから受け取った画像を、
    既存OCRの単一画像処理へ渡す。

    今回のPoCでは画像1枚だけを対象にするため、
    複数画像の並列処理やマージ処理はまだ使用しない。
    """
    if not image_files:
        raise ValueError("画像ファイルが指定されていません。")
    
    # 
    return _analyze_single_batch(
        image_files=image_files[:1],
        property_type=property_type
    )

def _analyze_single_batch(
    image_files: list[Any],
    property_type: Optional[Any]
) -> dict[str, Any]:
    """
    画像一枚を既存OCR処理へ渡し、正規化済の物件データを返す。
    """

    # 途中でエラーが起きた場合に、
    # handle_analysis_error()へ渡すために用意している。
    try:
        # ==========================================
        # 1. 画像をOpenAIへ送れる形式へ変換する
        # ==========================================
        image_data_list = encode_images(
            image_files,
            apply_preprocessing=False,
        )

        # ==========================================
        # 2. OpenAIへ渡す指示文を取得する
        # ==========================================
        #
        # property_typeがNoneの場合は、
        # _get_prompt()側の処理に従う。
        #
        # len(image_data_list)は今回1になる想定。
        prompt = _get_prompt(
            property_type,
            len(image_data_list),
        )

        # ==========================================
        # 3. OpenAIの返答形式を取得する
        # ==========================================
        #
        # OpenAIに、
        # どのようなJSON形式で返してほしいかを指定する。
        schema = _get_schema(property_type)

        # ==========================================
        # 4. OpenAIへ送るメッセージを組み立てる
        # ==========================================
        #
        # prompt:
        #   OCRへの指示
        #
        # image_data_list:
        #   APIへ送れる形に変換された画像
        message_content = build_message_content(
            prompt,
            image_data_list,
        )

        from .prompts.base_prompt import get_system_message

        # ==========================================
        # 6. OpenAI Vision APIを呼び出す
        # ==========================================

        content = call_vision_api(
            system_message=get_system_message(
                len(image_data_list) > 1
            ),
            message_content=message_content,
            response_format=schema,
        )

        # ==========================================
        # 7. JSON文字列をPython辞書へ変換する
        # ==========================================

        ocr_data = json.loads(content)

        # ==========================================
        # 8. OCR結果をシステム共通形式へ正規化する
        # ==========================================
        from .field_mapping import normalize_ocr_data

        property_data = normalize_ocr_data(
            ocr_data,
            property_type or "overview",
        )

        # ==========================================
        # 9. OCR結果の品質を確認する
        # ==========================================
        #
        # 十分な数の項目が抽出できているかを確認する。
        if not validate_extraction_quality(
            property_data,
            exclude_internal=True,
        ):
            raise ImageAnalysisUserError(
                "画像から物件情報を読み取れませんでした。"
                "不動産資料の画像を選択してください。"
            )

        # ==========================================
        # 10. 正規化済みデータを返す
        # ==========================================
        return property_data

    except Exception as error:
        raise
        # 途中で発生したエラーを、
        # 既存のエラー処理へ渡す。
        # handle_analysis_error(error, content)
def _get_prompt(
    property_type: Optional[str],
    image_count: int,
) -> str:
    """
    独立OCR PoCではoverview用プロンプトだけを使用する。
    """

    from .prompts.overview_prompt import get_overview_prompt

    return get_overview_prompt(image_count)


def _get_schema(
    property_type: Optional[str],
) -> dict[str, Any]:
    """
    独立OCR PoCではoverview用Schemaだけを使用する。
    """

    from .prompts.json_schemas import get_schema

    return get_schema("overview")

API_TIMEOUT_SECONDS = 90.0


def _get_openai_client() -> OpenAI:
    """
    環境変数からAPIキーを取得し、
    OpenAIクライアントを作成する。
    """

    global _openai_client

    if _openai_client is None:
        api_key = os.getenv("OPENAI_API_KEY")

        if not api_key:
            raise RuntimeError(
                "OPENAI_API_KEYが設定されていません。"
            )

        _openai_client = OpenAI(
            api_key=api_key,
            timeout=API_TIMEOUT_SECONDS,
        )

    return _openai_client


def call_vision_api(
    system_message: str,
    message_content: list[dict[str, Any]],
    response_format: dict[str, Any],
) -> str:
    """
    OpenAI Vision APIを呼び出し、
    JSON文字列を返す。
    """

    client = _get_openai_client()

    model_name = os.getenv("OPENAI_VISION_MODEL")

    if not model_name:
        raise RuntimeError(
            "OPENAI_VISION_MODELが設定されていません。"
        )

    response = client.chat.completions.create(
        model=model_name,
        messages=[
            {
                "role": "system",
                "content": system_message,
            },
            {
                "role": "user",
                "content": message_content,
            },
        ],
        max_completion_tokens=4000,
        response_format=response_format,
    )

    content = response.choices[0].message.content

    if content is None:
        raise RuntimeError(
            "OpenAI APIからレスポンス本文を取得できませんでした。"
        )

    return content
