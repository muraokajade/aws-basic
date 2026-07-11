"""
独立OCR PoC 実行スクリプト

使い方:
    python3 run_ocr.py sample.png
"""
import json
import sys
from pathlib import Path

# .envファイルがあれば環境変数を読み込む
try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

from ocr_core.services import analyze_property_images


class LocalImageFile:
    """
    ローカル画像を
    Django UploadedFileに近い形で扱うための最小Adapter
    """

    def __init__(self, image_path: Path):
        self.name = image_path.name
        self.size = image_path.stat().st_size
        self.file = image_path.open("rb")

    def read(self):
        return self.file.read()

    def seek(self, position):
        return self.file.seek(position)

    def close(self):
        self.file.close()


def main():
    if len(sys.argv) < 2:
        print("使い方: python3 run_ocr.py <画像ファイル>")
        sys.exit(1)

    image_path = Path(sys.argv[1])
    if not image_path.exists():
        print(f"画像ファイルが見つかりません: {image_path}")
        sys.exit(1)

    image_file = LocalImageFile(image_path)

    try:
        result = analyze_property_images(
            image_files=[image_file],
            property_type=None,
        )
        print(json.dumps(result, ensure_ascii=False, indent=2))
    finally:
        image_file.close()


if __name__ == "__main__":
    main()
