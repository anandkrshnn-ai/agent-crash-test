"""Base adapter interface for agent frameworks."""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any, Dict, Optional

from chaos.base import ChaosConfig
from harness.trajectory import Trajectory


class AgentAdapter(ABC):
    """
    Common interface that every framework adapter must implement.

    The harness uses this to:
    1. Inject chaos wrappers around tools
    2. Execute the agent
    3. Collect a full Trajectory
    """

    framework_name: str = "base"

    def __init__(self, chaos_config: Optional[ChaosConfig] = None):
        self.chaos_config = chaos_config or ChaosConfig(enabled=False)

    @abstractmethod
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
        Execute the agent under the configured chaos and return a Trajectory.

        Parameters
        ----------
        agent :
            Framework-specific agent / graph / crew object.
        input_message :
            The user / task input to start the run.
        model_name :
            Name of the underlying LLM (for metadata).
        agent_name :
            Optional human-readable name.
        tags :
            Optional tags for filtering later.
        """
        ...

    def _new_trajectory(
        self,
        model_name: str,
        agent_name: Optional[str] = None,
        tags: Optional[list[str]] = None,
    ) -> Trajectory:
        from harness.trajectory import SessionMetadata, Trajectory

        meta = SessionMetadata(
            framework=self.framework_name,
            model=model_name,
            agent_name=agent_name,
            chaos_config=self.chaos_config.to_dict(),
            tags=tags or [],
        )
        return Trajectory(metadata=meta)
