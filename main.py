#!/usr/bin/env python3
import asyncio
from fastapi import FastAPI, UploadFile, File, HTTPException
from fastapi.responses import FileResponse
from starlette.concurrency import run_in_threadpool
import os
from datetime import datetime
import traceback

app = FastAPI()

@app.on_event("startup")
async def delay_startup_for_render():
    # Дать Render время на инициализацию перед health-check
    await asyncio.sleep(2)

@app.get("/")  # Health check endpoint
async def root():
    return {"status": "ok"}

@app.post("/process")
async def process_file(data: UploadFile = File(...)):
    try:
        # Импортировать reconcile только при необходимости
        from reconcile import reconcile

        # Сохраняем файл во временную директорию
        input_path = f"/tmp/{data.filename}"
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        output_path = f"/tmp/file_processed_{timestamp}.xlsx"

        with open(input_path, "wb") as f:
            f.write(await data.read())

        # Асинхронно запускаем тяжёлую CPU-операцию
        await run_in_threadpool(reconcile, input_path, output_path)

        # Отдаём обработанный файл пользователю
        return FileResponse(
            output_path,
            media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            filename=os.path.basename(output_path),
        )

    except Exception:
        tb = traceback.format_exc()
        print(tb)
        raise HTTPException(status_code=500, detail=tb)
