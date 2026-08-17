from typing import Any, Dict, List
from pathlib import Path


class FailureReportGenerator:
    """Generates detailed, readable Markdown reports highlighting annotated failure transcripts."""

    @staticmethod
    def generate_markdown_report(report_data: Dict[str, Any], output_path: str) -> Path:
        pack_id = report_data.get("pack_id", "Unknown Pack")
        framework = report_data.get("framework", "Unknown Framework")
        total = report_data.get("total_scenarios", 0)
        passed = report_data.get("total_passed", 0)
        silent_count = report_data.get("total_silent_wrong_states", 0)
        pass_pct = report_data.get("overall_pass_rate_pct", 0.0)
        scorecards = report_data.get("scorecards", [])

        failed_scorecards = [s for s in scorecards if not s.get("passed")]

        lines = [
            f"# Agent Crash Test Report — {pack_id}",
            f"**Framework:** `{framework}` | **Total Scenarios:** `{total}` | **Pass Rate:** `{pass_pct}%` | **Silent Wrong-States:** `{silent_count}`\n",
            "---",
            "## 1. Executive Summary\n",
            "| Scenario Family | Total | Passed | Pass Rate | Silent Wrong-States |",
            "| :--- | :--- | :--- | :--- | :--- |",
        ]

        for fam, stats in report_data.get("family_breakdown", {}).items():
            f_total = stats.get("total", 0)
            f_passed = stats.get("passed", 0)
            f_silent = stats.get("silent_wrong_states", 0)
            f_pct = (f_passed / f_total * 100.0) if f_total > 0 else 0.0
            lines.append(f"| `{fam}` | {f_total} | {f_passed} | {f_pct:.1f}% | **{f_silent}** |")

        lines.extend([
            "\n---",
            "## 2. Key Failure Transcripts & Incident Analysis\n",
            "Below are the primary failure modes where the agent breached behavioral contracts or silently corrupted state without flagging uncertainty:\n",
        ])

        if not failed_scorecards:
            lines.append("> _No failures recorded in this run._\n")
        else:
            for idx, sc in enumerate(failed_scorecards[:8], 1):
                sc_id = sc.get("scenario_id")
                fam = sc.get("family")
                reasons = sc.get("failure_reasons", [])
                is_silent = sc.get("silent_wrong_state_detected")
                repro = sc.get("reproduction_summary", {})

                silent_badge = " ⚠️ **[CRITICAL: SILENT WRONG-STATE]**" if is_silent else ""
                lines.extend([
                    f"### Case #{idx}: `{sc_id}` ({fam}){silent_badge}\n",
                    f"- **Tools Called:** `{repro.get('tools_called', [])}`",
                    f"- **Run Status:** `{repro.get('status')}`",
                    "- **Failure Reasons:**",
                ])
                for r in reasons:
                    lines.append(f"  - `{r}`")
                lines.append("\n")

        lines.extend([
            "---",
            "## 3. Methodology & Reproduction\n",
            "Each case in this evaluation executed against a strict behavioral contract (`clarify`, `execute`, `reject`).",
            "For full raw trajectories, inspect the corresponding session files in `./runs/`.",
        ])

        out_file = Path(output_path)
        out_file.parent.mkdir(parents=True, exist_ok=True)
        with open(out_file, "w", encoding="utf-8") as f:
            f.write("\n".join(lines))

        return out_file
