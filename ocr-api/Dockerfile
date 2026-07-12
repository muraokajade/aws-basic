FROM python:3.12-slim
# → どのLinux・Python環境を土台にするか

WORKDIR /app
# → Container内の作業場所

COPY requirements.txt .
# → Mac上のファイルをImageへ入れる

RUN pip install --no-cache-dir -r requirements.txt
# → Image作成中に実行する処理

COPY . .
# 左の .
# ＝ Mac側の現在のocr-apiフォルダ

# 右の .
# ＝ Container側のWORKDIR、つまり/app


EXPOSE 8000
# → Container内で使うPortの説明

CMD ["python", "-m", "uvicorn", "app:app", "--host", "0.0.0.0", "--port", "8000"]
# → Container起動時に実行するコマンド

# Macのocr-apiフォルダを材料にして
# Docker Imageを作り、
# Container起動時にUvicornを実行する