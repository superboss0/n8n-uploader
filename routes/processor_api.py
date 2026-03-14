import html
import re
import traceback

from fastapi import APIRouter, File, Form, HTTPException, UploadFile
from fastapi.responses import HTMLResponse, Response

import processors
from processors.registry import registry

router = APIRouter()


def make_safe_download_name(filename: str, processor_name: str) -> str:
    base_name = (filename or "input.xlsx").rsplit(".", 1)[0].strip()
    safe = re.sub(r"[^A-Za-z0-9._-]+", "_", base_name).strip("._")

    if not safe:
        safe = "file"

    return f"{safe}_{processor_name}_processed.xlsx"


@router.get("/upload", response_class=HTMLResponse)
async def upload_form() -> str:
    options = "\n".join(
        f'<option value="{html.escape(name)}">{html.escape(name)}</option>'
        for name in registry.list_names()
    )

    return f"""<!DOCTYPE html>
<html lang="ru">
<head>
  <meta charset="UTF-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1.0" />
  <title>Обработка Excel</title>
  <style>
    :root {{
      --bg: #f3efe7;
      --panel: #fffdf9;
      --text: #1f2937;
      --muted: #6b7280;
      --accent: #d97706;
      --accent-hover: #b45309;
      --border: #eadfce;
    }}

    * {{
      box-sizing: border-box;
    }}

    body {{
      margin: 0;
      min-height: 100vh;
      font-family: Georgia, "Times New Roman", serif;
      color: var(--text);
      background:
        radial-gradient(circle at top left, rgba(217, 119, 6, 0.14), transparent 30%),
        linear-gradient(135deg, #efe6d7, var(--bg));
      display: grid;
      place-items: center;
      padding: 24px;
    }}

    .card {{
      width: min(100%, 560px);
      background: var(--panel);
      border: 1px solid var(--border);
      border-radius: 20px;
      padding: 28px;
      box-shadow: 0 20px 50px rgba(69, 46, 19, 0.12);
    }}

    h1 {{
      margin: 0 0 10px;
      font-size: 32px;
      line-height: 1.1;
    }}

    p {{
      margin: 0 0 18px;
      color: var(--muted);
      line-height: 1.5;
    }}

    label {{
      display: block;
      margin: 16px 0 8px;
      font-size: 14px;
      font-weight: 700;
    }}

    select, input[type="file"], button {{
      width: 100%;
      border-radius: 12px;
      font: inherit;
    }}

    select, input[type="file"] {{
      padding: 12px 14px;
      border: 1px solid var(--border);
      background: #fff;
    }}

    button {{
      margin-top: 18px;
      border: none;
      padding: 14px 18px;
      color: #fff;
      background: var(--accent);
      font-weight: 700;
      cursor: pointer;
    }}

    button:hover {{
      background: var(--accent-hover);
    }}

    .hint {{
      margin-top: 16px;
      font-size: 13px;
      color: var(--muted);
    }}
  </style>
</head>
<body>
  <main class="card">
    <h1>Обработка Excel</h1>
    <p>Выберите тип обработки, загрузите исходный файл и получите готовый результат обратно.</p>

    <form action="/run-processor" method="post" enctype="multipart/form-data">
      <label for="processor">Тип обработки</label>
      <select name="processor" id="processor" required>
        {options}
      </select>

      <label for="file">Файл</label>
      <input id="file" type="file" name="file" accept=".xlsx,.xls" required />

      <button type="submit">Обработать файл</button>
    </form>

    <div class="hint">Старый endpoint <code>/process</code> продолжает работать без изменений.</div>
  </main>
</body>
</html>"""


@router.post("/run-processor")
async def run_processor(
    processor: str = Form(...),
    file: UploadFile = File(...),
):
    try:
        processor_func = registry.get(processor)
        if not processor_func:
            raise HTTPException(status_code=404, detail=f"Unknown processor: {processor}")

        filename = file.filename or "input.xlsx"
        if not filename.lower().endswith((".xlsx", ".xls")):
            raise HTTPException(status_code=400, detail="Please upload an Excel file (.xlsx / .xls)")

        input_bytes = await file.read()
        output_bytes = processor_func(input_bytes)
        output_name = make_safe_download_name(filename, processor)

        return Response(
            content=output_bytes,
            media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            headers={"Content-Disposition": f'attachment; filename="{output_name}"'},
        )
    except HTTPException:
        raise
    except Exception:
        tb = traceback.format_exc()
        print(tb)
        raise HTTPException(status_code=500, detail=tb)
