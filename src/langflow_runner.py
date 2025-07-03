"""Utility to load and execute LangFlow JSON flows."""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any, Callable

try:
    from langflow.load import load_flow_from_json
    # Disable LangFlow tracing globally to avoid runtime errors when no
    # tracing backend/context is active. We monkey-patch the
    # `trace_component` method to return a no-op async context manager.
    try:
        from langflow.services.tracing.service import TracingService

        class _NullAsyncTracer:  # noqa: D401
            async def __aenter__(self):
                return self

            async def __aexit__(self, exc_type, exc, tb):
                return False

        def _noop_trace_component(self, *_, **__):  # noqa: D401
            return _NullAsyncTracer()

        TracingService.trace_component = _noop_trace_component  # type: ignore[assignment]

        # Patch TracingService.set_outputs as a no-op to avoid "no component context" errors
        TracingService.set_outputs = lambda *_, **__: None  # type: ignore[assignment]

        # Patch VariableService.get_variable so that it simply returns the
        # requested secret from the environment if available, otherwise a
        # stub string – preventing OPENAI_API_KEY lookup failures.
        try:
            from langflow.services.variable.service import VariableService

            async def _env_get_variable(self, user_id, name: str, field: str, session=None):  # noqa: D401
                return os.environ.get(name, os.environ.get(field, "stub-secret"))

            VariableService.get_variable = _env_get_variable  # type: ignore[assignment]
        except Exception:
            pass
    except Exception:
        # If TracingService import fails, ignore – not critical.
        pass
except Exception:  # pragma: no cover - optional dependency
    load_flow_from_json = None

# Auto-load environment variables from a local .env file so that the
# OPENAI_API_KEY (and any others) are available during flow execution.
# This is a no-op if python-dotenv is unavailable or the variables are
# already set – so it is safe in production environments where the
# variables might be injected via Kubernetes/Cloud Run/etc.
try:
    from dotenv import load_dotenv

    # Only load .env if the key is still missing so we do not override
    # any environment provided by the host.
    if "OPENAI_API_KEY" not in os.environ:
        # Look for a .env file in the workspace root (the repo root).
        load_dotenv()
except Exception:  # pragma: no cover – optional dependency / graceful degradation
    pass


def _compile_flow(flow: Any) -> Callable[[dict[str, str]], Any]:
    """Return a callable for the given LangFlow *flow* object."""
    if hasattr(flow, "build"):
        return flow.build()
    if hasattr(flow, "compile"):
        return flow.compile()  # type: ignore[attr-defined]
    if hasattr(flow, "prepare") and hasattr(flow, "start"):

        def _run(input_dict: dict[str, str]):
            flow.prepare()
            gen = flow.start(inputs=[input_dict])  # type: ignore[attr-defined]
            last: Any | None = None
            for last in gen:
                pass
            return last or {}

        return _run
    if callable(flow):
        return flow
    raise RuntimeError(
        "Unsupported LangFlow object: expected .build()/.compile()/.prepare()+start() or callable"
    )


