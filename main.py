from flask import Flask, request, send_file
import tempfile
import os
import datetime
from reconcile import reconcile

app = Flask(__name__)

@app.route("/")
def hello():
    return "🧾 Excel reconciliation API is working."

@app.route("/process", methods=["POST"])
def process():
    uploaded_file = request.files.get("data")
    if not uploaded_file:
        return "❌ No file uploaded", 400

    with tempfile.NamedTemporaryFile(delete=False, suffix=".xlsx") as tmp_in:
        uploaded_file.save(tmp_in.name)
        in_path = tmp_in.name

    timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
    out_path = os.path.join("/tmp", f"file_processed_{timestamp}.xlsx")

    reconcile(in_path, out_path)

    return send_file(
        out_path,
        as_attachment=True,
        download_name=os.path.basename(out_path),
        mimetype="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    )