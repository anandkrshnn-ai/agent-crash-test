"""Unit tests for the chaos injector (no LLM required)."""

from __future__ import annotations

import pytest

from chaos.base import ChaosConfig
from chaos.tool_chaos import ToolChaosInjector, ChaosToolWrapper


def test_malformed_arguments_triggers():
    cfg = ChaosConfig(
        enabled=True,
        malformed_arguments_prob=1.0,  # always
        max_chaos_per_run=5,
    )
    injector = ToolChaosInjector(cfg)

    original = {"a": 10, "b": 20}
    perturbed, event = injector.maybe_perturb_arguments("multiply", original)

    assert event is not None
    assert event["chaos_type"].value == "malformed_arguments"
    assert perturbed != original


def test_no_chaos_when_disabled():
    cfg = ChaosConfig(enabled=False, malformed_arguments_prob=1.0)
    injector = ToolChaosInjector(cfg)

    original = {"a": 1}
    perturbed, event = injector.maybe_perturb_arguments("multiply", original)
    assert event is None
    assert perturbed == original


def test_tool_error_raises():
    cfg = ChaosConfig(
        enabled=True,
        tool_error_prob=1.0,
        tool_timeout_prob=0.0,
        max_chaos_per_run=5,
    )
    injector = ToolChaosInjector(cfg)

    def real_tool(x: int) -> int:
        return x * 2

    with pytest.raises(RuntimeError, match="Simulated failure"):
        injector.maybe_perturb_execution("real_tool", real_tool, {"x": 5})


def test_wrapper_records_chaos():
    cfg = ChaosConfig(
        enabled=True,
        malformed_arguments_prob=1.0,
        max_chaos_per_run=5,
    )
    injector = ToolChaosInjector(cfg)
    events = []

    def on_chaos(ev):
        events.append(ev)

    def real(a: float, b: float) -> float:
        return a * b

    wrapper = ChaosToolWrapper(real, injector, "multiply", on_chaos=on_chaos)
    # Even if the tool later fails because of bad args, the chaos event should be recorded
    try:
        wrapper(a=3, b=4)
    except Exception:
        pass

    assert len(events) >= 1
    assert events[0]["chaos_type"].value == "malformed_arguments"


def test_max_chaos_cap():
    cfg = ChaosConfig(
        enabled=True,
        malformed_arguments_prob=1.0,
        max_chaos_per_run=1,
    )
    injector = ToolChaosInjector(cfg)

    _, e1 = injector.maybe_perturb_arguments("t1", {"x": 1})
    _, e2 = injector.maybe_perturb_arguments("t2", {"x": 2})

    assert e1 is not None
    assert e2 is None  # capped
