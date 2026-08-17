"""Base chaos configuration and injector interface."""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any, Dict, Optional

from harness.trajectory import ChaosType


@dataclass
class ChaosConfig:
    """Controls which chaos types are active and at what intensity."""

    enabled: bool = True

    # Probability (0.0 – 1.0) that a given chaos type triggers on a tool call
    tool_timeout_prob: float = 0.0
    malformed_arguments_prob: float = 0.0
    schema_error_prob: float = 0.0
    tool_error_prob: float = 0.0
    partial_result_prob: float = 0.0
    delayed_result_prob: float = 0.0

    # Concrete parameters
    timeout_seconds: float = 8.0
    delay_seconds: float = 3.0
    max_chaos_per_run: int = 3  # safety cap

    # Allowlist / denylist of tool names (empty = all tools)
    target_tools: list[str] = field(default_factory=list)
    exclude_tools: list[str] = field(default_factory=list)

    def is_tool_eligible(self, tool_name: str) -> bool:
        if self.exclude_tools and tool_name in self.exclude_tools:
            return False
        if self.target_tools and tool_name not in self.target_tools:
            return False
        return True

    def to_dict(self) -> Dict[str, Any]:
        return {
            "enabled": self.enabled,
            "tool_timeout_prob": self.tool_timeout_prob,
            "malformed_arguments_prob": self.malformed_arguments_prob,
            "schema_error_prob": self.schema_error_prob,
            "tool_error_prob": self.tool_error_prob,
            "partial_result_prob": self.partial_result_prob,
            "delayed_result_prob": self.delayed_result_prob,
            "timeout_seconds": self.timeout_seconds,
            "delay_seconds": self.delay_seconds,
            "max_chaos_per_run": self.max_chaos_per_run,
            "target_tools": self.target_tools,
            "exclude_tools": self.exclude_tools,
        }


class BaseChaosInjector(ABC):
    """Interface for any chaos injector."""

    def __init__(self, config: ChaosConfig):
        self.config = config
        self._chaos_count = 0

    def can_apply_more(self) -> bool:
        return self._chaos_count < self.config.max_chaos_per_run

    def record_applied(self) -> None:
        self._chaos_count += 1

    @abstractmethod
    def maybe_perturb_arguments(
        self, tool_name: str, arguments: Dict[str, Any]
    ) -> tuple[Dict[str, Any], Optional[dict]]:
        """Return (possibly modified args, chaos_event_dict or None)."""
        ...

    @abstractmethod
    def maybe_perturb_execution(
        self, tool_name: str, original_callable, arguments: Dict[str, Any]
    ) -> tuple[Any, Optional[dict]]:
        """Execute (or fake) the tool and return (result, chaos_event_dict or None)."""
        ...
