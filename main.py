from fastapi import FastAPI, UploadFile, File
from fastapi.responses import FileResponse
import os
from datetime import datetime
from reconcile import reconcile

app = FastAPI()

@app.post("/process")
async def process_file(data: UploadFile = File(...)):
    input_path = f"/tmp/{data.filename}"
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    output_path = f"/tmp/file_processed_{timestamp}.xlsx"

    with open(input_path, "wb") as f:
        f.write(await data.read())

    reconcile(input_path, output_path)
    return FileResponse(output_path, media_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet', filename=os.path.basename(output_path))
