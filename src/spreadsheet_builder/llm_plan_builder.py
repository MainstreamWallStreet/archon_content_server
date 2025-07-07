from __future__ import annotations

"""llm_plan_builder.py – convert free-form user text into a v0.2 build-plan.

This is a **placeholder** implementation suitable for offline / unit-test use.
When an ``OPENAI_API_KEY`` environment variable is available, it will call
OpenAI *o3* (latest lightweight model) via LangChain to reason about the spreadsheet plan.
Otherwise, a deterministic sample plan (identical to the unit-test fixture) is
returned so that tests do not need live network access.
"""

import json
import logging
import os
from typing import Any, Dict

from langchain_openai import ChatOpenAI
from langchain.schema import HumanMessage, SystemMessage

from .spec import CellType, Unit, FormatToken

log = logging.getLogger("llm_plan_builder")
DEFAULT_FILENAME = "llm_model.xlsx"

SCHEMA_HINT = (
    "Spreadsheet-Builder v0.2 expects JSON with *exactly* these top-level keys:\n"
    "workbook → {filename}.  worksheet → {name, columns, named_ranges}.\n"
    "Each column object: {col, header, cells}.  Each cell object: {row, label, type, unit, value|formula, format}.\n\n"
    "Allowed enums:\n"
    f"  type → {[m.value for m in CellType]}\n"
    f"  unit → {[m.value for m in Unit]}\n"
    f"  format → {[m.value for m in FormatToken]}\n\n"
    "Example minimal JSON (single column):\n"
    '{"workbook":{"filename":"model.xlsx"},"worksheet":{"name":"Model","columns":[{"col":2,"header":"FY-2024","cells":[{"row":2,"label":"Revenue","type":"fact","unit":"dollars","value":100,"format":"currency_0dp"}]}],"named_ranges":[]}}'
)


class PlanGenerator:
    """Generate a validated Spreadsheet-Builder plan for a given *objective* using provided *plaintext data*."""

    def __init__(self, model_name: str | None = None):
        api_key = os.getenv("OPENAI_API_KEY")
        self.llm: ChatOpenAI | None = None
        if api_key:
            self.llm = ChatOpenAI(
                model_name=model_name or "o3",
                temperature=1.0,
                request_timeout=45,
                model_kwargs={"response_format": {"type": "json_object"}},
            )
            log.info("LLM PlanGenerator initialised with model %s", self.llm.model_name)
        else:
            log.warning("OPENAI_API_KEY not set – PlanGenerator will run in stub mode.")

    # ------------------------------------------------------------------
    # Public helper
    # ------------------------------------------------------------------
    def generate(self, objective: str, plaintext_data: str = "") -> Dict[str, Any]:
        """Return a **validated** build-plan dict based on objective & data.

        Parameters
        ----------
        objective:
            High-level modelling goal (e.g. "Project FY-2025 cash flow").
        plaintext_data:
            Raw context the LLM can extract numbers from (CSV, pasted table, prose).
        """

        # Fail fast if no LLM available unless explicit stub requested via env.
        if not self.llm:
            if os.getenv("FORCE_STUB", "").lower() in {"1", "true", "yes"}:
                return _sample_plan()
            raise RuntimeError("OPENAI_API_KEY is required for online plan generation.")

        sys_msg = SystemMessage(
            content=(
                "You are a spreadsheet-modelling assistant.\n"
                "Create a valid v0.2 *Spreadsheet-Builder* JSON plan (single sheet).\n"
                "• Use the OBJECTIVE section to decide labels & structure.\n"
                "• Use the DATA section to source raw numeric values.\n"
                "• All numeric values raw (≤2dp) with explicit unit + format token.\n\n"
                + SCHEMA_HINT
                + "\nReturn ONLY JSON – no markdown fences."
            )
        )

        user_content = (
            "OBJECTIVE:\n"
            + objective.strip()
            + "\n\n"
            + "DATA:\n"
            + (plaintext_data.strip() or "(none)")
        )
        human = HumanMessage(content=user_content)

        base_msgs = [sys_msg, human]
        max_tries = 3
        last_err: str | None = None

        for attempt in range(1, max_tries + 1):
            rsp = self.llm.invoke(base_msgs)  # type: ignore[assignment]
            raw = rsp.content.strip()

            # Try to parse strictly JSON
            try:
                plan = json.loads(raw)
            except Exception as exc:
                last_err = f"JSON parse error: {exc}"
            else:
                try:
                    _basic_validate(plan)
                    return plan  # success
                except Exception as exc:
                    last_err = f"Validation error: {exc}"

            # prepare feedback message and retry
            feedback = (
                f"The previous response had an error → {last_err}.\n"
                "Please correct it and return ONLY JSON. Remember the schema and enums: \n"
                + SCHEMA_HINT
            )
            base_msgs.append(HumanMessage(content=feedback))

        raise ValueError(
            f"Unable to obtain valid plan after {max_tries} attempts. Last error: {last_err}"
        )


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------


def _sample_plan() -> Dict[str, Any]:
    """Return deterministic plan identical to tests' fixture."""

    return {
        "workbook": {"filename": DEFAULT_FILENAME},
        "worksheet": {
            "name": "Model",
            "columns": [
                {
                    "col": 2,
                    "header": "FY-2024",
                    "cells": [
                        {
                            "row": 2,
                            "label": "Revenue",
                            "type": CellType.FACT.value,
                            "unit": Unit.DOLLARS.value,
                            "value": 763900000,
                            "format": FormatToken.CURRENCY_0DP.value,
                        },
                        {
                            "row": 3,
                            "label": "Participants",
                            "type": CellType.FACT.value,
                            "unit": Unit.VANILLA.value,
                            "value": 7020,
                            "format": FormatToken.COMMA_0DP.value,
                        },
                        {
                            "row": 4,
                            "label": "Revenue per Participant",
                            "type": CellType.CALC.value,
                            "unit": Unit.DOLLARS.value,
                            "formula": "=B2/B3",
                            "format": FormatToken.CURRENCY_2DP.value,
                        },
                    ],
                }
            ],
            "named_ranges": [
                {"name": "Revenue", "ref": "B2"},
                {"name": "Participants", "ref": "B3"},
            ],
        },
    }


def _basic_validate(plan: Dict[str, Any]) -> None:  # pragma: no cover – light
    """Lightweight enum validation to reject obviously broken LLM output."""

    try:
        columns = plan["worksheet"]["columns"]
        for col in columns:
            for cell in col["cells"]:
                CellType(cell["type"])  # type: ignore[arg-type]
                Unit(cell["unit"])
                if fmt := cell.get("format"):
                    FormatToken(fmt)
    except Exception as exc:
        raise ValueError("Invalid LLM plan structure") from exc
