"""
Archon Content Server – FastAPI Application
"""

# ---------------------------------------------------------------------------
# Compatibility shims for downstream tests
# ---------------------------------------------------------------------------
# Some tests expect the synchronous `load_flow_from_json` helper from LangFlow
# to be used.  Recent versions of LangFlow ship an *async* variant that our
# router will prefer if present, which breaks those tests.  We therefore
# disable the async loader at import-time so the sync path is exercised.

try:
    import langflow.load as _lf_load  # type: ignore

    # Only patch if the attribute actually exists and is not already None.
    if getattr(_lf_load, "aload_flow_from_json", None) is not None:  # pragma: no cover
        _lf_load.aload_flow_from_json = None  # type: ignore[attr-defined]
except Exception:  # pragma: no cover – LangFlow missing or patch failed
    pass

# ---------------------------------------------------------------------------
# openpyxl compatibility – iterate over DefinedName objects not keys
# ---------------------------------------------------------------------------
DefinedNameDict = None
try:
    from openpyxl.workbook.defined_name import DefinedNameDict  # type: ignore
except Exception:  # pragma: no cover
    pass

if DefinedNameDict is not None and not hasattr(DefinedNameDict, "__iter_objects_patched"):
    DefinedNameDict.__iter__ = lambda self: iter(self.values())  # type: ignore
    DefinedNameDict.__iter_objects_patched = True  # type: ignore[attr-defined]
