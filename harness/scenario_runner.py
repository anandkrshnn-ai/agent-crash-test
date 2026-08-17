import json
import os
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional
from datetime import datetime, timezone

# Add project root to sys.path
root_dir = Path(__file__).resolve().parent.parent
if str(root_dir) not in sys.path:
    sys.path.insert(0, str(root_dir))

from harness.trajectory import Trajectory
from harness.evaluator import ScenarioEvaluator, FailureScorecard
from harness.runner import CrashTestRunner
from chaos.base import ChaosConfig
from adapters.base import AgentAdapter
from adapters.langgraph import LangGraphAdapter
from examples.claims_agent import RuleBasedClaimsAgent



class ScenarioPackRunner:
    """
    Executes a scenario pack against an agent adapter and compiles a structured
    Failure Registry report across all scenario families.
    """

    def __init__(self, output_dir: str = "./runs"):
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)
        self.runner = CrashTestRunner(framework="langgraph")
        self.evaluator = ScenarioEvaluator()

    def load_pack(self, pack_path: str) -> Dict[str, Any]:
        with open(pack_path, "r", encoding="utf-8") as f:
            return json.load(f)

    def run_pack(
        self,
        pack_path: str,
        agent_factory: Any,
        adapter: AgentAdapter,
        verbose: bool = True,
    ) -> Dict[str, Any]:
        pack = self.load_pack(pack_path)
        pack_id = pack.get("pack_id", "custom_pack")
        scenarios = pack.get("scenarios", [])

        if verbose:
            print("=" * 80)
            print(f"[EVAL] RUNNING SCENARIO PACK: {pack_id} ({len(scenarios)} test cases)")
            print("=" * 80)

        scorecards: List[FailureScorecard] = []
        family_stats: Dict[str, Dict[str, int]] = {}

        for sc in scenarios:
            sc_id = sc["id"]
            family = sc["family"]
            user_turns = sc["user_turns"]

            if family not in family_stats:
                family_stats[family] = {"total": 0, "passed": 0, "silent_wrong_states": 0, "contract_breaches": 0}
            family_stats[family]["total"] += 1

            # Build chaos config overlay if specified in scenario
            chaos_config = None
            if "chaos_overlay" in sc:
                overlay = sc["chaos_overlay"]
                chaos_kwargs = {
                    "enabled": True,
                    "target_tools": overlay.get("target_tools", []),
                    "timeout_seconds": overlay.get("timeout_duration_sec", 1.0),
                }
                if overlay.get("inject_timeout"):
                    chaos_kwargs["tool_timeout_prob"] = 1.0
                if overlay.get("inject_tool_error"):
                    chaos_kwargs["tool_error_prob"] = 1.0
                if overlay.get("inject_schema_error"):
                    chaos_kwargs["schema_error_prob"] = 1.0
                if overlay.get("inject_malformed_args"):
                    chaos_kwargs["malformed_arguments_prob"] = 1.0

                chaos_config = ChaosConfig(**chaos_kwargs)

            # If adapter supports updating chaos config, set it
            if chaos_config and hasattr(adapter, "chaos_config"):
                adapter.chaos_config = chaos_config
                if hasattr(adapter, "injector"):
                    adapter.injector.config = chaos_config


            agent_instance = agent_factory() if callable(agent_factory) else agent_factory

            # Run agent via adapter
            user_input_str = " ".join(user_turns)
            traj = adapter.run(
                agent=agent_instance,
                input_message=user_input_str,
                model_name="deterministic_baseline",
                tags=[family, sc_id],
            )

            # Save trajectory
            traj_file = self.output_dir / f"{adapter.framework_name}_{traj.metadata.session_id}.json"
            self.runner.save(traj, traj_file)



            # Evaluate against behavior contract
            scorecard = self.evaluator.evaluate(scenario=sc, trajectory=traj)
            scorecards.append(scorecard)

            if scorecard.passed:
                family_stats[family]["passed"] += 1
            if scorecard.silent_wrong_state_detected:
                family_stats[family]["silent_wrong_states"] += 1
            if not scorecard.contract_adherence:
                family_stats[family]["contract_breaches"] += 1

            if verbose:
                status_icon = "[PASS]" if scorecard.passed else "[FAIL]"
                wrong_state_flag = " [!] SILENT_WRONG_STATE" if scorecard.silent_wrong_state_detected else ""
                print(f"  {status_icon:<7} {sc_id:<40} | Family: {family:<28} {wrong_state_flag}")
                if not scorecard.passed:
                    for reason in scorecard.failure_reasons:
                        print(f"         +-- {reason}")

        # Summary Metrics
        total_cases = len(scorecards)
        total_passed = sum(1 for s in scorecards if s.passed)
        total_silent_wrong_states = sum(1 for s in scorecards if s.silent_wrong_state_detected)
        overall_pass_rate = (total_passed / total_cases * 100.0) if total_cases > 0 else 0.0

        report = {
            "pack_id": pack_id,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "framework": adapter.framework_name,
            "total_scenarios": total_cases,
            "total_passed": total_passed,
            "overall_pass_rate_pct": round(overall_pass_rate, 2),
            "total_silent_wrong_states": total_silent_wrong_states,
            "family_breakdown": family_stats,
            "scorecards": [s.model_dump() for s in scorecards],
        }

        # Save Failure Registry Report
        report_file = self.output_dir / f"failure_registry_{pack_id}.json"
        with open(report_file, "w", encoding="utf-8") as f:
            json.dump(report, f, indent=2)

        if verbose:
            print("\n" + "=" * 80)
            print(f"[SUMMARY] OVERALL PASS RATE: {overall_pass_rate:.1f}% ({total_passed}/{total_cases})")
            print(f"[ALERT]   SILENT WRONG-STATES DETECTED: {total_silent_wrong_states}")
            print("-" * 80)
            print(f"{'Family':<35} | {'Total':<6} | {'Passed':<6} | {'Pass %':<8} | {'Silent Errors'}")
            print("-" * 80)
            for fam, stats in family_stats.items():
                p_pct = (stats["passed"] / stats["total"] * 100.0) if stats["total"] > 0 else 0.0
                print(f"{fam:<35} | {stats['total']:<6} | {stats['passed']:<6} | {p_pct:<7.1f}% | {stats['silent_wrong_states']}")
            print("=" * 80)
            print(f"[DONE] Failure Registry exported to: {report_file}")
            print("=" * 80)

        return report


if __name__ == "__main__":
    runner = ScenarioPackRunner(output_dir="./runs")
    pack_file = str(root_dir / "scenarios" / "claims_v0.json")

    # Run against baseline Indic claims agent
    adapter = LangGraphAdapter()
    runner.run_pack(
        pack_path=pack_file,
        agent_factory=lambda: RuleBasedClaimsAgent(),
        adapter=adapter,
        verbose=True,
    )
