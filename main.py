#!/usr/bin/env python3
import asyncio
from fastapi import FastAPI, UploadFile, File, HTTPException, Form
from fastapi.responses import FileResponse
from starlette.concurrency import run_in_threadpool
import os
from datetime import datetime
import traceback
from pydantic import BaseModel


app = FastAPI()

@app.on_event("startup")
async def delay_startup_for_render():
    # Дать Render время на инициализацию перед health-check
    await asyncio.sleep(2)

@app.get("/")  # Health check endpoint
async def root():
    return {"status": "ok"}

# --- TG Sender API ---

class TgSendRequest(BaseModel):
    target: str | int
    text: str

@app.post("/tg/send")
async def tg_send(payload: TgSendRequest):
    """
    Отправляет сообщение через Telethon (MTProto) от аккаунта, заданного TG_SESSION.
    target: user_id (int) или '@username' или 'me'
    """
    try:
        # Импортируем только по факту, чтобы сервис мог стартовать без env при локальном тесте
        from tg_sender import send_tg

        target = str(payload.target).strip()
        text = payload.text.strip()

        if not target:
            raise HTTPException(status_code=400, detail="target is required")
        if not text:
            raise HTTPException(status_code=400, detail="text is required")

        await send_tg(target, text)
        return {"ok": True}

    except HTTPException:
        raise
    except Exception:
        tb = traceback.format_exc()
        print(tb)
        raise HTTPException(status_code=500, detail=tb)


@app.post("/tg/send_file")
async def tg_send_file(
    target: str = Form(...),
    caption: str | None = Form(None),
    file: UploadFile = File(...),
):
    """
    multipart/form-data: target, caption, file
    """
    try:
        # ВАЖНО: функция называется send_file (а не send_file_tg)
        from tg_sender import send_file

        target = target.strip()
        caption = (caption or "").strip() or None

        if not target:
            raise HTTPException(status_code=400, detail="target is required")

        # сохраняем во временный файл
        tmp_path = f"/tmp/{file.filename}"
        with open(tmp_path, "wb") as f:
            f.write(await file.read())

        await send_file(target, tmp_path, caption=caption)
        return {"ok": True}

    except HTTPException:
        raise
    except Exception:
        tb = traceback.format_exc()
        print(tb)
        raise HTTPException(status_code=500, detail=tb)

# --- Existing file processing ---

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
