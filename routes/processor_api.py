import html
import os
import re
import tempfile
import traceback

from fastapi import APIRouter, File, Form, HTTPException, UploadFile
from fastapi.responses import HTMLResponse, Response

import processors
from fg_vs_mb_reconcile import reconcile_files
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
        (
            f'<option value="{html.escape(spec.name)}">'
            f"{html.escape(spec.label)}"
            f"</option>"
        )
        for spec in registry.list()
    )
    processor_cards = "\n".join(
        (
            '<div class="processor-line">'
            f'<div class="processor-title">{html.escape(spec.label)}</div>'
            f'<div class="processor-desc">{html.escape(spec.description)}</div>'
            "</div>"
        )
        for spec in registry.list()
        if spec.description
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

    .card + .card {{
      margin-top: 18px;
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

    .processor-list {{
      margin-top: 10px;
      margin-bottom: 14px;
      padding: 12px 14px;
      border: 1px dashed var(--border);
      border-radius: 12px;
      background: rgba(255, 255, 255, 0.7);
    }}

    .processor-line + .processor-line {{
      margin-top: 10px;
      padding-top: 10px;
      border-top: 1px solid var(--border);
    }}

    .processor-title {{
      font-size: 14px;
      font-weight: 700;
    }}

    .processor-desc {{
      margin-top: 4px;
      font-size: 13px;
      color: var(--muted);
      line-height: 1.45;
    }}
  </style>
</head>
<body>
  <div>
    <main class="card">
      <h1>Обработка Excel</h1>
      <p>Единая точка входа для бухгалтерских Excel-сценариев. Старые API-маршруты остаются рабочими.</p>

      <div class="processor-list">
        {processor_cards}
      </div>

      <form action="/run-processor" method="post" enctype="multipart/form-data">
        <label for="processor">Тип обработки</label>
        <select name="processor" id="processor" required>
          {options}
        </select>

        <label for="file">Файл</label>
        <input id="file" type="file" name="file" accept=".xlsx,.xls" required />

        <button type="submit">Обработать файл</button>
      </form>

      <div class="hint">Подходит для одиночных преобразований, включая старый <code>reconcile</code> и новый FinGrad transform.</div>
    </main>

    <main class="card">
      <h1>Сверка Metabase vs FinGrad</h1>
      <p>Загрузите два отчета и получите Excel с расхождениями и подсветкой.</p>

      <form action="/run-fg-mb-reconcile" method="post" enctype="multipart/form-data">
        <label for="file_a">Файл из Metabase</label>
        <input id="file_a" type="file" name="file_a" accept=".xlsx,.xls" required />

        <label for="file_b">Файл из FinGrad</label>
        <input id="file_b" type="file" name="file_b" accept=".xlsx,.xls" required />

        <button type="submit">Сверить отчеты</button>
      </form>

      <div class="hint">Этот сценарий перенесен из <code>fg-rec-transform-service</code> в текущий сервис.</div>
    </main>
  </div>
</body>
</html>"""


@router.post("/run-processor")
async def run_processor(
    processor: str = Form(...),
    file: UploadFile = File(...),
):
    try:
        processor_spec = registry.get(processor)
        if not processor_spec:
            raise HTTPException(status_code=404, detail=f"Unknown processor: {processor}")

        filename = file.filename or "input.xlsx"
        if not filename.lower().endswith((".xlsx", ".xls")):
            raise HTTPException(status_code=400, detail="Please upload an Excel file (.xlsx / .xls)")

        input_bytes = await file.read()
        output_bytes = processor_spec.handler(input_bytes)
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


@router.post("/run-fg-mb-reconcile")
async def run_fg_mb_reconcile(
    file_a: UploadFile = File(...),
    file_b: UploadFile = File(...),
):
    a_path = ""
    b_path = ""
    out_path = ""

    try:
        for upload_file, field_name in ((file_a, "file_a"), (file_b, "file_b")):
            filename = upload_file.filename or ""
            if not filename.lower().endswith((".xlsx", ".xls")):
                raise HTTPException(status_code=400, detail=f"{field_name} must be an Excel file (.xlsx / .xls)")

        suffix_a = os.path.splitext(file_a.filename or "")[1] or ".xlsx"
        suffix_b = os.path.splitext(file_b.filename or "")[1] or ".xlsx"

        with tempfile.NamedTemporaryFile(delete=False, suffix=suffix_a) as tmp_a:
            a_path = tmp_a.name
            tmp_a.write(await file_a.read())

        with tempfile.NamedTemporaryFile(delete=False, suffix=suffix_b) as tmp_b:
            b_path = tmp_b.name
            tmp_b.write(await file_b.read())

        out_path, _report_kind = reconcile_files(a_path, b_path)

        with open(out_path, "rb") as result_file:
            output_bytes = result_file.read()

        return Response(
            content=output_bytes,
            media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            headers={"Content-Disposition": f'attachment; filename="{os.path.basename(out_path)}"'},
        )
    except HTTPException:
        raise
    except Exception:
        tb = traceback.format_exc()
        print(tb)
        raise HTTPException(status_code=500, detail=tb)
    finally:
        for path in (a_path, b_path, out_path):
            if path and os.path.exists(path):
                os.remove(path)