def run_langflow_json(
    flow_path: str | Path, query: str, debug_file: str | None = None
) -> tuple[str, dict[str, Any], dict[str, Any]]:
    """Run a LangFlow flow defined in *flow_path* with *query*.

    Parameters
    ----------
    flow_path: str | Path
        Path to the JSON flow definition.
    query: str
        Input query string for the flow.
    debug_file: str | None
        Optional path to write debug information.

    Returns
    -------
    tuple[str, dict, dict]
        The extracted result string, debug info and raw outputs.
    """
    if load_flow_from_json is None:
        raise RuntimeError("LangFlow is not installed.")

    os.environ.setdefault("LANGFLOW_USER_ID", "api-client")

    flow = load_flow_from_json(str(flow_path))
    compiled = _compile_flow(flow)

    try:
        from langflow.schema.schema import INPUT_FIELD_NAME  # type: ignore
    except Exception:  # pragma: no cover
        INPUT_FIELD_NAME = "input_value"

    try:
        outputs = compiled({INPUT_FIELD_NAME: query})
    except Exception as first_exc:  # noqa: BLE001
        # Fallback #1: common key used by TextInput components
        try:
            outputs = compiled({"text": query})
        except Exception:
            # Fallback #2: attempt to target TextInput node IDs directly
            try:
                flow_json: dict[str, Any]
                with open(flow_path, "r") as f:
                    flow_json = json.load(f)
                nodes = flow_json.get("data", {}).get("nodes", [])
                text_input_ids = [
                    node.get("data", {}).get("id")
                    for node in nodes
                    if node.get("data", {}).get("type") == "TextInput"
                ]
                attempted: list[Exception] = []
                outputs = None  # type: ignore[assignment]
                # First, try simple mapping of node id to query
                for nid in text_input_ids:
                    try:
                        outputs = compiled({nid: query})
                        break
                    except Exception as exc:
                        attempted.append(exc)
                # If that failed, try mapping nested under 'input_value'
                if outputs is None:
                    for nid in text_input_ids:
                        try:
                            outputs = compiled({nid: {"input_value": query}})
                            break
                        except Exception as exc:
                            attempted.append(exc)
                if outputs is None:
                    # All fallbacks failed – attempt manual injection into TextInput nodes
                    try:
                        # Manually prepare and run the flow if it exposes a vertex map
                        if hasattr(flow, "vertex_map"):
                            flow.prepare()
                            for vertex in flow.vertex_map.values():
                                comp = getattr(vertex, "custom_component", None)
                                if comp is not None:
                                    # Inject user_id if component expects it and it's missing
                                    if hasattr(comp, "user_id") and (not getattr(comp, "user_id", None)):
                                        # Attempt to set the private attribute used by the property
                                        try:
                                            import uuid
                                            setattr(
                                                comp,
                                                "_user_id",
                                                os.environ.get("LANGFLOW_USER_ID", "00000000-0000-0000-0000-000000000000"),
                                            )
                                        except Exception:
                                            pass
                                    # Inject OpenAI API key if the component expects it
                                    if hasattr(comp, "openai_api_key") and (not getattr(comp, "openai_api_key", None)):
                                        comp.openai_api_key = os.environ.get("OPENAI_API_KEY", "sk-restricted")
                                    # Provide a dummy tracing service to avoid RuntimeError when LangFlow
                                    # components attempt to trace outside an active context.
                                    if hasattr(comp, "_tracing_service") and getattr(comp, "_tracing_service", None) is None:
                                        class _NullAsyncContext:  # noqa: D401
                                            """Minimal async context manager that does nothing."""

                                            async def __aenter__(self):
                                                return self

                                            async def __aexit__(self, exc_type, exc, tb):
                                                return False

                                        class _NullTracingService:  # noqa: D401
                                            """Stub replacement for LangFlow's TracingService."""

                                            def trace_component(self, *_, **__):  # noqa: D401
                                                return _NullAsyncContext()

                                        comp._tracing_service = _NullTracingService()  # type: ignore[attr-defined]
                                    # Provide the query to the first TextInput-like component
                                    if hasattr(comp, "input_value") and getattr(comp, "input_value", None) in (None, ""):
                                        setattr(comp, "input_value", query)
                            gen = flow.start()
                            last: Any | None = None
                            for last in gen:
                                pass
                            outputs = last or {}
                        else:
                            raise first_exc
                    except Exception:
                        raise first_exc
            except Exception:
                # Could not resolve via node-id strategy – raise original error
                raise first_exc

    # At this point `outputs` might be an arbitrary object depending on how the
    # LangFlow generator ended (e.g., `VertexBuildResult`).  Down-stream we
    # treat it like a mapping, so coerce non-mappings into a dict wrapper.
    def _ensure_dict(obj: Any) -> dict:
        if isinstance(obj, dict):
            return obj
        # Fall back to using __dict__ when available, else string repr.
        if hasattr(obj, "__dict__") and obj.__dict__:
            return obj.__dict__  # type: ignore[return-value]
        return {"value": obj}

    outputs = _ensure_dict(outputs)

    debug_info = {
        "output_keys": list(outputs.keys()),
        "outputs": {k: str(v)[:500] for k, v in outputs.items()},
    }
    if debug_file:
        with open(debug_file, "w") as f:
            json.dump(
                {"outputs": outputs, "debug_info": debug_info}, f, indent=2, default=str
            )

    preferred = ["text", "text_output", "output", "result"]
    result: str | None = None
    for key in preferred:
        if key in outputs:
            val = outputs[key]
            if isinstance(val, dict) and "data" in val:
                result = val["data"]
                break
            if isinstance(val, str):
                result = val
                break
    if result is None:
        for val in outputs.values():
            if isinstance(val, dict) and "data" in val:
                result = val["data"]
                break
            if isinstance(val, str):
                result = val
                break
    if result is None:
        # Final fallback: fetch the `input_value` of any TextOutput component in the graph
        if hasattr(flow, "vertex_map"):
            for vertex in flow.vertex_map.values():
                comp = getattr(vertex, "custom_component", None)
                if comp and vertex.display_name == "Text Output" and hasattr(comp, "input_value"):
                    text_val = getattr(comp, "input_value", "")
                    if isinstance(text_val, str) and text_val.strip():
                        result = text_val.strip()
                        break
    if result is None:
        result = str(outputs)

    return result, debug_info, outputs
