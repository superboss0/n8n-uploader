from __future__ import annotations

import traceback
from typing import Any

from fastapi import APIRouter, Body, HTTPException
from fastapi.responses import Response
from pydantic import BaseModel, Field, ValidationError, field_validator

from services.xlsx_builder import build_xlsx_bytes, normalize_file_name

router = APIRouter()


class XlsxSheetPayload(BaseModel):
    name: str = Field(min_length=1)
    rows: list[dict[str, Any]]

    @field_validator("name")
    @classmethod
    def validate_name(cls, value: str) -> str:
        stripped = value.strip()
        if not stripped:
            raise ValueError("sheet name must not be empty")
        return stripped


class XlsxBuildPayload(BaseModel):
    file_name: str | None = None
    sheets: list[XlsxSheetPayload]

    @field_validator("sheets")
    @classmethod
    def validate_sheets(cls, value: list[XlsxSheetPayload]) -> list[XlsxSheetPayload]:
        if not value:
            raise ValueError("sheets must contain at least one sheet")
        return value


def format_validation_error(exc: ValidationError) -> str:
    messages: list[str] = []
    for error in exc.errors():
        location = ".".join(str(part) for part in error["loc"])
        messages.append(f"{location}: {error['msg']}")
    return "; ".join(messages)


@router.post("/xlsx/build")
async def build_xlsx(payload: Any = Body(...)):
    try:
        parsed = XlsxBuildPayload.model_validate(payload)
    except ValidationError as exc:
        raise HTTPException(status_code=400, detail=format_validation_error(exc)) from exc

    try:
        file_name = normalize_file_name(parsed.file_name)
        content = build_xlsx_bytes(
            sheets=[sheet.model_dump() for sheet in parsed.sheets],
        )

        return Response(
            content=content,
            media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            headers={"Content-Disposition": f'attachment; filename="{file_name}"'},
        )
    except HTTPException:
        raise
    except Exception as exc:
        print(traceback.format_exc())
        raise HTTPException(status_code=500, detail="Failed to build xlsx file") from exc
