"""Trajectory data models for Agent Crash Test.

Captures full multi-step agent runs including tool calls,
chaos interventions, and intermediate state.
"""

from __future__ import annotations

from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, List, Optional
from uuid import uuid4

from pydantic import BaseModel, Field


class ChaosType(str, Enum):
    NONE = "none"
    TOOL_TIMEOUT = "tool_timeout"
    MALFORMED_ARGUMENTS = "malformed_arguments"
    SCHEMA_ERROR = "schema_error"
    TOOL_ERROR = "tool_error"
    PARTIAL_RESULT = "partial_result"
    DELAYED_RESULT = "delayed_result"


class StepType(str, Enum):
    AGENT_THOUGHT = "agent_thought"
    TOOL_CALL = "tool_call"
    TOOL_RESULT = "tool_result"
    HUMAN_MESSAGE = "human_message"
    FINAL_ANSWER = "final_answer"
    ERROR = "error"
    STATE_UPDATE = "state_update"


class ToolCallRecord(BaseModel):
    tool_name: str
    arguments: Dict[str, Any] = Field(default_factory=dict)
    call_id: Optional[str] = None


class ToolResultRecord(BaseModel):
    tool_name: str
    call_id: Optional[str] = None
    status: str = "success"  # success | error | timeout | partial
    content: Any = None
    execution_ms: Optional[float] = None
    error_message: Optional[str] = None


class ChaosEvent(BaseModel):
    chaos_type: ChaosType
    applied_to: str  # tool name or "arguments" / "result"
    description: str
    original_value: Optional[Any] = None
    perturbed_value: Optional[Any] = None


class TrajectoryStep(BaseModel):
    step_id: str = Field(default_factory=lambda: str(uuid4())[:8])
    step_index: int
    step_type: StepType
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

    # Content
    content: Optional[str] = None
    tool_call: Optional[ToolCallRecord] = None
    tool_result: Optional[ToolResultRecord] = None
    chaos: Optional[ChaosEvent] = None

    # Framework-specific state snapshot (optional, can be large)
    state_snapshot: Optional[Dict[str, Any]] = None
    metadata: Dict[str, Any] = Field(default_factory=dict)


class SessionMetadata(BaseModel):
    session_id: str = Field(default_factory=lambda: str(uuid4()))
    framework: str  # "langgraph" | "crewai" | ...
    model: str
    agent_name: Optional[str] = None
    chaos_config: Dict[str, Any] = Field(default_factory=dict)
    started_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    ended_at: Optional[datetime] = None
    success: Optional[bool] = None
    final_answer: Optional[str] = None
    error: Optional[str] = None
    total_steps: int = 0
    total_tool_calls: int = 0
    tags: List[str] = Field(default_factory=list)


class Trajectory(BaseModel):
    """Complete record of one agent run under (optional) chaos."""

    metadata: SessionMetadata
    steps: List[TrajectoryStep] = Field(default_factory=list)

    def add_step(self, step: TrajectoryStep) -> None:
        self.steps.append(step)
        self.metadata.total_steps = len(self.steps)
        if step.step_type == StepType.TOOL_CALL:
            self.metadata.total_tool_calls += 1

    def finalize(
        self,
        success: bool,
        final_answer: Optional[str] = None,
        error: Optional[str] = None,
    ) -> None:
        self.metadata.ended_at = datetime.now(timezone.utc)
        self.metadata.success = success
        self.metadata.final_answer = final_answer
        self.metadata.error = error

    def to_dict(self) -> Dict[str, Any]:
        return self.model_dump(mode="json")

    def summary(self) -> str:
        lines = [
            f"Session: {self.metadata.session_id}",
            f"Framework: {self.metadata.framework} | Model: {self.metadata.model}",
            f"Steps: {self.metadata.total_steps} | Tool calls: {self.metadata.total_tool_calls}",
            f"Success: {self.metadata.success}",
        ]
        chaos_events = [s for s in self.steps if s.chaos is not None]
        if chaos_events:
            lines.append(f"Chaos events: {len(chaos_events)}")
            for s in chaos_events:
                lines.append(f"  - [{s.chaos.chaos_type}] {s.chaos.description}")
        return "\n".join(lines)
