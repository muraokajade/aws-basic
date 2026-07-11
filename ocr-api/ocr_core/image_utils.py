"""
独立OCR PoC用の画像変換処理。

ローカル画像を読み込み、
OpenAI Vision APIへ送れるbase64形式へ変換する。
"""

import base64
import os
from typing import Any, Optional


MAX_IMAGE_COUNT = 3

MIME_TYPE_MAP = {
    ".jpg": "image/jpeg",
    ".jpeg": "image/jpeg",
    ".png": "image/png",
    ".gif": "image/gif",
    ".webp": "image/webp",
}


def encode_images(
    image_files: list[Any],
    apply_preprocessing: bool = False,
) -> list[dict[str, str]]:
    """
    画像ファイルをbase64形式へ変換する。

    現在の独立OCR PoCでは、
    リサイズ、シャープ化、横長画像分割などの
    画像前処理は行わない。

    Adapterが提供する以下を使用する。

    ・name
    ・read()
    ・seek()
    """

    image_data_list: list[dict[str, str]] = []

    for image_file in image_files:
        if len(image_data_list) >= MAX_IMAGE_COUNT:
            break

        # Adapterの読み込み位置を先頭へ戻す
        image_file.seek(0)

        # 画像のbytesを読み込む
        image_bytes = image_file.read()

        # bytesをOpenAIへ送れるbase64文字列へ変換する
        encoded_image = base64.b64encode(
            image_bytes
        ).decode("utf-8")

        # ファイル名から拡張子を取得する
        file_extension = os.path.splitext(
            image_file.name
        )[1].lower()

        # 拡張子からMIMEタイプを決める
        mime_type = MIME_TYPE_MAP.get(
            file_extension,
            "image/jpeg",
        )

        image_data_list.append({
            "data": encoded_image,
            "mime_type": mime_type,
            "filename": image_file.name,
        })

    return image_data_list

def build_message_content(
    prompt: str,
    image_data_list: list[dict[str, str]],
) -> list[dict[str, Any]]:
    """
    OpenAI API リクエスト用のメッセージコンテンツを構築

    Args:
        prompt: プロンプト文字列
        image_data_list: base64エンコードされた画像データのリスト

    Returns:
        List[Dict[str, Any]]: OpenAI API用のメッセージコンテンツ
    """
    message_content: List[Dict[str, Any]] = [{"type": "text", "text": prompt}]

    for img_data in image_data_list:
        message_content.append({
            "type": "image_url",
            "image_url": {
                "url": f"data:{img_data['mime_type']};base64,{img_data['data']}",
                "detail": "original",
            },
        })

    return message_content

# def _get_openai_client() -> OpenAI:
#     """
#     独立OCR PoC用のOpenAIクライアントを取得する。

#     Django settingsは使用せず、
#     OPENAI_API_KEY環境変数からAPIキーを取得する。
#     """

#     global _openai_client

#     if _openai_client is None:
#         api_key = os.getenv("OPENAI_API_KEY")

#         if not api_key:
#             raise RuntimeError(
#                 "OPENAI_API_KEY環境変数が設定されていません。"
#             )

#         _openai_client = OpenAI(
#             api_key=api_key,
#             timeout=API_TIMEOUT_SECONDS,
#         )

#     return _openai_client

# def call_vision_api(
#     system_message: str,
#     message_content: list[dict[str, Any]],
#     response_format: dict[str, Any],
# ) -> str:
#     """
#     OpenAI Vision APIを呼び出し、
#     JSON文字列を返す。
#     """

#     client = _get_openai_client()

#     # Django settingsではなく環境変数からモデル名を取得する。
#     #
#     # OPENAI_VISION_MODELが未設定の場合は、
#     # 一時的なデフォルト値を使用する。
#     model_name = os.getenv(
#         "OPENAI_VISION_MODEL",
#         "gpt-4.1-mini",
#     )

#     response = client.chat.completions.create(
#         model=model_name,
#         messages=[
#             {
#                 "role": "system",
#                 "content": system_message,
#             },
#             {
#                 "role": "user",
#                 "content": message_content,
#             },
#         ],
#         max_completion_tokens=4000,
#         response_format=response_format,
#     )

#     content = response.choices[0].message.content

#     if content is None:
#         raise RuntimeError(
#             "OpenAI APIからレスポンス本文を取得できませんでした。"
#         )

#     return content