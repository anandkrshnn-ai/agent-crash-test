"""LangGraph adapter with tool-level chaos injection and trajectory capture."""

from __future__ import annotations

import time
from typing import Any, Callable, Dict, List, Optional

from adapters.base import AgentAdapter
from chaos.base import ChaosConfig
from chaos.tool_chaos import ChaosToolWrapper, ToolChaosInjector
from harness.trajectory import (
    ChaosEvent,
    ChaosType,
    StepType,
    ToolCallRecord,
    ToolResultRecord,
    Trajectory,
    TrajectoryStep,
)


class LangGraphAdapter(AgentAdapter):
    """
    Adapter for LangGraph CompiledStateGraph (and similar runnable graphs).

    Strategy
    --------
    - Before execution we wrap every tool that appears in the graph's tool set.
    - We run the graph with stream_mode that yields updates so we can record
      every node transition and tool call.
    - Chaos events are recorded via a callback into the trajectory.
    """

    framework_name = "langgraph"

    def __init__(self, chaos_config: Optional[ChaosConfig] = None):
        super().__init__(chaos_config)
        self.injector = ToolChaosInjector(self.chaos_config)

    def run(
        self,
        agent: Any,
        input_message: str,
        *,
        model_name: str = "unknown",
        agent_name: Optional[str] = None,
        tags: Optional[list[str]] = None,
        config: Optional[Dict[str, Any]] = None,
        **kwargs,
    ) -> Trajectory:
        """
        Parameters
        ----------
        agent :
            A compiled LangGraph (CompiledStateGraph) or any object that
            supports .stream() / .invoke().
        input_message :
            User message. Will be placed into the standard {"messages": [...]}
            format if the graph expects it.
        config :
            Optional RunnableConfig passed to the graph.
        """
        traj = self._new_trajectory(model_name, agent_name, tags)
        step_idx = 0

        def record_chaos(event_dict: dict) -> None:
            nonlocal step_idx
            chaos = ChaosEvent(**event_dict)
            step = TrajectoryStep(
                step_index=step_idx,
                step_type=StepType.TOOL_RESULT,  # chaos usually surfaces around tool
                chaos=chaos,
                content=f"[Chaos] {chaos.description}",
            )
            traj.add_step(step)
            step_idx += 1

        # Attempt to discover and wrap tools if the graph exposes them.
        # Many LangGraph agents keep tools in a registry or pass them at build time.
        # For the minimal harness we rely on the example agents to hand us
        # already-wrapped tools, or we wrap at the call site in examples.

        # Build input
        if isinstance(input_message, str):
            graph_input = {"messages": [("user", input_message)]}
        else:
            graph_input = input_message

        start = time.time()
        final_answer = None
        error_msg = None
        success = False

        try:
            # Prefer streaming so we can capture intermediate state
            if hasattr(agent, "stream"):
                for chunk in agent.stream(graph_input, config=config or {}, stream_mode="updates"):
                    step_idx = self._record_stream_chunk(traj, chunk, step_idx)
                # Also try to get final state
                if hasattr(agent, "get_state") and config:
                    try:
                        state = agent.get_state(config)
                        if state and hasattr(state, "values"):
                            messages = state.values.get("messages", [])
                            if messages:
                                last = messages[-1]
                                final_answer = getattr(last, "content", str(last))
                    except Exception:
                        pass
            else:
                # Fallback to invoke
                result = agent.invoke(graph_input, config=config or {})
                step_idx = self._record_invoke_result(traj, result, step_idx)
                if isinstance(result, dict) and "messages" in result:
                    messages = result["messages"]
                    if messages:
                        last = messages[-1]
                        final_answer = getattr(last, "content", str(last))

            success = True
        except Exception as e:
            error_msg = str(e)
            step = TrajectoryStep(
                step_index=step_idx,
                step_type=StepType.ERROR,
                content=error_msg,
            )
            traj.add_step(step)
            success = False

        traj.finalize(success=success, final_answer=final_answer, error=error_msg)
        return traj

    def wrap_tools(
        self,
        tools: List[Any],
        on_chaos: Optional[Callable[[dict], None]] = None,
    ) -> List[Any]:
        """
        Convenience helper: wrap a list of LangChain / LangGraph tools
        with chaos. Returns new tool objects that can be bound to the model
        or passed into the graph.
        """
        wrapped = []
        for tool in tools:
            name = getattr(tool, "name", getattr(tool, "__name__", "unknown_tool"))
            # LangChain tools usually have .func or are callable
            original_func = getattr(tool, "func", None) or getattr(tool, "_run", None) or tool

            chaos_wrapper = ChaosToolWrapper(
                original=original_func,
                injector=self.injector,
                tool_name=name,
                on_chaos=on_chaos,
            )

            # Try to keep the original tool interface
            try:
                from langchain_core.tools import StructuredTool

                if isinstance(tool, StructuredTool):
                    new_tool = StructuredTool(
                        name=tool.name,
                        description=tool.description,
                        func=chaos_wrapper,
                        args_schema=tool.args_schema,
                    )
                    wrapped.append(new_tool)
                    continue
            except Exception:
                pass

            # Fallback: just return the callable wrapper
            chaos_wrapper.name = name  # type: ignore
            wrapped.append(chaos_wrapper)

        return wrapped

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _record_stream_chunk(
        self, traj: Trajectory, chunk: Any, step_idx: int
    ) -> int:
        """Best-effort conversion of a stream update into TrajectorySteps."""
        if not isinstance(chunk, dict):
            step = TrajectoryStep(
                step_index=step_idx,
                step_type=StepType.STATE_UPDATE,
                content=str(chunk)[:500],
            )
            traj.add_step(step)
            return step_idx + 1

        for node_name, update in chunk.items():
            # Messages node is the most common
            if isinstance(update, dict) and "messages" in update:
                messages = update["messages"]
                for msg in messages if isinstance(messages, list) else [messages]:
                    content = getattr(msg, "content", str(msg))
                    tool_calls = getattr(msg, "tool_calls", None)

                    if tool_calls:
                        for tc in tool_calls:
                            name = tc.get("name") if isinstance(tc, dict) else getattr(tc, "name", "tool")
                            args = tc.get("args") if isinstance(tc, dict) else getattr(tc, "args", {})
                            step = TrajectoryStep(
                                step_index=step_idx,
                                step_type=StepType.TOOL_CALL,
                                content=f"Tool call: {name}",
                                tool_call=ToolCallRecord(
                                    tool_name=name or "unknown",
                                    arguments=args or {},
                                    call_id=tc.get("id") if isinstance(tc, dict) else None,
                                ),
                                metadata={"node": node_name},
                            )
                            traj.add_step(step)
                            step_idx += 1
                    else:
                        step = TrajectoryStep(
                            step_index=step_idx,
                            step_type=StepType.AGENT_THOUGHT,
                            content=content[:1000] if content else None,
                            metadata={"node": node_name},
                        )
                        traj.add_step(step)
                        step_idx += 1
            else:
                step = TrajectoryStep(
                    step_index=step_idx,
                    step_type=StepType.STATE_UPDATE,
                    content=str(update)[:500],
                    metadata={"node": node_name},
                )
                traj.add_step(step)
                step_idx += 1

        return step_idx

    def _record_invoke_result(
        self, traj: Trajectory, result: Any, step_idx: int
    ) -> int:
        step = TrajectoryStep(
            step_index=step_idx,
            step_type=StepType.FINAL_ANSWER,
            content=str(result)[:2000],
        )
        traj.add_step(step)
        return step_idx + 1
