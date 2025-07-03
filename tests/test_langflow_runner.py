import types
from pathlib import Path
import pytest

from src.langflow_runner import run_langflow_json


class DummyFlow:
    def __init__(self) -> None:
        self.called = False

    def build(self):
        def _run(inputs):
            self.called = True
            q = list(inputs.values())[0]
            return {"result": f"echo {q}"}

        return _run


def dummy_loader(path: str):
    return DummyFlow()


def test_run_langflow_json_success(monkeypatch, tmp_path: Path):
    monkeypatch.setattr("src.langflow_runner.load_flow_from_json", dummy_loader)
    result, debug, outputs = run_langflow_json("dummy.json", "hello")
    assert result == "echo hello"
    assert outputs["result"] == "echo hello"
    assert "result" in debug["output_keys"]


def test_run_langflow_json_fallback(monkeypatch):
    class OldFlow:
        def __call__(self, inputs):
            if "input_value" in inputs:
                raise KeyError("bad key")
            return {"text_output": inputs.get("text")}

    monkeypatch.setattr("src.langflow_runner.load_flow_from_json", lambda p: OldFlow())
    result, _, _ = run_langflow_json("old.json", "hi")
    assert result == "hi"
