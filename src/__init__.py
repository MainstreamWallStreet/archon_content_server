"""
Archon Content Server – FastAPI Application
"""

# ---------------------------------------------------------------------------
# openpyxl compatibility – iterate over DefinedName objects not keys
# ---------------------------------------------------------------------------
try:
    from openpyxl.workbook.defined_name import DefinedNameDict  # type: ignore

    if not hasattr(DefinedNameDict, "__iter_objects_patched"):
        DefinedNameDict.__iter__ = lambda self: iter(self.values())  # type: ignore
        DefinedNameDict.__iter_objects_patched = True  # type: ignore[attr-defined]
except Exception:  # pragma: no cover
    # openpyxl not available or import failed, skip the patch
    pass
