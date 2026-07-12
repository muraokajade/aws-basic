## Image確認

docker build -t ocr-api .

docker build
→ Imageを作る

-t ocr-api
→ Imageに ocr-api という名前をつける

.
→ 現在のディレクトリにあるDockerfileを使う

## Container起動

docker run --rm --name ocr-api-container -p 8001:8000 ocr-api

## 意味

```text
--rm
→ Container停止後に自動削除

--name ocr-api-container
→ Container名

-p 8001:8000
→ Macの8001番をContainerの8000番へ接続

ocr-api
→ 起動元のImage名

```

docker ps

0.0.0.0:8001->8000/tcp, [::]:8001->8000/tcp ocr-demo-api

```
Macのlocalhost:8001
↓
Dockerのport転送
↓
Containerの8000
↓
Uvicorn
↓
FastAPI
```

curl http://localhost:8001/health

```
curl
↓
Macの localhost:8001 にアクセス
↓
docker run の -p 8001:8000 が転送
↓
Container内の8000番portへ到着
↓
Uvicornが受け取る
↓
FastAPIの /health を探す
↓
JSONを返す

出力:{"status":"ok","message":"OCR API is Running"}%
```
