"""
OCR Demo API (FastAPI)

エンドポイント:
- GET  /health   ヘルスチェック
- GET  /ocr-demo ブラウザUI
- POST /ocr      画像OCR実行（1〜3枚）
"""
import logging
from pathlib import Path
from typing import Optional

from fastapi import FastAPI, File, Form, UploadFile, Request
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

# .envファイルがあれば環境変数を読み込む
try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

from ocr_core.services import analyze_property_images, ImageAnalysisUserError
from ocr_core.image_utils import (
    MAX_IMAGE_COUNT,
    MAX_FILE_SIZE_BYTES,
    MAX_FILE_SIZE_MB,
    ALLOWED_CONTENT_TYPES,
    validate_image_file,
)

logger = logging.getLogger(__name__)

# ============================
# 同期アダプター
# ============================


class SyncImageFile:
    """
    UploadFile(非同期)から読み込んだバイト列を、
    ocr_core が要求する同期インターフェース(.name, .size, .read(), .seek())で
    提供するための軽量アダプター。
    """

    def __init__(self, filename: str, data: bytes):
        self.name = filename
        self.size = len(data)
        self._data = data
        self._position = 0

    def read(self) -> bytes:
        result = self._data[self._position:]
        self._position = len(self._data)
        return result

    def seek(self, position: int):
        self._position = position


# ============================
# アプリ初期化
# ============================

BASE_DIR = Path(__file__).resolve().parent

app = FastAPI(title="OCR Demo API")

app.mount(
    "/static",
    StaticFiles(directory=str(BASE_DIR / "static")),
    name="static",
)

templates = Jinja2Templates(directory=str(BASE_DIR / "templates"))


# ============================
# GET /health
# ============================

@app.get("/health")
def health() -> dict:
    return {
        "status": "ok",
        "message": "OCR API is Running",
    }


# ============================
# GET /ocr-demo
# ============================

@app.get("/ocr-demo", response_class=HTMLResponse)
def ocr_demo(request: Request):
    return templates.TemplateResponse(
        request=request,
        name="ocr_demo.html",
    )


# ============================
# POST /ocr
# ============================

@app.post("/ocr")
async def ocr(
    images: list[UploadFile] = File(...),
    property_type: Optional[str] = Form(None),
):
    """
    画像を受け取り、OCR処理を実行して結果を返す。

    バリデーション:
    - 0枚: 400
    - 4枚以上: 400
    - 0バイトファイル: 400
    - 不正Content-Type: 400
    - ファイルサイズ超過: 400
    - Pillow画像検証失敗: 400
    """

    # --- 枚数チェック ---
    if not images:
        return JSONResponse(
            status_code=400,
            content={
                "success": False,
                "message": "画像ファイルが選択されていません。",
                "data": None,
            },
        )

    if len(images) > MAX_IMAGE_COUNT:
        return JSONResponse(
            status_code=400,
            content={
                "success": False,
                "message": f"画像は最大{MAX_IMAGE_COUNT}枚までです。{len(images)}枚が送信されました。",
                "data": None,
            },
        )

    # --- 各ファイルのバリデーション + アダプター変換 ---
    adapted_files: list[SyncImageFile] = []

    for img in images:
        # Content-Typeチェック
        content_type = img.content_type or ''
        if content_type not in ALLOWED_CONTENT_TYPES:
            return JSONResponse(
                status_code=400,
                content={
                    "success": False,
                    "message": f"対応していないファイル形式です（{img.filename}）。JPEG/PNG/GIF/WebPのみ対応しています。",
                    "data": None,
                },
            )

        # ファイル読み込み
        content = await img.read()

        # 0バイトチェック
        if len(content) == 0:
            return JSONResponse(
                status_code=400,
                content={
                    "success": False,
                    "message": f"ファイルが空です（{img.filename}）。",
                    "data": None,
                },
            )

        # ファイルサイズチェック
        if len(content) > MAX_FILE_SIZE_BYTES:
            return JSONResponse(
                status_code=400,
                content={
                    "success": False,
                    "message": f"ファイルサイズが{MAX_FILE_SIZE_MB}MBを超えています（{img.filename}）。",
                    "data": None,
                },
            )

        # ファイル名のサニタイズ
        filename = img.filename if img.filename else f"image_{len(adapted_files) + 1}.jpg"

        # SyncImageFileに変換
        sync_file = SyncImageFile(filename=filename, data=content)

        # Pillow画像検証
        error = validate_image_file(sync_file)
        if error:
            return JSONResponse(
                status_code=400,
                content={
                    "success": False,
                    "message": error,
                    "data": None,
                },
            )

        adapted_files.append(sync_file)

    # --- OCR実行 ---
    try:
        result = analyze_property_images(
            image_files=adapted_files,
            property_type=property_type,
        )

        return {
            "success": True,
            "message": f"{len(adapted_files)}枚の画像から物件情報を読み取りました。",
            "data": result,
        }

    except ImageAnalysisUserError as e:
        return JSONResponse(
            status_code=400,
            content={
                "success": False,
                "message": str(e),
                "data": None,
            },
        )

    except Exception as e:
        logger.error('OCR処理で予期しないエラーが発生しました', exc_info=True)
        return JSONResponse(
            status_code=500,
            content={
                "success": False,
                "message": "サーバー内部エラーが発生しました。管理者に連絡してください。",
                "data": None,
            },
        )
