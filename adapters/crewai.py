"""CrewAI adapter with tool-level chaos injection and trajectory capture."""

from __future__ import annotations

import time
from typing import Any, Callable, Dict, List, Optional

from adapters.base import AgentAdapter
from chaos.base import ChaosConfig
from chaos.tool_chaos import ChaosToolWrapper, ToolChaosInjector
from harness.trajectory import (
    ChaosEvent,
    StepType,
    ToolCallRecord,
    ToolResultRecord,
    Trajectory,
    TrajectoryStep,
)


class CrewAIAdapter(AgentAdapter):
    """
    Adapter for CrewAI Crew / Agent objects.

    Strategy
    --------
    - Walk all agents in the crew and wrap their tools with ChaosToolWrapper.
    - Execute crew.kickoff() (or agent.execute_task).
    - Use a combination of callbacks and post-hoc inspection of task outputs
      to build the trajectory. CrewAI's event system has improved; we keep
      the adapter defensive so it works across recent versions.
    """

    framework_name = "crewai"

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
        **kwargs,
    ) -> Trajectory:
        """
        Parameters
        ----------
        agent :
            A CrewAI Crew instance (preferred) or a single Agent.
        input_message :
            The task description / user request. For a Crew this becomes
            the input to kickoff; for a single Agent it becomes the task.
        """
        traj = self._new_trajectory(model_name, agent_name, tags)
        step_idx = 0
        chaos_events: List[dict] = []

        def record_chaos(event_dict: dict) -> None:
            chaos_events.append(event_dict)

        # Inject chaos into tools
        self._wrap_crew_tools(agent, record_chaos)

        start = time.time()
        final_answer = None
        error_msg = None
        success = False

        try:
            # Crew path
            if hasattr(agent, "kickoff"):
                # Newer CrewAI accepts inputs= dict
                result = agent.kickoff(inputs={"input": input_message})
                final_answer = str(result) if result is not None else None
            elif hasattr(agent, "execute_task"):
                # Single agent path – create a minimal task if needed
                result = agent.execute_task(input_message)
                final_answer = str(result) if result is not None else None
            else:
                raise TypeError(
                    "Expected a CrewAI Crew (with .kickoff) or Agent "
                    "(with .execute_task). Got: " + type(agent).__name__
                )

            # Record a high-level final step
            step = TrajectoryStep(
                step_index=step_idx,
                step_type=StepType.FINAL_ANSWER,
                content=final_answer[:2000] if final_answer else None,
            )
            traj.add_step(step)
            step_idx += 1

            # Attach any chaos events that were recorded during tool calls
            for ev in chaos_events:
                chaos = ChaosEvent(**ev)
                step = TrajectoryStep(
                    step_index=step_idx,
                    step_type=StepType.TOOL_RESULT,
                    chaos=chaos,
                    content=f"[Chaos] {chaos.description}",
                )
                traj.add_step(step)
                step_idx += 1

            success = True

        except Exception as e:
            error_msg = str(e)
            step = TrajectoryStep(
                step_index=step_idx,
                step_type=StepType.ERROR,
                content=error_msg,
            )
            traj.add_step(step)
            # Still surface chaos events that happened before the crash
            for ev in chaos_events:
                chaos = ChaosEvent(**ev)
                step = TrajectoryStep(
                    step_index=step_idx + 1,
                    step_type=StepType.TOOL_RESULT,
                    chaos=chaos,
                    content=f"[Chaos] {chaos.description}",
                )
                traj.add_step(step)
            success = False

        traj.finalize(success=success, final_answer=final_answer, error=error_msg)
        return traj

    def _wrap_crew_tools(
        self, crew_or_agent: Any, on_chaos: Callable[[dict], None]
    ) -> None:
        """Mutate tools in-place so chaos is active for the upcoming run."""
        agents = []
        if hasattr(crew_or_agent, "agents"):
            agents = list(crew_or_agent.agents or [])
        elif hasattr(crew_or_agent, "tools"):
            # single agent
            agents = [crew_or_agent]

        for ag in agents:
            tools = getattr(ag, "tools", None) or []
            new_tools = []
            for tool in tools:
                name = getattr(tool, "name", getattr(tool, "__name__", "unknown_tool"))
                original = getattr(tool, "func", None) or getattr(tool, "_run", None) or tool

                wrapper = ChaosToolWrapper(
                    original=original,
                    injector=self.injector,
                    tool_name=name,
                    on_chaos=on_chaos,
                )

                # Try to preserve StructuredTool / CrewAI tool interface
                try:
                    # CrewAI tools often have .name, .description, .func
                    if hasattr(tool, "name") and hasattr(tool, "description"):
                        tool.func = wrapper  # mutate in place when possible
                        new_tools.append(tool)
                        continue
                except Exception:
                    pass

                wrapper.name = name  # type: ignore
                new_tools.append(wrapper)

            try:
                ag.tools = new_tools
            except Exception:
                # Some agent objects make tools read-only; best-effort only
                pass
