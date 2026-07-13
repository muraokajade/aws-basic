"""
画像処理ユーティリティ

ファイルバリデーション・画像前処理・base64変換を提供する。
Django依存なし。ファイルオブジェクトはname/size/read()/seek()を持つ任意の型。
"""
import base64
import io
import logging
import os
from typing import Any, Dict, List, Optional

from PIL import Image, ImageChops, ImageEnhance, ImageFilter, ImageOps

logger = logging.getLogger(__name__)

# =============================================================================
# 定数
# =============================================================================

# 許可する拡張子
ALLOWED_IMAGE_EXTENSIONS = ['.jpg', '.jpeg', '.png', '.gif', '.webp']

# 許可するContent-Type
ALLOWED_CONTENT_TYPES = [
    'image/jpeg', 'image/png', 'image/gif', 'image/webp',
]

# 最大ファイルサイズ（1MB — project_managerと同じ）
MAX_FILE_SIZE_MB = 1
MAX_FILE_SIZE_BYTES = MAX_FILE_SIZE_MB * 1024 * 1024

# MIMEタイプマッピング
MIME_TYPE_MAP = {
    '.jpg': 'image/jpeg',
    '.jpeg': 'image/jpeg',
    '.png': 'image/png',
    '.gif': 'image/gif',
    '.webp': 'image/webp',
}

# 画像前処理定数
IMAGE_MAX_SIZE = 6000       # 長辺の最大ピクセル数
IMAGE_MIN_SIZE = 1024       # 長辺がこれ未満なら拡大する
IMAGE_SCALE_FACTOR = 2.0    # 小さい画像を拡大する倍率
JPEG_QUALITY = 95           # 再エンコード時の品質

# 横長画像の分割閾値
WIDE_IMAGE_RATIO = 1.3
SPLIT_OVERLAP_RATIO = 0.05

# API設定
MAX_IMAGE_COUNT = 3

# 赤色除去の閾値設定
RED_CHANNEL_MIN = 150
RED_GREEN_DIFF_MIN = 60
RED_BLUE_DIFF_MIN = 60


# =============================================================================
# ファイルバリデーション
# =============================================================================


def validate_image_file(image_file: Any) -> Optional[str]:
    """
    画像ファイルのバリデーションを行う

    拡張子・ファイルサイズ・Pillowによるマジックバイト検証を実施。

    Args:
        image_file: name/size/read()/seek()を持つファイルオブジェクト

    Returns:
        Optional[str]: エラーメッセージ。問題なければ None
    """
    filename = getattr(image_file, 'name', 'unknown')

    # 0バイトファイルチェック
    if getattr(image_file, 'size', 0) == 0:
        return f'ファイルが空です（{filename}）'

    # 拡張子チェック
    file_ext = os.path.splitext(filename)[1].lower()
    if file_ext not in ALLOWED_IMAGE_EXTENSIONS:
        return (
            f'対応していないファイル形式です（{filename}）。'
            f'対応形式: {", ".join(ALLOWED_IMAGE_EXTENSIONS)}'
        )

    # ファイルサイズチェック
    file_size = getattr(image_file, 'size', 0)
    if file_size > MAX_FILE_SIZE_BYTES:
        return f'ファイルサイズが{MAX_FILE_SIZE_MB}MBを超えています（{filename}）'

    # マジックバイト検証（Pillowで実際の画像形式を確認）
    try:
        image_file.seek(0)
        raw_bytes = image_file.read()
        img = Image.open(io.BytesIO(raw_bytes))
        img.verify()
    except Exception:
        return f'画像ファイルが破損しているか、不正な形式です（{filename}）'
    finally:
        image_file.seek(0)

    return None


# =============================================================================
# 手書き文字除去
# =============================================================================


def remove_red_handwriting(img: Image.Image) -> Image.Image:
    """赤色の手書き文字を除去する"""
    if img.mode != 'RGB':
        return img

    r_ch, g_ch, b_ch = img.split()

    r_high = r_ch.point(lambda v: 255 if v >= RED_CHANNEL_MIN else 0)

    rg_diff = ImageChops.subtract(r_ch, g_ch)
    rg_mask = rg_diff.point(lambda v: 255 if v >= RED_GREEN_DIFF_MIN else 0)

    rb_diff = ImageChops.subtract(r_ch, b_ch)
    rb_mask = rb_diff.point(lambda v: 255 if v >= RED_BLUE_DIFF_MIN else 0)

    red_mask = ImageChops.multiply(r_high, ImageChops.multiply(rg_mask, rb_mask))

    white = Image.new('RGB', img.size, (255, 255, 255))
    result = Image.composite(white, img, red_mask)
    return result


# =============================================================================
# 画像前処理
# =============================================================================


