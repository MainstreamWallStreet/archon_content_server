from __future__ import annotations

"""Shared specification enums for Spreadsheet Builder plans."""

import enum
from typing import Any

__all__ = [
    "CellType",
    "Unit",
    "FormatToken",
    "validate_cell_type",
    "validate_unit",
    "validate_format",
]


class CellType(str, enum.Enum):
    """Allowed cell ``type`` values in build-plan."""

    FACT = "fact"
    ASSUMPTION = "assumption"
    CALC = "calc"


class Unit(str, enum.Enum):
    """Allowed unit annotations for numeric cells."""

    DOLLARS = "dollars"
    PERCENT = "percent"
    VANILLA = "vanilla"


class FormatToken(str, enum.Enum):
    """Builtin number-format identifiers (see README § 4)."""

    COMMA_0DP = "comma_0dp"
    COMMA_2DP = "comma_2dp"
    CURRENCY_0DP = "currency_0dp"
    CURRENCY_2DP = "currency_2dp"
    PERCENT_1DP = "percent_1dp"
    PERCENT_2DP = "percent_2dp"

    @classmethod
    def for_unit(cls, unit: Unit) -> list["FormatToken"]:
        if unit is Unit.DOLLARS:
            return [cls.CURRENCY_0DP, cls.CURRENCY_2DP]
        if unit is Unit.PERCENT:
            return [cls.PERCENT_1DP, cls.PERCENT_2DP]
        return [cls.COMMA_0DP, cls.COMMA_2DP]


# ---------------------------------------------------------------------------
# Helper validation functions (LLM & runtime reuse)
# ---------------------------------------------------------------------------

def _ensure_enum(value: str, enum_cls: type[enum.Enum], field: str) -> enum.Enum:
    try:
        return enum_cls(value)  # type: ignore[arg-type]
    except ValueError as e:
        msg = f"Unknown {field} '{value}'. Allowed: {[m.value for m in enum_cls]}"
        raise ValueError(msg) from e


def validate_cell_type(value: str) -> CellType:  # noqa: D401 – simple helper
    """Return ``CellType`` or raise ``ValueError`` if invalid."""
    return _ensure_enum(value, CellType, "cell type")  # type: ignore[return-value]


def validate_unit(value: str) -> Unit:
    return _ensure_enum(value, Unit, "unit")  # type: ignore[return-value]


def validate_format(value: str) -> FormatToken:
    return _ensure_enum(value, FormatToken, "format token")  # type: ignore[return-value] 