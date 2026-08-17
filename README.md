# Agent Crash Test – Open

Minimal, extensible harness for stress-testing open agent frameworks (LangGraph, CrewAI) under controlled chaos.

## Goals

- Capture **full trajectories** (thoughts, tool calls, results, state)
- Inject **reproducible chaos** (timeouts, malformed args, schema errors, partial results, …)
- Produce a structured **Failure Registry** entry for every run
- Start with open models + open frameworks so anyone can reproduce

## Quick Start

```bash
cd agent-crash-test
python -m venv .venv
source .venv/bin/activate   # or Windows equivalent
pip install -r requirements.txt

# Unit tests (no LLM needed)
pytest tests/ -v

# Minimal LangGraph demo (deterministic, no LLM key required)
python -m examples.langgraph_math
```

Trajectories are written to `runs/*.json`.

## Layout

```
agent-crash-test/
├── chaos/           # ChaosConfig + ToolChaosInjector + ChaosToolWrapper
├── adapters/        # LangGraphAdapter, CrewAIAdapter
├── harness/         # Trajectory models + CrashTestRunner
├── examples/        # Ready-to-run agents
├── tests/
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
5. Publish a first public “Open Agent Crash Test Report”.

## Design Notes

- Chaos is applied at the **tool boundary** so the same injector works across frameworks.
- Adapters are deliberately thin; they only need to (a) wrap tools and (b) turn framework events into `TrajectoryStep`s.
- The trajectory schema is the long-term contract – keep it stable.
