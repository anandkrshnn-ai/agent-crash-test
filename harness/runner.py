"""High-level runner that ties adapters + chaos + trajectory together."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, Optional, Union

from adapters.base import AgentAdapter
from adapters.crewai import CrewAIAdapter
from adapters.langgraph import LangGraphAdapter
from chaos.base import ChaosConfig
from harness.trajectory import Trajectory


class CrashTestRunner:
    """
    Convenience facade.

    Example
    -------
    runner = CrashTestRunner(framework="langgraph", chaos=ChaosConfig(...))
    traj = runner.run(agent=my_graph, input_message="What is 23*47?", model_name="llama3.1")
    print(traj.summary())
    runner.save(traj, "runs/run_001.json")
    """

    def __init__(
        self,
        framework: str = "langgraph",
        chaos: Optional[ChaosConfig] = None,
    ):
        self.framework = framework.lower()
        self.chaos = chaos or ChaosConfig(enabled=False)

        if self.framework == "langgraph":
            self.adapter: AgentAdapter = LangGraphAdapter(self.chaos)
        elif self.framework == "crewai":
            self.adapter = CrewAIAdapter(self.chaos)
        else:
            raise ValueError(f"Unsupported framework: {framework}. Use 'langgraph' or 'crewai'.")

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
        return self.adapter.run(
            agent=agent,
            input_message=input_message,
            model_name=model_name,
            agent_name=agent_name,
            tags=tags,
            **kwargs,
        )

    def save(self, trajectory: Trajectory, path: Union[str, Path]) -> Path:
        path = Path(path)
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("w", encoding="utf-8") as f:
            json.dump(trajectory.to_dict(), f, indent=2, default=str)
        return path

    @staticmethod
    def load(path: Union[str, Path]) -> Trajectory:
        with Path(path).open("r", encoding="utf-8") as f:
            data = json.load(f)
        return Trajectory.model_validate(data)
