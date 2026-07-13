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


# 1. UploadFile
# 2. await img.read()
# 3. bytes取得
# 4. SyncImageFileへ保存
# 5. _position = 0
# 6. read()で現在位置から末尾まで返す
# 7. read()後、_positionは末尾
# 8. seek(0)で先頭へ戻す
# 9. もう一度read()できる
# 10. 実際のseek(0)利用箇所はrg "seek\(0\)" ocr_core
# ============================
# 同期アダプター
# ============================

class SyncImageFile:
    """
        SyncImageFileが作っているのは、特別な画像形式ではありません。
        既存OCRが「ファイルとして扱える」と判断できる、最小限のファイル風オブジェクトです。

        既存OCR
        はこういう使い方だった。

            image_file.name
            image_file.size
            image_file.read()
            image_file.seek(0)


        UploadFile(非同期)から読み込んだバイト列を、
        ocr_core が要求する同期インターフェース(.name, .read(), .seek())で
        提供するための軽量アダプター。

        インターフェイス「Pythonでは多くの場合、
        この属性とメソッドを持っていれば使えるというダックタイピングで扱います。」
        既存OCRが要求しているもの→ file-like object(DjangoのUploadedFileと同じように操作できるファイル風オブジェクト)
    
            read()
            → 全部読む
            → positionは末尾

            read()
            → 空

            seek(0)
            → positionを先頭へ戻す

            read()
            → また全部読める


        """

    def __init__(self, filename: str, data: bytes):
        self.name = filename
        self.size = len(data)
        self._data = data
        self._position = 0

    def read(self) -> bytes:
        result = self._data[self._position:] # self._data = b"ABCDE" だとすると、self._data[0:]で最後まで。
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
            # 1. UploadFileから画像本体をbytesとして取り出す
            content = await img.read()
            # 2. bytesを同期ファイル風オブジェクトへ包む
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

# for img in images:
#     # 1. UploadFileから画像本体をbytesとして取り出す
#     content = await img.read()

#     # 2. bytesを同期ファイル風オブジェクトへ包む
#     adapted_file = SyncImageFile(
#         filename=img.filename,
#         data=content,
#     )

#     # 3. OCRへ渡すためlistへ追加
#     adapted_files.append(adapted_file)