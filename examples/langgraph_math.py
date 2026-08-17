"""
Minimal LangGraph math agent for verifying the harness + chaos.

This version is fully deterministic (no LLM required) so you can
exercise both clean and chaos paths immediately.

Usage (from agent-crash-test/):
    PYTHONPATH=. python -m examples.langgraph_math
"""

from __future__ import annotations

import operator
import re
from pathlib import Path
from typing import Annotated, TypedDict

from langchain_core.messages import AIMessage, HumanMessage, ToolMessage
from langchain_core.tools import tool
from langgraph.graph import END, StateGraph
from langgraph.prebuilt import ToolNode

from adapters.langgraph import LangGraphAdapter
from chaos.base import ChaosConfig
from harness.runner import CrashTestRunner
from harness.trajectory import Trajectory


# ---------------------------------------------------------------------------
# Tools (will be wrapped by the adapter)
# ---------------------------------------------------------------------------

@tool
def multiply(a: float, b: float) -> float:
    """Multiply two numbers and return the product."""
    return a * b


@tool
def add(a: float, b: float) -> float:
    """Add two numbers and return the sum."""
    return a + b


RAW_TOOLS = [multiply, add]


# ---------------------------------------------------------------------------
# Graph factory – accepts already-wrapped tools so chaos is active
# ---------------------------------------------------------------------------

class AgentState(TypedDict):
    messages: Annotated[list, operator.add]


def make_agent_node():
    def agent_node(state: AgentState):
        last = state["messages"][-1]
        content = last.content if hasattr(last, "content") else str(last)

        # If we already have a ToolMessage, produce a final answer
        if isinstance(last, ToolMessage) or (
            hasattr(last, "type") and last.type == "tool"
        ):
            result = content
            return {"messages": [AIMessage(content=f"The result is {result}")]}

        # Otherwise try to parse a multiplication and emit a tool call
        m = re.search(r"(\d+(?:\.\d+)?)\s*[\*x×]\s*(\d+(?:\.\d+)?)", content, re.I)
        if not m:
            m = re.search(r"(\d+(?:\.\d+)?)\s+times\s+(\d+(?:\.\d+)?)", content, re.I)

        if m:
            a, b = float(m.group(1)), float(m.group(2))
            ai = AIMessage(
                content="",
                tool_calls=[{
                    "name": "multiply",
                    "args": {"a": a, "b": b},
                    "id": "call_demo_1",
                    "type": "tool_call",
                }],
            )
            return {"messages": [ai]}

        return {"messages": [AIMessage(content="I could not parse a multiplication.")]}

    return agent_node


def should_continue(state: AgentState):
    last = state["messages"][-1]
    if hasattr(last, "tool_calls") and last.tool_calls:
        return "tools"
    return END


def build_graph(tools):
    tool_node = ToolNode(tools)
    g = StateGraph(AgentState)
    g.add_node("agent", make_agent_node())
    g.add_node("tools", tool_node)
    g.set_entry_point("agent")
    g.add_conditional_edges("agent", should_continue, {"tools": "tools", END: END})
    g.add_edge("tools", "agent")
    return g.compile()


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def run_once(label: str, chaos_config: ChaosConfig) -> Trajectory:
    print("=" * 60)
    print(label)
    print("=" * 60)

    adapter = LangGraphAdapter(chaos_config)

    # Wrap tools so chaos is actually applied
    def on_chaos(ev):
        # The adapter / trajectory will also see these via other paths;
        # for the demo we just print.
        print(f"  [chaos event] {ev['chaos_type']}: {ev['description']}")

    wrapped_tools = adapter.wrap_tools(RAW_TOOLS, on_chaos=on_chaos)
    graph = build_graph(wrapped_tools)

    runner = CrashTestRunner(framework="langgraph", chaos=chaos_config)
    traj = runner.run(
        agent=graph,
        input_message="What is 23 * 47?",
        model_name="deterministic-demo",
        agent_name="math-agent",
        tags=["demo", label.lower().replace(" ", "_")],
    )
    print(traj.summary())
    print()
    return traj


def main():
    out_dir = Path("runs")
    out_dir.mkdir(exist_ok=True)

    # Clean
    clean_cfg = ChaosConfig(enabled=False)
    traj_clean = run_once("CLEAN RUN (no chaos)", clean_cfg)

    # Chaos – high chance of argument / error problems
    chaos_cfg = ChaosConfig(
        enabled=True,
        tool_timeout_prob=0.0,          # keep 0 so the demo finishes quickly
        malformed_arguments_prob=0.7,
        tool_error_prob=0.4,
        partial_result_prob=0.3,
        schema_error_prob=0.3,
        max_chaos_per_run=2,
        target_tools=["multiply", "add"],
    )
    traj_chaos = run_once("CHAOS RUN", chaos_cfg)

    # Persist
    runner = CrashTestRunner(framework="langgraph")
    runner.save(traj_clean, out_dir / "langgraph_math_clean.json")
    runner.save(traj_chaos, out_dir / "langgraph_math_chaos.json")
    print(f"Trajectories saved under {out_dir}/")


if __name__ == "__main__":
    main()
