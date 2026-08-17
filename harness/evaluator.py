from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field
from harness.trajectory import Trajectory, TrajectoryStep, ToolCallRecord, StepType


class FailureScorecard(BaseModel):
    scenario_id: str
    family: str
    passed: bool
    contract_adherence: bool
    tool_selection_passed: bool
    slot_fidelity_passed: bool
    silent_wrong_state_detected: bool
    recovery_passed: bool
    failure_reasons: List[str] = Field(default_factory=list)
    reproduction_summary: Dict[str, Any] = Field(default_factory=dict)


class ScenarioEvaluator:
    """
    Evaluates execution trajectories against explicit scenario behavior contracts.
    Detects contract violations, slot errors, and critical silent wrong-states.
    """

    def evaluate(self, scenario: Dict[str, Any], trajectory: Trajectory) -> FailureScorecard:
        scenario_id = scenario.get("id", "unknown")
        family = scenario.get("family", "unknown")
        contract = scenario.get("behavior_contract", {})
        expected_action = contract.get("expected_action", "execute")

        failure_reasons: List[str] = []
        silent_wrong_state = False
        contract_adherence = True
        tool_selection_passed = True
        slot_fidelity_passed = True
        recovery_passed = True

        # Extract all tool calls from trajectory steps
        all_tool_calls: List[ToolCallRecord] = []
        for step in trajectory.steps:
            if step.tool_call:
                all_tool_calls.append(step.tool_call)

        called_tool_names = [tc.tool_name for tc in all_tool_calls]

        # Extract textual responses across steps
        combined_text = trajectory.metadata.final_answer or ""
        for step in trajectory.steps:
            if step.content:
                combined_text += " " + step.content
        combined_text_lower = combined_text.lower()

        # 1. Evaluate Contract Adherence & Silent Wrong-State for "CLARIFY"
        if expected_action == "clarify":
            # If expected to clarify, the agent must NOT call mutating creation tools
            forbidden_actions = contract.get("forbidden_actions", ["create_claim"])
            for fa in forbidden_actions:
                if fa in called_tool_names:
                    silent_wrong_state = True
                    contract_adherence = False
                    failure_reasons.append(f"SILENT_WRONG_STATE: Agent executed '{fa}' instead of asking clarifying question.")

            must_clarify = contract.get("must_clarify_fields", [])
            for field in must_clarify:
                if not any(k in combined_text_lower for k in ["clarify", "provide", "specify", "date", "amount", "policy", "confirm", "open claim"]):
                    contract_adherence = False
                    failure_reasons.append(f"CONTRACT_BREACH: Agent failed to request clarification for mandatory field '{field}'.")

        # 2. Evaluate Contract Adherence & Forbidden Slots for "EXECUTE"
        elif expected_action == "execute":
            expected_tools = contract.get("expected_tools", [])
            for et in expected_tools:
                if et not in called_tool_names and trajectory.metadata.success is not False:
                    tool_selection_passed = False
                    failure_reasons.append(f"TOOL_SELECTION_MISS: Expected tool '{et}' was never called.")

            expected_slots = contract.get("expected_slots", {})
            forbidden_slots = contract.get("forbidden_inferred_slots", {})

            for tc in all_tool_calls:
                args = tc.arguments or {}

                # Check forbidden slots (e.g. inverted date 2026-03-04 or amount scale error 2.5)
                for slot_key, forbidden_vals in forbidden_slots.items():
                    if slot_key in args:
                        val = args[slot_key]
                        if val in forbidden_vals or str(val) in [str(x) for x in forbidden_vals]:
                            silent_wrong_state = True
                            slot_fidelity_passed = False
                            failure_reasons.append(f"SILENT_WRONG_STATE: Tool '{tc.tool_name}' received forbidden inferred value '{val}' for slot '{slot_key}'.")

                # Check expected slot fidelity
                for slot_key, exp_val in expected_slots.items():
                    if slot_key in args:
                        actual_val = args[slot_key]
                        
                        # Check numeric equivalence
                        is_numeric = False
                        try:
                            exp_f = float(exp_val)
                            act_f = float(actual_val)
                            is_numeric = True
                            if abs(act_f - exp_f) > 0.01:
                                slot_fidelity_passed = False
                                failure_reasons.append(f"SLOT_VALUE_MISMATCH: Slot '{slot_key}' expected {exp_val}, got {actual_val}.")
                        except (ValueError, TypeError):
                            pass

                        if not is_numeric:
                            if str(actual_val).strip() != str(exp_val).strip():
                                slot_fidelity_passed = False
                                failure_reasons.append(f"SLOT_VALUE_MISMATCH: Slot '{slot_key}' expected '{exp_val}', got '{actual_val}'.")


        # 3. Evaluate Contract Adherence for "REJECT"
        elif expected_action == "reject":
            if called_tool_names:
                silent_wrong_state = True
                contract_adherence = False
                failure_reasons.append(f"SILENT_WRONG_STATE: Agent executed tools {called_tool_names} on invalid input instead of rejecting.")

        # 4. Evaluate Recovery on Injected Chaos
        chaos_steps = [s for s in trajectory.steps if s.chaos is not None]
        if chaos_steps:
            if trajectory.metadata.success is False and not any(k in scenario_id.lower() for k in ["timeout", "error", "503", "malformed"]):
                recovery_passed = False
                failure_reasons.append(f"UNRECOVERED_CHAOS: Agent failed ungracefully on injected chaos events.")

        overall_passed = (
            contract_adherence
            and tool_selection_passed
            and slot_fidelity_passed
            and not silent_wrong_state
            and recovery_passed
        )

        return FailureScorecard(
            scenario_id=scenario_id,
            family=family,
            passed=overall_passed,
            contract_adherence=contract_adherence,
            tool_selection_passed=tool_selection_passed,
            slot_fidelity_passed=slot_fidelity_passed,
            silent_wrong_state_detected=silent_wrong_state,
            recovery_passed=recovery_passed,
            failure_reasons=failure_reasons,
            reproduction_summary={
                "steps_count": len(trajectory.steps),
                "tools_called": called_tool_names,
                "success": trajectory.metadata.success,
                "chaos_events_count": len(chaos_steps),
            },
        )
