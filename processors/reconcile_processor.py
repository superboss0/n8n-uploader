import os
import tempfile

from processors.registry import registry
from reconcile import reconcile


def reconcile_bytes(input_bytes: bytes) -> bytes:
    src_path = ""
    dst_path = ""

    try:
        with tempfile.NamedTemporaryFile(delete=False, suffix=".xlsx") as src:
            src.write(input_bytes)
            src_path = src.name

        with tempfile.NamedTemporaryFile(delete=False, suffix=".xlsx") as dst:
            dst_path = dst.name

        reconcile(src_path, dst_path)

        with open(dst_path, "rb") as result_file:
            return result_file.read()
    finally:
        for path in (src_path, dst_path):
            if path and os.path.exists(path):
                os.remove(path)


registry.register(
    "reconcile",
    reconcile_bytes,
    label="Сверка проводок по валютам",
    description="Один Excel -> несколько листов EUR/USD/RUB и matched-сверка.",
)
