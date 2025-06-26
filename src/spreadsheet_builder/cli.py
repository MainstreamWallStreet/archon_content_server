from __future__ import annotations

"""Command-line helper: prompt → plan → spreadsheet (.xlsx).

Example usage::

    python -m src.spreadsheet_builder.cli --prompt "Model FY-2024 revenue…" -o /tmp

If no ``--prompt`` is given the tool falls back to *interactive* stdin input.

The script relies on:
    • OPENAI_API_KEY – optional; without it PlanGenerator runs in stub mode.

CLI tool to convert a free-form prompt into a Spreadsheet-Builder workbook.

It can be invoked in two ways:

1. Module style (recommended):

       python -m src.spreadsheet_builder.cli --prompt "…"

2. Direct file execution:

       python src/spreadsheet_builder/cli.py --prompt "…"

Running as a *file* means the parent *src* directory is **not** on ``sys.path``.
We therefore insert it at runtime so that absolute imports resolve correctly.
"""

import argparse
import json
import sys
from pathlib import Path
from typing import Any

# ───────────────────── dynamic path / imports ─────────────────────

if __package__ is None and __name__ == "__main__":  # executed as script
    # Add parent *src* directory so we can import `spreadsheet_builder`.
    _SRC_DIR = Path(__file__).resolve().parents[1]
    sys.path.insert(0, str(_SRC_DIR))
    from spreadsheet_builder import PlanGenerator, build_from_plan  # type: ignore
else:
    # Running via `python -m src.spreadsheet_builder.cli` – use relative import.
    from . import PlanGenerator, build_from_plan


def _parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    p = argparse.ArgumentParser(
        description="Generate spreadsheet from free-form prompt."
    )
    p.add_argument(
        "--objective", "-p", required=True, help="High-level modelling objective."
    )
    p.add_argument(
        "--data", "-d", required=True, help="Plaintext data (or @path to file)."
    )
    p.add_argument(
        "--output-dir",
        "-o",
        type=Path,
        default=Path.cwd(),
        help="Directory to write the resulting .xlsx (default: current dir)",
    )
    return p.parse_args(argv)


def main(argv: list[str] | None = None) -> None:  # pragma: no cover – manual tool
    args = _parse_args(argv)

    objective = args.objective
    if objective is None:
        print("Enter OBJECTIVE (end with Ctrl-D):", file=sys.stderr)
        objective = sys.stdin.read().strip()
        if not objective:
            print("Error: empty prompt", file=sys.stderr)
            sys.exit(1)

    data_txt = args.data or ""

    # Handle @file-path shorthand
    if data_txt.startswith("@") and Path(data_txt[1:]).exists():
        data_txt = Path(data_txt[1:]).read_text()

    generator = PlanGenerator()
    plan: dict[str, Any] = generator.generate(objective, data_txt)

    print("\n=== Generated build-plan JSON ===")
    print(json.dumps(plan, indent=2))

    try:
        output_path = build_from_plan(plan, output_dir=args.output_dir)
    except Exception as exc:  # noqa: BLE001
        print(f"\nError building spreadsheet: {exc}", file=sys.stderr)
        sys.exit(2)

    print(f"\nSpreadsheet written → {output_path}")


if __name__ == "__main__":  # pragma: no cover
    main()
