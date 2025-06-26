from __future__ import annotations

from types import SimpleNamespace

import pytest

from src.spreadsheet_builder.llm_plan_builder import PlanGenerator, _sample_plan


class DummyLLM:
    """First returns invalid JSON, then valid JSON."""

    def __init__(self):
        self.calls = 0

    def invoke(self, _msgs):  # noqa: D401
        self.calls += 1
        if self.calls == 1:
            return SimpleNamespace(content="{ not valid json")
        # second call returns valid sample
        import json
        return SimpleNamespace(content=json.dumps(_sample_plan()))


def test_generate_with_retry(monkeypatch):
    pg = PlanGenerator(model_name="o3")
    monkeypatch.setattr(pg, "llm", DummyLLM())

    plan = pg.generate("Objective", "some data")
    assert plan["worksheet"]["name"] == "Model" 