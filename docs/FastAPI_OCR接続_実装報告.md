# FastAPI・OCR接続 実装報告

## 1. 実施内容

- 既存のOCRデモ画面（HTML/CSS/JS）をFastAPIから表示できるようにした
- `POST /ocr` エンドポイントで画像ファイルを受け取り、既存の `ocr_core` 処理を呼び出してOCR結果をJSONで返せるようにした
- FastAPIからstaticファイル（CSS・JavaScript）を配信する設定を追加した
- Django固有のテンプレート記法をJinja2/FastAPI向けに書き換えた

---

## 2. 変更ファイル一覧

| # | ファイル | 変更種別 |
|---|---------|---------|
| 1 | `requirements.txt` | 依存追加 |
| 2 | `app.py` | 全面書き換え |
| 3 | `templates/ocr_demo.html` | Django記法の除去・FastAPI向け修正 |
| 4 | `static/js/ocr_demo.js` | APIエンドポイント変更・CSRF削除 |

### 変更していないファイル

- `ocr_core/` 配下すべて（services.py, image_utils.py, prompts/, field_mapping.py等）
- `run_ocr.py`
- `static/css/ocr_demo.css`
- `Dockerfile`
- `sample.png`

---

## 3. 各ファイルの変更詳細

### 3-1. `requirements.txt`

#### 修正前

```
openai
python-dotenv
```

#### 修正後

```
openai
python-dotenv
fastapi
uvicorn[standard]
jinja2
python-multipart
```

#### 追加した各ライブラリの役割

| ライブラリ | 役割 |
|-----------|------|
| `fastapi` | Python用Webフレームワーク。APIルーティング・リクエスト処理を担当 |
| `uvicorn[standard]` | ASGIサーバー。FastAPIアプリを起動するために必要 |
| `jinja2` | テンプレートエンジン。HTMLファイル内で `{{ 変数 }}` を展開する |
| `python-multipart` | multipart/form-dataのパース。ファイルアップロード（`UploadFile`）に必須 |

#### なぜ必要だったか

FastAPIでHTMLテンプレート表示とファイルアップロード受信を行うには、この4つが最低限必要。

---

### 3-2. `app.py`（全面書き換え）

#### 修正前（仮実装）

```python
from fastapi import FastAPI

app = FastAPI(title="OCR Demo API")

@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok", "message": "OCR API is Running"}

@app.post("/ocr")
def ocr() -> dict[str, str]:
    return {"status": "ok", "message": "OCR endpoint is Rinning"}
```

問題点:
- `POST /ocr` が画像を受け取っていない（仮の固定レスポンス）
- static配信の設定がない
- テンプレート設定がない
- デモ画面を表示するルートがない

#### 修正後

```python
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
    return {"status": "ok", "message": "OCR API is Running"}


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
    if not images:
        return JSONResponse(
            status_code=400,
            content={"success": False, "message": "画像ファイルが選択されていません。", "data": None},
        )

    try:
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
            content={"success": False, "message": str(e), "data": None},
        )
```

#### 主要な変更ポイント

| 変更箇所 | 内容 | なぜ必要か |
|---------|------|-----------|
| `StaticFiles` マウント | `/static` パスでCSS/JSを配信 | ブラウザからCSS/JSファイルを読み込むため |
| `Jinja2Templates` 設定 | `templates/` ディレクトリを指定 | HTMLテンプレート内で `{{ url_for(...) }}` を使うため |
| `GET /ocr-demo` | テンプレートをレンダリングしてHTML返却 | デモ画面を表示するルートが必要 |
| `POST /ocr` 本実装 | `UploadFile` で画像受信 → OCR実行 → JSON返却 | 仮実装を本物に置き換え |
| `SyncImageFile` クラス | 非同期→同期の変換アダプター | 下記「技術的な課題」参照 |
| `load_dotenv()` | `.env` ファイルから環境変数読み込み | `run_ocr.py` と同様に `.env` でAPIキーを設定可能にするため |