def _enhance_for_ocr(img: Image.Image) -> Image.Image:
    """
    OCR精度向上のための共通画像補正処理

    赤色手書き除去・リサイズを適用する。
    高解像度モード（IMAGE_MAX_SIZE >= 6000）ではSHARPEN・コントラスト強化をスキップ。
    """
    img = remove_red_handwriting(img)

    w, h = img.size
    long_side = max(w, h)

    if long_side < IMAGE_MIN_SIZE:
        scale = IMAGE_SCALE_FACTOR
        img = img.resize((int(w * scale), int(h * scale)), Image.LANCZOS)
    elif long_side > IMAGE_MAX_SIZE:
        scale = IMAGE_MAX_SIZE / long_side
        img = img.resize((int(w * scale), int(h * scale)), Image.LANCZOS)

    if IMAGE_MAX_SIZE < 6000:
        img = img.filter(ImageFilter.SHARPEN)
        if img.mode == 'RGB':
            img = ImageEnhance.Contrast(img).enhance(1.3)

    return img


def _to_jpeg_bytes(img: Image.Image) -> tuple:
    """画像をJPEGバイト列にエンコードする"""
    buf = io.BytesIO()
    img.save(buf, format='JPEG', quality=JPEG_QUALITY)
    return buf.getvalue(), 'image/jpeg'


def preprocess_image(image_file: Any) -> tuple:
    """
    OCR精度向上のための画像前処理

    - EXIF Orientation に基づいて正しい向きに回転
    - RGBA/P モードを RGB に変換
    - 赤色手書き除去・リサイズ等

    Args:
        image_file: ファイルオブジェクト

    Returns:
        tuple: (処理済み画像バイト列, MIMEタイプ)
    """
    image_file.seek(0)
    raw_bytes = image_file.read()
    img = Image.open(io.BytesIO(raw_bytes))

    img = ImageOps.exif_transpose(img)

    if img.mode in ('RGBA', 'P'):
        img = img.convert('RGB')

    img = _enhance_for_ocr(img)
    return _to_jpeg_bytes(img)


def split_wide_image(image_file: Any) -> List[tuple]:
    """
    横長画像（見開きスキャン等）を左右に分割する

    幅が高さの WIDE_IMAGE_RATIO 倍以上の場合、左半分と右半分に分割する。

    Returns:
        List[tuple]: [(画像バイト列, MIMEタイプ, ファイル名), ...]
            横長でない場合は空リスト
    """
    image_file.seek(0)
    raw_bytes = image_file.read()
    img = Image.open(io.BytesIO(raw_bytes))
    img = ImageOps.exif_transpose(img)

    if img.mode in ('RGBA', 'P'):
        img = img.convert('RGB')

    w, h = img.size

    if w < h * WIDE_IMAGE_RATIO:
        return []

    overlap = int(w * SPLIT_OVERLAP_RATIO)
    mid = w // 2

    left_img = img.crop((0, 0, mid + overlap, h))
    right_img = img.crop((mid - overlap, 0, w, h))

    results = []
    base_name = getattr(image_file, 'name', 'image')

    for part_img, suffix in [(left_img, '_left'), (right_img, '_right')]:
        part_img = _enhance_for_ocr(part_img)
        img_bytes, mime_type = _to_jpeg_bytes(part_img)
        results.append((img_bytes, mime_type, f'{base_name}{suffix}'))

    return results


# =============================================================================
# 画像エンコード
# =============================================================================


def encode_images(
    image_files: List[Any],
    apply_preprocessing: bool = True,
) -> List[Dict[str, str]]:
    """
    画像ファイルをbase64エンコード

    横長画像は自動的に左右に分割してから処理する。
    分割後も合計枚数は MAX_IMAGE_COUNT 以内に制限される。

    Args:
        image_files: ファイルオブジェクトのリスト
        apply_preprocessing: 前処理（リサイズ・シャープ化）を適用するか

    Returns:
        List[Dict[str, str]]: base64エンコードされた画像データのリスト
    """
    image_data_list = []
    for image_file in image_files:
        if len(image_data_list) >= MAX_IMAGE_COUNT:
            break

        if apply_preprocessing:
            # 横長画像の分割を試みる
            split_results = split_wide_image(image_file)

            if split_results:
                for img_bytes, mime_type, filename in split_results:
                    if len(image_data_list) >= MAX_IMAGE_COUNT:
                        break
                    image_data = base64.b64encode(img_bytes).decode('utf-8')
                    image_data_list.append({
                        'data': image_data,
                        'mime_type': mime_type,
                        'filename': filename,
                    })
            else:
                processed_bytes, mime_type = preprocess_image(image_file)
                image_data = base64.b64encode(processed_bytes).decode('utf-8')
                image_data_list.append({
                    'data': image_data,
                    'mime_type': mime_type,
                    'filename': getattr(image_file, 'name', 'image'),
                })
        else:
            image_file.seek(0)
            raw_bytes = image_file.read()
            image_data = base64.b64encode(raw_bytes).decode('utf-8')
            file_ext = os.path.splitext(
                getattr(image_file, 'name', 'image.jpg')
            )[1].lower()
            mime_type = MIME_TYPE_MAP.get(file_ext, 'image/jpeg')
            image_data_list.append({
                'data': image_data,
                'mime_type': mime_type,
                'filename': getattr(image_file, 'name', 'image'),
            })

    return image_data_list


# =============================================================================
# メッセージ構築
# =============================================================================


def build_message_content(
    prompt: str,
    image_data_list: List[Dict[str, str]],
) -> List[Dict[str, Any]]:
    """OpenAI API リクエスト用のメッセージコンテンツを構築"""
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
