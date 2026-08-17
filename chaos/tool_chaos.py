"""Concrete tool-level chaos injector."""

from __future__ import annotations

import copy
import random
import time
from typing import Any, Callable, Dict, Optional, Tuple

from chaos.base import BaseChaosInjector, ChaosConfig
from harness.trajectory import ChaosType


class ToolChaosInjector(BaseChaosInjector):
    """Applies controlled chaos to tool arguments and execution."""

    def maybe_perturb_arguments(
        self, tool_name: str, arguments: Dict[str, Any]
    ) -> Tuple[Dict[str, Any], Optional[dict]]:
        if not self.config.enabled or not self.can_apply_more():
            return arguments, None
        if not self.config.is_tool_eligible(tool_name):
            return arguments, None

        if random.random() < self.config.malformed_arguments_prob:
            perturbed = self._malform_arguments(arguments)
            self.record_applied()
            event = {
                "chaos_type": ChaosType.MALFORMED_ARGUMENTS,
                "applied_to": tool_name,
                "description": f"Malformed arguments for tool '{tool_name}'",
                "original_value": arguments,
                "perturbed_value": perturbed,
            }
            return perturbed, event

        return arguments, None

    def maybe_perturb_execution(
        self,
        tool_name: str,
        original_callable: Callable,
        arguments: Dict[str, Any],
    ) -> Tuple[Any, Optional[dict]]:
        if not self.config.enabled or not self.can_apply_more():
            result = original_callable(**arguments) if arguments else original_callable()
            return result, None

        if not self.config.is_tool_eligible(tool_name):
            result = original_callable(**arguments) if arguments else original_callable()
            return result, None

        # Decide which chaos (if any) to apply — ordered by severity interest
        r = random.random()

        # 1. Hard timeout / hang
        if r < self.config.tool_timeout_prob:
            self.record_applied()
            time.sleep(self.config.timeout_seconds)
            event = {
                "chaos_type": ChaosType.TOOL_TIMEOUT,
                "applied_to": tool_name,
                "description": f"Injected {self.config.timeout_seconds}s timeout on '{tool_name}'",
                "original_value": None,
                "perturbed_value": None,
            }
            raise TimeoutError(f"[Chaos] Tool '{tool_name}' timed out after {self.config.timeout_seconds}s")

        # 2. Direct exception
        if r < self.config.tool_timeout_prob + self.config.tool_error_prob:
            self.record_applied()
            event = {
                "chaos_type": ChaosType.TOOL_ERROR,
                "applied_to": tool_name,
                "description": f"Injected exception on tool '{tool_name}'",
                "original_value": None,
                "perturbed_value": "ChaosInjectedError",
            }
            raise RuntimeError(f"[Chaos] Simulated failure in tool '{tool_name}'")

        # 3. Delayed but successful result
        if r < (
            self.config.tool_timeout_prob
            + self.config.tool_error_prob
            + self.config.delayed_result_prob
        ):
            self.record_applied()
            time.sleep(self.config.delay_seconds)
            result = original_callable(**arguments) if arguments else original_callable()
            event = {
                "chaos_type": ChaosType.DELAYED_RESULT,
                "applied_to": tool_name,
                "description": f"Delayed result by {self.config.delay_seconds}s for '{tool_name}'",
                "original_value": None,
                "perturbed_value": None,
            }
            return result, event

        # 4. Partial / truncated result
        if r < (
            self.config.tool_timeout_prob
            + self.config.tool_error_prob
            + self.config.delayed_result_prob
            + self.config.partial_result_prob
        ):
            self.record_applied()
            result = original_callable(**arguments) if arguments else original_callable()
            partial = self._make_partial(result)
            event = {
                "chaos_type": ChaosType.PARTIAL_RESULT,
                "applied_to": tool_name,
                "description": f"Returned partial/truncated result from '{tool_name}'",
                "original_value": result,
                "perturbed_value": partial,
            }
            return partial, event

        # 5. Schema / type mismatch on success path
        if r < (
            self.config.tool_timeout_prob
            + self.config.tool_error_prob
            + self.config.delayed_result_prob
            + self.config.partial_result_prob
            + self.config.schema_error_prob
        ):
            self.record_applied()
            result = original_callable(**arguments) if arguments else original_callable()
            bad = self._schema_break(result)
            event = {
                "chaos_type": ChaosType.SCHEMA_ERROR,
                "applied_to": tool_name,
                "description": f"Returned schema-incompatible result from '{tool_name}'",
                "original_value": result,
                "perturbed_value": bad,
            }
            return bad, event

        # No chaos this time
        result = original_callable(**arguments) if arguments else original_callable()
        return result, None

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def _malform_arguments(self, arguments: Dict[str, Any]) -> Dict[str, Any]:
        if not arguments:
            return {"_chaos_injected": True}

        perturbed = copy.deepcopy(arguments)
        keys = list(perturbed.keys())
        if not keys:
            return perturbed

        action = random.choice(["drop", "type_flip", "nullify", "extra_noise"])
        key = random.choice(keys)

        if action == "drop":
            perturbed.pop(key, None)
        elif action == "type_flip":
            val = perturbed[key]
            if isinstance(val, (int, float)):
                perturbed[key] = str(val)
            elif isinstance(val, str):
                perturbed[key] = 42
            elif isinstance(val, bool):
                perturbed[key] = "true" if val else "false"
            else:
                perturbed[key] = None
        elif action == "nullify":
            perturbed[key] = None
        else:  # extra_noise
            perturbed["_chaos_extra"] = "injected_noise_value"

        return perturbed

    def _make_partial(self, result: Any) -> Any:
        if isinstance(result, str) and len(result) > 20:
            return result[: len(result) // 3] + " ...[truncated by chaos]"
        if isinstance(result, dict):
            keys = list(result.keys())
            if keys:
                keep = keys[: max(1, len(keys) // 2)]
                return {k: result[k] for k in keep}
        if isinstance(result, list) and len(result) > 1:
            return result[: max(1, len(result) // 2)]
        return result

    def _schema_break(self, result: Any) -> Any:
        """Return something that is likely to break downstream schema expectations."""
        if isinstance(result, dict):
            return [result]  # list instead of object
        if isinstance(result, list):
            return {"items": result, "_chaos": True}
        if isinstance(result, str):
            return {"text": result, "unexpected_field": 123}
        return {"unexpected_type": str(type(result)), "value": result}


class ChaosToolWrapper:
    """
    Drop-in wrapper around any callable tool.

    Usage:
        wrapper = ChaosToolWrapper(original_tool_func, injector, tool_name="search")
        result = wrapper(query="...")
    """

    def __init__(
        self,
        original: Callable,
        injector: ToolChaosInjector,
        tool_name: str,
        on_chaos: Optional[Callable[[dict], None]] = None,
    ):
        self.original = original
        self.injector = injector
        self.tool_name = tool_name
        self.on_chaos = on_chaos  # callback to record ChaosEvent into trajectory

    def __call__(self, *args, **kwargs) -> Any:
        # Normalize to kwargs for simplicity
        if args and not kwargs:
            # Best-effort: many tools are single-arg
            if len(args) == 1:
                kwargs = {"input": args[0]}
            else:
                kwargs = {f"arg{i}": a for i, a in enumerate(args)}

        # 1. Possibly malform arguments
        arguments, arg_event = self.injector.maybe_perturb_arguments(
            self.tool_name, kwargs
        )
        if arg_event and self.on_chaos:
            self.on_chaos(arg_event)

        # 2. Execute with possible execution chaos
        try:
            result, exec_event = self.injector.maybe_perturb_execution(
                self.tool_name, self.original, arguments
            )
            if exec_event and self.on_chaos:
                self.on_chaos(exec_event)
            return result
        except Exception as e:
            # Re-raise so the agent / framework can handle it
            # (timeouts and tool_errors are raised inside maybe_perturb_execution)
            raise
