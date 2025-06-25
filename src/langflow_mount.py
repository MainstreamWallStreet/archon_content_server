"""Helper to attach LangFlow as a sub-application.

Usage::

    from src.langflow_mount import attach_langflow
    attach_langflow(app, "/langflow")

If LangFlow is not installed in the current environment the function
returns immediately, so importing it never breaks local development.
"""

from fastapi import FastAPI


def attach_langflow(parent: FastAPI, prefix: str = "/langflow") -> None:  # pragma: no cover
    """Mount the LangFlow application on *parent* under *prefix*.

    Parameters
    ----------
    parent: FastAPI
        The main application where LangFlow should be mounted.
    prefix: str, default="/langflow"
        URL prefix under which LangFlow will be accessible.
    """

    try:
        # Prefer full LangFlow application with frontend (static files)
        try:
            from langflow.main import setup_app as _create_langflow_app  # type: ignore
        except ImportError:  # Fallback for older versions
            from langflow.main import create_app as _create_langflow_app  # type: ignore
    except (ImportError, ModuleNotFoundError):
        # LangFlow not available – nothing to do.
        return

    # -------------------------------------------------------------------
    # Front-end (static files) -------------------------------------------
    # -------------------------------------------------------------------
    from fastapi.staticfiles import StaticFiles
    from fastapi.responses import HTMLResponse
    from pathlib import Path

    try:
        from langflow.main import get_static_files_dir  # type: ignore
    except ImportError:
        # Path relative fallback (should not happen)
        import importlib.resources as pkg_resources

        static_dir = Path(pkg_resources.files("langflow")) / "frontend"
    else:
        static_dir = get_static_files_dir()

    # Mount BEFORE the backend so that asset requests are served directly and
    # are not caught by the backend application.
    parent.mount(f"{prefix}/assets", StaticFiles(directory=static_dir / "assets"), name="langflow-assets")

    # -------------------------------------------------------------------
    # Index file ---------------------------------------------------------
    # -------------------------------------------------------------------
    # Serve the modified index.html at <prefix>/ (with corrected <base href>)
    index_path = static_dir / "index.html"
    original_index = index_path.read_text(encoding="utf-8")
    adjusted_index = original_index.replace('<base href="/" />', f'<base href="{prefix}/" />', 1)

    @parent.get(f"{prefix}/", include_in_schema=False)
    async def _langflow_index() -> HTMLResponse:  # type: ignore[override]
        return HTMLResponse(adjusted_index)

    # -------------------------------------------------------------------
    # Backend (API) ------------------------------------------------------
    # -------------------------------------------------------------------
    # Mount the LangFlow backend *after* the index route so that the custom
    # index takes precedence for the exact "/langflow/" path.

    try:
        backend_app = _create_langflow_app(backend_only=True)  # type: ignore[arg-type]
    except TypeError:
        backend_app = _create_langflow_app()  # type: ignore[assignment]

    parent.mount(f"{prefix}", backend_app, name="langflow-backend") 