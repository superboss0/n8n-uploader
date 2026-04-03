#!/usr/bin/env python3
import asyncio
from fastapi import FastAPI, UploadFile, File, HTTPException, Form
from fastapi.responses import FileResponse
from starlette.concurrency import run_in_threadpool
import os
from datetime import datetime
import traceback
from pydantic import BaseModel

from routes import router as app_router

app = FastAPI(title="fin_tools")
app.include_router(app_router)

# Background task for Telethon listener
tg_task = None
tg_boot_task = None


async def _boot_tg_listener():
    global tg_task
    try:
        from tg_listener import install_handlers
        from tg_sender import client

        install_handlers()
        await asyncio.wait_for(client.start(), timeout=15)
        tg_task = asyncio.create_task(client.run_until_disconnected())
        print("✅ TG listener started")
    except Exception as e:
        # Do not block HTTP startup if Telegram is slow, misconfigured, or unavailable.
        print("⚠️ TG listener not started:", repr(e))


@app.on_event("startup")
async def startup():
    # Give Render some time before health-checks
    await asyncio.sleep(2)

    # Start TG listener in the background and let HTTP come up immediately.
    global tg_boot_task
    if os.getenv("DISABLE_TG_BOOT") == "1":
        print("ℹ️ TG listener boot disabled")
        return
    tg_boot_task = asyncio.create_task(_boot_tg_listener())


@app.on_event("shutdown")
async def shutdown():
    global tg_task, tg_boot_task
    try:
        from tg_sender import client

        if tg_boot_task:
            tg_boot_task.cancel()

        if tg_task:
            tg_task.cancel()

        await client.disconnect()
        print("✅ TG listener stopped")
    except Exception as e:
        print("⚠️ TG listener stop error:", repr(e))


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
    Send a text message via Telethon (MTProto) using TG_SESSION account.
    target: user_id (int) or '@username' or 'me'
    """
    try:
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
    Sends file to Telegram via Telethon.
    """
    try:
        from tg_sender import send_file

        target = target.strip()
        caption = (caption or "").strip() or None

        if not target:
            raise HTTPException(status_code=400, detail="target is required")

        safe_name = file.filename or "metabase_export.xlsx"
        tmp_path = f"/tmp/{safe_name}"

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


# --- Existing file processing API ---

@app.post("/process")
async def process_file(data: UploadFile = File(...)):
    try:
        from reconcile import reconcile

        # Save to tmp
        input_path = f"/tmp/{data.filename}"
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        output_path = f"/tmp/file_processed_{timestamp}.xlsx"

        with open(input_path, "wb") as f:
            f.write(await data.read())

        # Run CPU-heavy task in threadpool
        await run_in_threadpool(reconcile, input_path, output_path)

        # Return processed file
        return FileResponse(
            output_path,
            media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            filename=os.path.basename(output_path),
        )

    except Exception:
        tb = traceback.format_exc()
        print(tb)
        raise HTTPException(status_code=500, detail=tb)
