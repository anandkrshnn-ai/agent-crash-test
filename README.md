# Agent Crash Test – Open

Minimal, extensible harness for stress-testing open agent frameworks (LangGraph, CrewAI) under controlled chaos.

## Goals

- Capture **full trajectories** (thoughts, tool calls, results, state)
- Inject **reproducible chaos** (timeouts, malformed args, schema errors, partial results, …)
- Produce a structured **Failure Registry** entry for every run
- Start with open models + open frameworks so anyone can reproduce

## Quickstart

### 1. Harness Regression Check (Reference Baseline)
Runs the deterministic reference baseline to verify harness mechanics, trajectory serialization, and evaluator scoring:
```bash
python harness/scenario_runner.py --agent baseline
```

### 2. Authentic Agent Crash Test (LLM Device Under Test)
Evaluates an un-tuned LLM model on the `claims_v0` Indic chaos pack without pre-tuned heuristics:
```bash
# Local open weights via Ollama
python harness/scenario_runner.py --agent llm --provider ollama --model qwen2.5:7b

# Cloud / Open weights via Groq / OpenAI-compatible endpoint
python harness/scenario_runner.py --agent llm --provider groq --model llama-3.1-70b-versatile
```

### 3. Run Automated Test Suite
```bash
python -m unittest discover -s tests -p "test_*.py"
```

---

## Evaluation Philosophy: Baseline vs. DUT

- **`RuleBasedClaimsAgent` (Reference Baseline)**: A rule-based parser used exclusively in CI to verify harness invariants and ensure trajectory capture is lossless. It is **not** a benchmark candidate.
- **`build_llm_claims_agent` (Device Under Test)**: A pure ReAct agent connected to open or frontier models. Evaluator scorecards on this agent expose authentic LLM reasoning failures: date inversion assumptions, crore/lakh conversion drops, and unhandled multi-turn contradictions.

Trajectories are written to `runs/*.json`.

## Layout

```
agent-crash-test/
├── chaos/           # ChaosConfig + ToolChaosInjector + ChaosToolWrapper
├── adapters/        # LangGraphAdapter, CrewAIAdapter
├── harness/         # Trajectory models + CrashTestRunner
├── examples/        # Ready-to-run agents
├── docs/            # Scenario taxonomy (vertical + code-mixed)
├── tests/
├── LICENSE          # MIT
└── requirements.txt
```

## Chaos Types (current)

| Type                    | What it does                                      |
|-------------------------|---------------------------------------------------|
| `tool_timeout`          | Sleeps then raises TimeoutError                   |
| `malformed_arguments`   | Drops / type-flips / nullifies tool args          |
| `tool_error`            | Raises a simulated RuntimeError                   |
| `partial_result`        | Truncates or drops parts of the tool return value |
| `schema_error`          | Returns a type/shape the agent did not expect     |
| `delayed_result`        | Adds latency but returns a normal result          |

All probabilities and a hard `max_chaos_per_run` cap are configurable via `ChaosConfig`.

## Next Steps

1. Run the LangGraph math example and inspect the JSON trajectories.
2. Add more chaos dimensions (contradictory instructions, state corruption, multi-agent contention).
3. Expand the failure taxonomy and auto-label trajectories.
4. Add Ollama / local open-model examples.
5. **First public report (revised):** map failure surfaces on *vertical + code-mixed* scenarios — not a framework bake-off. Target: production-shaped Indian enterprise agents (claims intake, support tickets) under Hinglish/Tanglish input noise, ambiguous dates, and regional number formats. See `docs/scenario-taxonomy.md`.

## Design Notes

- Chaos is applied at the **tool boundary** so the same injector works across frameworks.
- Adapters are deliberately thin; they only need to (a) wrap tools and (b) turn framework events into `TrajectoryStep`s.
- The trajectory schema is the long-term contract – keep it stable.
- License: MIT (see `LICENSE`).
