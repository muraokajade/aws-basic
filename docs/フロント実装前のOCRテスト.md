```
docker build -t ocr-api .
```

```
docker build
→ Dockerfileを使ってImageを作る

-t ocr-api
→ 作るImageに「ocr-api」という名前を付ける

.
→ 現在のフォルダを材料として使う
```

## ImageからContainerを起動するコマンド

- CMD ["python", "-m", "uvicorn", "app:app", "--host", "0.0.0.0", "--port", "8000"]

```

docker run --name ocr-api-container -p 8000:8000 --env-file .env ocr-api


```
