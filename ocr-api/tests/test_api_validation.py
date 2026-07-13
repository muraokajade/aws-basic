"""
POST /ocr バリデーションの単体テスト

OpenAI APIを呼ばずにバリデーション層のみテストする。
"""
import io
import pytest
from fastapi.testclient import TestClient
from PIL import Image

from app import app

client = TestClient(app)


def _create_test_image(width=100, height=100, fmt="PNG") -> bytes:
    """テスト用の有効な画像バイト列を生成する"""
    img = Image.new("RGB", (width, height), color=(255, 0, 0))
    buf = io.BytesIO()
    img.save(buf, format=fmt)
    return buf.getvalue()


class TestOcrEndpointValidation:
    def test_0枚送信で400(self):
        response = client.post("/ocr", data={"property_type": "overview"})
        assert response.status_code == 422  # FastAPIはFile(...)で0件を422にする

    def test_4枚送信で400(self):
        img_bytes = _create_test_image()
        files = [
            ("images", (f"img{i}.png", img_bytes, "image/png"))
            for i in range(4)
        ]
        response = client.post("/ocr", files=files, data={"property_type": "overview"})
        assert response.status_code == 400
        data = response.json()
        assert data["success"] is False
        assert "最大3枚" in data["message"]

    def test_0バイトファイルで400(self):
        files = [("images", ("empty.png", b"", "image/png"))]
        response = client.post("/ocr", files=files, data={"property_type": "overview"})
        assert response.status_code == 400
        data = response.json()
        assert "空です" in data["message"]

    def test_不正Content_Typeで400(self):
        files = [("images", ("doc.pdf", b"fake content", "application/pdf"))]
        response = client.post("/ocr", files=files, data={"property_type": "overview"})
        assert response.status_code == 400
        data = response.json()
        assert "対応していないファイル形式" in data["message"]

    def test_サイズ超過で400(self):
        # 1MB超のデータ
        big_data = b"x" * (1024 * 1024 + 1)
        files = [("images", ("big.png", big_data, "image/png"))]
        response = client.post("/ocr", files=files, data={"property_type": "overview"})
        assert response.status_code == 400
        data = response.json()
        assert "1MB" in data["message"]

    def test_破損画像で400(self):
        files = [("images", ("broken.png", b"not an image", "image/png"))]
        response = client.post("/ocr", files=files, data={"property_type": "overview"})
        assert response.status_code == 400
        data = response.json()
        assert "破損" in data["message"]

    def test_正常な画像1枚はバリデーション通過(self):
        """
        バリデーションを通過するが、OpenAI APIキーなしの場合は
        ImageAnalysisUserError (400) またはRuntimeError (500) になる。
        ここではバリデーション通過を確認する（400のバリデーションエラーではない）。
        """
        img_bytes = _create_test_image()
        files = [("images", ("test.png", img_bytes, "image/png"))]
        response = client.post("/ocr", files=files, data={"property_type": "overview"})
        # バリデーション通過 → APIキーエラーで400か500
        # 重要: "空です" や "対応していない" や "破損" ではない
        data = response.json()
        if response.status_code == 400:
            assert "APIキー" in data["message"] or "読み取れません" in data["message"]
        else:
            assert response.status_code == 500

    def test_正常な画像3枚もバリデーション通過(self):
        img_bytes = _create_test_image()
        files = [
            ("images", (f"test{i}.png", img_bytes, "image/png"))
            for i in range(3)
        ]
        response = client.post("/ocr", files=files, data={"property_type": "overview"})
        data = response.json()
        # バリデーション層のエラーではないことを確認
        if response.status_code == 400:
            assert "最大" not in data["message"]
            assert "空です" not in data["message"]
            assert "対応していない" not in data["message"]