#### 技術的な課題と解決

**問題**: FastAPIの `UploadFile.read()` は **非同期**（`async`）メソッドだが、`ocr_core.image_utils.encode_images()` は **同期的**に `.read()` を呼び出す。直接渡すと `coroutine` オブジェクトが返り、`bytes` として扱えずエラーになる。

**解決**: `SyncImageFile` アダプターを作成。エンドポイント内で `await img.read()` してバイト列を取得し、同期的な `.read()` / `.seek()` / `.name` を提供するオブジェクトに包んで `ocr_core` へ渡す。

```text
UploadFile (非同期)
    ↓ await img.read()  ← ここで全バイト列を取得
SyncImageFile (同期)
    ↓ .name, .read(), .seek()
ocr_core.image_utils.encode_images()  ← 既存コード変更なし
```

---

### 3-3. `templates/ocr_demo.html`

#### 変更箇所1: ファイル先頭

```html
<!-- 修正前 (Django) -->
{% load static %}
<!DOCTYPE html>
...
<link rel="stylesheet" href="{% static 'property_info_images/css/ocr_demo.css' %}">

<!-- 修正後 (FastAPI/Jinja2) -->
<!DOCTYPE html>
...
<link rel="stylesheet" href="{{ url_for('static', path='css/ocr_demo.css') }}">
```

| 修正前 | 修正後 | 理由 |
|--------|--------|------|
| `{% load static %}` | 削除 | Django専用タグ。Jinja2では不要 |
| `{% static 'property_info_images/css/...' %}` | `{{ url_for('static', path='css/...') }}` | FastAPIのStaticFilesが `/static/` で配信するため、`url_for` で正しいURLを生成 |

#### 変更箇所2: CSRFトークン

```html
<!-- 修正前 (Django) -->
<form id="csrfForm" class="d-none">
    {% csrf_token %}
</form>

<!-- 修正後 (FastAPI) -->
{# CSRF不要（FastAPI） #}
```

理由: DjangoはCSRFトークンが必要だが、FastAPIのAPIエンドポイントでは不要。form要素ごと削除。

#### 変更箇所3: JavaScript読み込み

```html
<!-- 修正前 -->
<script src="{% static 'property_info_images/js/ocr_demo.js' %}"></script>

<!-- 修正後 -->
<script src="{{ url_for('static', path='js/ocr_demo.js') }}"></script>
```

#### パスが変わった理由

Django側のstaticパスは `property_info_images/css/ocr_demo.css` だったが、FastAPI側では `static/` ディレクトリ直下に `css/` と `js/` があるため、`path='css/ocr_demo.css'` で正しい。

**HTMLの構造・デザインは一切変更なし。**

---

### 3-4. `static/js/ocr_demo.js`

#### 変更箇所1: APIエンドポイント

```javascript
// 修正前
const API_ENDPOINT = "/api/property-images/analyze/";

// 修正後
const API_ENDPOINT = "/ocr";
```

理由: Django側のURL `/api/property-images/analyze/` はFastAPIに存在しない。FastAPIの `POST /ocr` を向く必要がある。

#### 変更箇所2: CSRFヘッダー削除

```javascript
// 修正前
const response = await fetch(API_ENDPOINT, {
    method: "POST",
    headers: {
        "X-CSRFToken": getCsrfToken(),
    },
    body: formData,
});

// 修正後
const response = await fetch(API_ENDPOINT, {
    method: "POST",
    body: formData,
});
```

理由: FastAPIではCSRFトークンが不要。ヘッダーを送っても害はないが、不要なコードは削除。

**レスポンス形式 `{ success, data, message }` は新旧で一致するため、結果表示ロジック (`fillResultForm`, JSON表示等) は変更なし。**

---

## 4. 処理の流れ

