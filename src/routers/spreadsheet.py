from __future__ import annotations

"""Router exposing a single endpoint to generate Spreadsheet-Builder workbooks."""

from pathlib import Path
from tempfile import mkdtemp

from fastapi import APIRouter, HTTPException
from fastapi.responses import FileResponse
from pydantic import BaseModel, Field

from src.auth import APIKeyAuth
from src.spreadsheet_builder import PlanGenerator, build_from_plan

router = APIRouter(tags=["generation"])


class SpreadsheetRequest(BaseModel):
    """Body schema for `/generate-spreadsheet`.

    objective:
        Modelling goal passed verbatim to the LLM.
    data:
        Optional plain-text context or @filepath shorthand.
    """

    objective: str = Field(..., example="Model FY-2024 revenue break-even")
    data: str | None = Field(
        None,
        example="Revenue: 763.9M, Participants: 7020",
        description="Plaintext data or '@/abs/path.txt' to read from file.",
    )


@router.post(
    "/generate-spreadsheet",
    summary="Generate an Excel workbook via LLM",
    response_description="The generated .xlsx file is returned as a download.",
    response_class=FileResponse,
)
async def generate_spreadsheet(body: SpreadsheetRequest, api_key: APIKeyAuth):
    """LLM → build-plan → workbook → download pipeline."""

    # 1️⃣ Obtain plan from LLM
    generator = PlanGenerator()
    try:
        plan = generator.generate(body.objective, body.data or "")
    except RuntimeError as exc:  # Missing API key etc.
        raise HTTPException(status_code=503, detail=str(exc))
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status_code=500, detail=f"Error generating plan: {exc}")

    # 2️⃣ Build workbook in temp dir
    tmp_dir = Path(mkdtemp(prefix="sbuilder_"))
    try:
        output_path = build_from_plan(plan, output_dir=tmp_dir)
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(
            status_code=500, detail=f"Error building spreadsheet: {exc}"
        )

    # 3️⃣ Stream file back
    return FileResponse(
        path=output_path,
        filename=output_path.name,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    )
