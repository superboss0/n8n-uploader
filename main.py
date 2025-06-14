#!/usr/bin/env python3
from fastapi import FastAPI, UploadFile, File, HTTPException
from fastapi.responses import FileResponse
import os
from datetime import datetime
import traceback

app = FastAPI()

@app.get("/")  # лёгкий health-check
async def root():
    return {"status": "ok"}

@app.post("/process")
async def process_file(data: UploadFile = File(...)):
    try:
        # импортируем тяжёлую функцию только при загрузке файла
        from reconcile import reconcile

        # сохраняем входной файл во временную директорию
        input_path = f"/tmp/{data.filename}"
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        output_path = f"/tmp/file_processed_{timestamp}.xlsx"

        with open(input_path, "wb") as f:
            f.write(await data.read())

        # запускаем основную логику
        reconcile(input_path, output_path)

        # отдаем готовый файл пользователю
        return FileResponse(
            output_path,
            media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            filename=os.path.basename(output_path),
        )

    except Exception:
        # логируем полную трассировку в логи Render
        tb = traceback.format_exc()
        print(tb)
        # возвращаем её клиенту для дебага в n8n
        raise HTTPException(status_code=500, detail=tb)