```text
1. ブラウザで http://localhost:8001/ocr-demo を開く

2. GET /ocr-demo
   → FastAPIがJinja2で templates/ocr_demo.html をレンダリング
   → {{ url_for('static', path='css/ocr_demo.css') }} が
     http://localhost:8001/static/css/ocr_demo.css に展開される
   → HTMLがブラウザに返る

3. ブラウザがCSS/JSを読み込む
   → GET /static/css/ocr_demo.css  (200 OK)
   → GET /static/js/ocr_demo.js    (200 OK)

4. ユーザーが画像を選択して「OCRを実行」ボタンを押す

5. JavaScript (ocr_demo.js):
   → FormData に images (File) と property_type="overview" を詰める
   → fetch("POST /ocr", { body: formData }) を送信

6. FastAPI POST /ocr:
   → UploadFile として images を受信
   → await img.read() で全バイト列を取得
   → SyncImageFile アダプターに包む

7. ocr_core.services.analyze_property_images() を呼び出す:
   → image_utils.encode_images(): 画像をbase64変換
   → OpenAI Vision API 呼び出し
   → レスポンスJSONを正規化（field_mapping）
   → 物件データ辞書を返す

8. FastAPIがJSONレスポンスを返す:
   { "success": true, "data": { ...物件データ... }, "message": "..." }

9. JavaScript:
   → result.data を固定フォームの各inputに反映 (fillResultForm)
   → JSON表示ボタンでデバッグ表示可能
```

---

## 5. 既存コードへの影響

| 対象 | 影響 |
|------|------|
| `ocr_core/` 全体 | 変更なし。SyncImageFileが同じインターフェースを提供するため |
| `GET /health` | 変更なし。テスト確認済み（200 OK） |
| `run_ocr.py` | 変更なし。ターミナルから独立実行可能 |
| `static/css/ocr_demo.css` | 変更なし |
| `Dockerfile` | 変更なし（依存追加は `pip install -r requirements.txt` で吸収される） |

---

## 6. 確認結果

### 実行コマンド

```bash
cd ocr-api
OPENAI_VISION_MODEL=gpt-4.1-mini python3 -m uvicorn app:app --host 0.0.0.0 --port 8002
```

※ ポート8001はDockerが占有中のため、検証は8002で実施。

### 確認結果

| 確認項目 | 結果 | 備考 |
|---------|------|------|
| uvicorn起動 | 成功 | `Application startup complete` 確認 |
| `GET /health` → 200 | 成功 | `{"status":"ok"}` |
| `GET /ocr-demo` → 200 HTML | 成功 | 正しいHTML返却確認 |
| `/static/css/ocr_demo.css` → 200 | 成功 | |
| `/static/js/ocr_demo.js` → 200 | 成功 | |
| `POST /ocr` (sample.png) | 成功 | `success:true` + 物件データ取得 |
| OCR結果の中身 | 成功 | 物件名・住所・価格・交通情報等が正しく抽出 |

### OCR結果サンプル（実際の出力から抜粋）

```json
{
  "success": true,
  "message": "1枚の画像から物件情報を読み取りました。",
  "data": {
    "property_name": "サンプル物件④（収益転売）",
    "address_display": "東京都港区六本木3-2-1",
    "price": "300000000",
    "transport_line_1": "東京メトロ日比谷線",
    "transport_station_1": "六本木",
    "transport_minutes_1": "4"
  }
}
```

### 未確認事項

- ブラウザ画面からの操作テスト（curlでのAPI確認のみ実施）
- ポート8001での起動（Docker停止後に確認必要）
- 複数画像（2〜3枚）の同時アップロード

---

## 7. 現在のURL一覧

| メソッド | パス | 用途 |
|---------|------|------|
| GET | `/health` | ヘルスチェック |
| GET | `/ocr-demo` | OCRデモ画面表示 |
| POST | `/ocr` | OCR実行（multipart: images + property_type） |
| GET | `/static/css/ocr_demo.css` | スタイルシート |
| GET | `/static/js/ocr_demo.js` | JavaScript |

---

## 8. 次にやること

Dockerコンテナを停止してポート8001を解放し、`--port 8001` でuvicornを起動した上でブラウザから画面操作の動作確認を行う。
