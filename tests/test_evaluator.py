import unittest
import shutil
import sys
from pathlib import Path

root_dir = Path(__file__).resolve().parent.parent
if str(root_dir) not in sys.path:
    sys.path.insert(0, str(root_dir))

from harness.trajectory import Trajectory, TrajectoryStep, ToolCallRecord, StepType, SessionMetadata
from harness.evaluator import ScenarioEvaluator
from harness.scenario_runner import ScenarioPackRunner
from adapters.langgraph import LangGraphAdapter
from examples.claims_agent import RuleBasedClaimsAgent


class TestScenarioEvaluator(unittest.TestCase):

    def setUp(self):
        self.evaluator = ScenarioEvaluator()
        self.test_output = Path("./temp_eval_runs")
        self.test_output.mkdir(parents=True, exist_ok=True)

    def tearDown(self):
        if self.test_output.exists():
            shutil.rmtree(self.test_output)

    def test_silent_wrong_state_on_unwarranted_tool_execution(self):
        """When contract says 'clarify', but agent calls 'create_claim', must flag SILENT_WRONG_STATE."""
        scenario = {
            "id": "A1_test",
            "family": "A_date_time_ambiguity",
            "behavior_contract": {
                "expected_action": "clarify",
                "must_clarify_fields": ["incident_date"],
                "forbidden_actions": ["create_claim"],
            }
        }

        meta = SessionMetadata(framework="langgraph", model="test_model", agent_name="BuggyAgent")
        traj = Trajectory(metadata=meta)
        step = TrajectoryStep(
            step_index=0,
            step_type=StepType.TOOL_CALL,
            tool_call=ToolCallRecord(
                tool_name="create_claim",
                arguments={"policy_id": "POL-1001", "incident_date": "2026-03-04", "amount": 15000},
            )
        )
        traj.add_step(step)
        traj.finalize(success=True, final_answer="Created claim CLM-001")

        scorecard = self.evaluator.evaluate(scenario, traj)
        self.assertFalse(scorecard.passed)
        self.assertTrue(scorecard.silent_wrong_state_detected)
        self.assertFalse(scorecard.contract_adherence)
        self.assertTrue(any("SILENT_WRONG_STATE" in r for r in scorecard.failure_reasons))

    def test_silent_wrong_state_on_forbidden_slot_value(self):
        """When agent executes create_claim with forbidden slot (e.g. inverted date), must flag SILENT_WRONG_STATE."""
        scenario = {
            "id": "A1_test_forbidden_slot",
            "family": "A_date_time_ambiguity",
            "behavior_contract": {
                "expected_action": "execute",
                "expected_tools": ["create_claim"],
                "expected_slots": {"policy_id": "POL-1001", "amount": 15000},
                "forbidden_inferred_slots": {
                    "incident_date": ["2026-03-04"]
                }
            }
        }

        meta = SessionMetadata(framework="langgraph", model="test_model", agent_name="InvertedDateAgent")
        traj = Trajectory(metadata=meta)
        step = TrajectoryStep(
            step_index=0,
            step_type=StepType.TOOL_CALL,
            tool_call=ToolCallRecord(
                tool_name="create_claim",
                arguments={"policy_id": "POL-1001", "incident_date": "2026-03-04", "amount": 15000},
            )
        )
        traj.add_step(step)
        traj.finalize(success=True, final_answer="Done")

        scorecard = self.evaluator.evaluate(scenario, traj)
        self.assertFalse(scorecard.passed)
        self.assertTrue(scorecard.silent_wrong_state_detected)
        self.assertFalse(scorecard.slot_fidelity_passed)

    def test_scenario_pack_runner_end_to_end(self):
        pack_file = str(root_dir / "scenarios" / "claims_v0.json")
        runner = ScenarioPackRunner(output_dir=str(self.test_output))
        adapter = LangGraphAdapter()

        report = runner.run_pack(
            pack_path=pack_file,
            agent_factory=lambda: RuleBasedClaimsAgent(),
            adapter=adapter,
            verbose=False,
        )

        self.assertIn("pack_id", report)
        self.assertGreater(report["total_scenarios"], 20)
        self.assertIn("family_breakdown", report)
        self.assertGreaterEqual(report["overall_pass_rate_pct"], 80.0)


if __name__ == "__main__":
    unittest.main()
