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

from ocr_core.services import analyze_property_images


# ============================
# 同期アダプター
# ============================

class SyncImageFile:
    """
    UploadFile(非同期)から読み込んだバイト列を、
    ocr_core が要求する同期インターフェース(.name, .read(), .seek())で
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

# staticディレクトリを /static で配信
app.mount(
    "/static",
    StaticFiles(directory=str(BASE_DIR / "static")),
    name="static",
)

# テンプレートディレクトリ設定
templates = Jinja2Templates(directory=str(BASE_DIR / "templates"))


# ============================
# GET /health
# ============================

@app.get("/health")
def health() -> dict[str, str]:
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
        "ocr_demo.html",
        {"request": request},
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
    画像を受け取り、ocr_coreのOCR処理を実行して結果を返す。

    UploadFileの .read() は非同期なので、
    事前にバイト列を読み込んでからocr_coreへ渡す。
    """
    if not images:
        return JSONResponse(
            status_code=400,
            content={
                "success": False,
                "message": "画像ファイルが選択されていません。",
                "data": None,
            },
        )

    try:
        # UploadFileは非同期read()のため、
        # 同期的な ocr_core に渡せるアダプターへ変換する
        adapted_files = []
        for img in images:
            content = await img.read()
            adapted_files.append(
                SyncImageFile(filename=img.filename, data=content)
            )

        result = analyze_property_images(
            image_files=adapted_files,
            property_type=property_type,
        )

        return {
            "success": True,
            "message": f"{len(adapted_files)}枚の画像から物件情報を読み取りました。",
            "data": result,
        }

    except Exception as e:
        return JSONResponse(
            status_code=500,
            content={
                "success": False,
                "message": str(e),
                "data": None,
            },
        )
