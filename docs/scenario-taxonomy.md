# Scenario Taxonomy — Vertical + Code-Mixed Chaos

This document defines the **differentiated** chaos scenarios for Agent Crash Test.
The goal is not "which framework is more robust." The goal is: **where do production-shaped agents fail when Indian users type the way they actually type?**

Same harness. Same tool-boundary injector. New scenario families that existing mid-2026 framework comparisons did not systematically cover.

---

## 1. Design principles

1. **Input realism over random noise** — perturbations mirror real claims/support logs (dates, amounts, code-mix, missing fields).
2. **Trajectory-first scoring** — success is not "final answer looks ok." Score tool selection, argument extraction, recovery, and silent wrong-state.
3. **Reusable scenario packs** — each pack is a set of (user_turn, expected_tool_path, failure_labels) that any adapter can run.
4. **Vertical grounding** — start with two toys: insurance claims intake and support ticket triage. Expand later.

---

## 2. Scenario families (v0)

### Family A — Date & time ambiguity

| ID | Name | What it does | Expected failure modes |
|----|------|--------------|------------------------|
| A1 | `ambiguous_date_ddmm` | User writes `03/04/2026` (DD/MM). Agent or tool assumes MM/DD. | Wrong tool arg; silent date shift; claim period error |
| A2 | `mixed_date_formats` | Same conversation mixes `3 Apr`, `03-04-26`, `April 3rd`. | Inconsistent extraction across turns |
| A3 | `relative_date_noise` | "day before yesterday", "last Monday", "kal" (Hinglish). | Failed resolution; wrong relative offset |

### Family B — Number & amount formats

| ID | Name | What it does | Expected failure modes |
|----|------|--------------|------------------------|
| B1 | `lakh_crore` | Amount in words/units: "2.5 lakh", "₹1.2 Cr". | Parse failure; wrong currency scale |
| B2 | `mixed_script_amount` | "Rs 5000" / "₹५०००" / "five thousand only". | Extraction miss; partial amount |
| B3 | `comma_vs_decimal` | European vs Indian comma placement in numbers. | Off-by-factor tool args |

### Family C — Code-mixed instruction (Hinglish / Tanglish)

| ID | Name | What it does | Expected failure modes |
|----|------|--------------|------------------------|
| C1 | `hinglish_tool_intent` | "Mujhe claim status check karna hai for policy 123" | Wrong tool; English-only fallback path |
| C2 | `tanglish_mid_sentence` | "Naan accident details update pannanum — date 12/3" | Entity split across languages; missed slots |
| C3 | `script_switch_name` | Name in Tamil/Devanagari + English policy id in same turn | Name mangling; failed lookup key |
| C4 | `code_mix_contradiction` | First turn Tamil-ish, second turn English contradicts amount/date | Inconsistent state; no clarification ask |

### Family D — Claims / support field chaos

| ID | Name | What it does | Expected failure modes |
|----|------|--------------|------------------------|
| D1 | `missing_required_slot` | User omits policy number or incident date. | Proceeds with null; hallucinated fill |
| D2 | `contradictory_fields` | Amount in text ≠ amount in attached "form" tool result. | Silent preference for one source |
| D3 | `partial_tool_then_user_fix` | Tool returns partial record; user supplies rest in code-mix. | State merge failure; loop |
| D4 | `duplicate_claim_signal` | User language implies re-filing; system has open claim. | Double create; no idempotency check |

### Family E — Recovery & loop pressure

| ID | Name | What it does | Expected failure modes |
|----|------|--------------|------------------------|
| E1 | `tool_error_then_retry_noise` | First tool call fails (chaos); user rephrases in Hinglish. | Infinite retry; abandon; wrong tool on retry |
| E2 | `schema_error_after_code_mix` | Schema-breaking tool result after mixed-language extract. | Uncaught exception; empty final answer |

---

## 3. Scoring dimensions (per trajectory)

Do **not** use BLEU / string match as primary score.

| Dimension | Pass condition (sketch) |
|-----------|-------------------------|
| Tool selection | Correct tool chosen for the user's intent |
| Slot fidelity | Critical entities (date, amount, policy id, name) match ground truth under the scenario's ambiguity rules |
| Recovery | After injected tool chaos, agent either retries sanely or asks a clarifying question — does not silently invent |
| No silent wrong-state | Final state does not contain a confidently wrong date/amount |
| Language adherence | Does not abandon user's language without need (optional, softer) |

Each run produces a structured Failure Registry entry: scenario_id, chaos applied, failed dimensions, reproduction payload.

---

## 4. Toy agents for the first report

### 4.1 Claims intake (LangGraph or CrewAI)

Tools (minimal):

- `lookup_policy(policy_id: str)`
- `create_claim(policy_id, incident_date, amount, description)`
- `get_claim_status(claim_id)`

User turns: Family A + B + C + D packs.

### 4.2 Support ticket triage

Tools:

- `search_kb(query: str)`
- `create_ticket(category, priority, summary)`
- `add_note(ticket_id, text)`

User turns: C + D + E packs.

Both agents must be runnable with a deterministic mock backend (no LLM required for CI) **and** with an open local model for the public report.

---

## 5. Test-case design template

```text
scenario_id: C1_hinglish_tool_intent
user_turns:
  - "Mujhe policy POL-9981 ka claim status check karna hai"
expected:
  tool: get_claim_status | lookup then status
  slots: { policy_id: "POL-9981" }
chaos_overlay: optional tool_timeout on first call
labels_if_fail:
  - wrong_tool
  - english_only_fallback
  - slot_drop
```

Ground truth is defined **per scenario**, including which ambiguities are allowed (e.g. A1: only DD/MM is correct).

---

## 6. First public report shape (when ready)

Not a leaderboard.

1. Method: harness + scenario packs A–E, N runs per pack
2. Failure registry summary: rates by family and by dimension
3. 5–8 annotated trajectory excerpts (code-mix + date + amount failures)
4. What the taxonomy does *not* cover yet
5. Reproduction: this repo + scenario pack commit SHA

Audience: teams shipping claims/support agents in India, and anyone building agent eval for code-mixed production input.

---

## 7. Implementation order (for next commits)

1. Add scenario pack data files (`scenarios/claims_v0.yaml` or JSON) — pure data, no new chaos engine required for user-turn packs
2. Extend `ChaosConfig` / injector only where tool-level overlays are needed (timeouts already exist)
3. Deterministic mock claims agent example (mirror `langgraph_math.py`)
4. Runner that executes a pack and emits Failure Registry JSON
5. One vertical report draft from real runs

---

## 8. Out of scope for v0

- Full Indic LLM Arena-style preference voting
- Voice / ASR noise (later)
- Multi-agent contention across tenants
- Framework ranking tables as the headline result
