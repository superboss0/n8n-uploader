from fastapi import FastAPI, UploadFile, File, HTTPException
from fastapi.responses import FileResponse
import os
from datetime import datetime
from reconcile import reconcile
import traceback

app = FastAPI()

@app.post("/process")
async def process_file(data: UploadFile = File(...)):
    try:
        input_path = f"/tmp/{data.filename}"
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        output_path = f"/tmp/file_processed_{timestamp}.xlsx"

        # сохраняем
        with open(input_path, "wb") as f:
            f.write(await data.read())

        # главный рабочий код
        reconcile(input_path, output_path)

        return FileResponse(
            output_path,
            media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            filename=os.path.basename(output_path),
        )

    except Exception as e:
        # напечатать полную трассировку в логи Render
        tb = traceback.format_exc()
        print(tb)

        # и вернуть её клиенту, чтобы HTTP Request нода видела detail
        raise HTTPException(status_code=500, detail=tb)
