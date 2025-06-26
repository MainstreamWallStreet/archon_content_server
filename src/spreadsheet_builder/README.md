# Spreadsheet-Builder API

*(single-sheet, equation-friendly MVP · version 0.2)*

---

## 0 Scope & goals

* Build an **Excel workbook with one sheet** from a JSON "build-plan" that the LLM returns.
* Every cell is tagged as **fact**, **assumption**, or **calc**; calculated cells carry a native Excel formula.
* All **numbers arrive raw** (unscaled) with at most **two decimals** and an explicit **unit** note (`"dollars"`, `"percent"`, or `"vanilla"`).
* **Row 1** and **Column A** are reserved for *labels*; numeric data always start at **B2**.
* A1-style references only; builder raises normal **Python exceptions** on any validation failure.

---

## 1 End-to-end flow

```text
LLM ──► JSON build-plan ──► builder.build_from_plan() ──► .xlsx ──► returned path / URL
```

---

## 2 Build-plan JSON (v 0.2)

```jsonc
{
  "workbook": {
    "filename": "innv_model.xlsx"
  },

  "worksheet": {
    "name": "Model",

    /* === grid definition ===
       Labels:
         • Row-labels → Column A (row ≥2)
         • Col-labels → Row 1   (col ≥2)
       Data cells start at B2.
    */
    "columns": [                           // ordered, col ≥2
      {
        "col": 2,                          // 1-based; 2 == column B
        "header": "FY-2024",               // written into B1
        "cells": [
          {
            "row": 2,                      // 1-based; 2 == first data row
            "label": "Revenue",            // written into A2
            "type": "fact",
            "unit": "dollars",
            "value": 763900000,            // raw dollars
            "format": "currency_0dp"
          },
          {
            "row": 3,
            "label": "Participants",
            "type": "fact",
            "unit": "vanilla",
            "value": 7020,
            "format": "comma_0dp"
          },
          {
            "row": 4,
            "label": "Revenue per Participant",
            "type": "calc",
            "unit": "dollars",
            "formula": "=B2/B3",
            "format": "currency_2dp"
          }
        ]
      }

      /* add more column objects (C, D…) for scenarios / years */
    ],

    "named_ranges": [
      { "name": "Revenue",      "ref": "B2" },
      { "name": "Participants", "ref": "B3" }
    ]
  }
}
```

### Field rules

| Field        | Requirement                                                                              |              |           |
| ------------ | ---------------------------------------------------------------------------------------- | ------------ | --------- |
| `filename`   | `.xlsx` extension, no path separators                                                    |              |           |
| `col`, `row` | 1-based integers. **Must respect:** `col ≥ 2` for data columns, `row ≥ 2` for data rows. |              |           |
| `header`     | Text placed in **row 1** of the given column.                                            |              |           |
| `label`      | Text placed in **column A** of the given row.                                            |              |           |
| `type`       | `fact`                                                                                   | `assumption` | `calc`    |
| `unit`       | `dollars`                                                                                | `percent`    | `vanilla` |
| `value`      | Required when `type ≠ calc`; numeric ≤ 2 decimals.                                       |              |           |
| `formula`    | Required when `type = calc`; Excel A1 string beginning with `=`.                         |              |           |
| `format`     | One of the builtin format tokens (see § 4) or omitted for default.                       |              |           |

---

## 3 Python interface (`builder.py`)

```python
from pathlib import Path
from typing import Dict, Any


def build_from_plan(plan: Dict[str, Any],
                    output_dir: Path = Path(".")) -> Path:
    """
    Build an Excel workbook from a validated plan (v0.2).

    Returns: absolute Path to the saved file.

    Raises:
        SchemaError   – missing/invalid fields
        LayoutError   – label/data placed outside allowed grid
        FormulaError  – formula missing '=' or references out-of-sheet
        ValueError    – number >2 decimals, unknown unit/format, etc.
    """
```

All errors bubble up as Python exceptions; caller decides HTTP status etc.

---

## 4 Builtin number-format tokens

| Token          | Excel format string | Example render |
| -------------- | ------------------- | -------------- |
| `comma_0dp`    | `#,##0`             | 7 020          |
| `comma_2dp`    | `#,##0.00`          | 7 020.55       |
| `currency_0dp` | `$#,##0`            | $763,900,000   |
| `currency_2dp` | `$#,##0.00`         | $18.75         |
| `percent_1dp`  | `0.0%`              | 17.3 %         |
| `percent_2dp`  | `0.00%`             | 17.35 %        |

---

## 5 Validation highlights

* **Label & header collision** – Builder rejects any attempt to write a non-blank value outside row 1/col A rules.
* **Decimals** – Reject values whose textual representation has > 2 decimals (`round(value, 2) != value`).
* **Units vs. format** – Warning (not fatal): if `unit="percent"` but format token is not `percent_*`.
* **Formula safety** – No security stripping; API trusts internal users.

---

## 6 Example end-to-end call

```python
import json, builder
from pathlib import Path

with open("plan.json") as f:
    plan = json.load(f)

path = builder.build_from_plan(plan, output_dir=Path("/tmp"))
print("Workbook written to", path)
```

Open the resulting XLSX and verify:

* Row 1 headers (`FY-2024`, `FY-2025`, …)
* Column A labels (`Revenue`, `Participants`, …)
* Formulas live (e.g., `B4` shows `=B2/B3`)
* Formats and units rendered correctly.

---

### Future extensions (kept out of v 0.2)

* Multiple worksheets & cross-sheet formulas
* Data-validation for assumptions (dropdowns, sliders)
* Conditional styling (negative margins red)
* Chart & pivot-table builders

---

Enjoy — this spec now matches the clarified guidelines (raw dollars, two-decimal rule, fixed label rows/cols, simple A1 formulas, Python exceptions, no formula sanitising). 