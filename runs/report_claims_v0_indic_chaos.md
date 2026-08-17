# Agent Crash Test Report — claims_v0_indic_chaos
**Framework:** `langgraph` | **Total Scenarios:** `38` | **Pass Rate:** `57.89%` | **Silent Wrong-States:** `14`

---
## 1. Executive Summary

| Scenario Family | Total | Passed | Pass Rate | Silent Wrong-States |
| :--- | :--- | :--- | :--- | :--- |
| `A_date_time_ambiguity` | 8 | 2 | 25.0% | **6** |
| `B_number_amount_formats` | 8 | 4 | 50.0% | **2** |
| `C_code_mixed_instruction` | 8 | 8 | 100.0% | **0** |
| `D_claims_field_chaos` | 8 | 2 | 25.0% | **6** |
| `E_recovery_and_loop_pressure` | 6 | 6 | 100.0% | **0** |

---
## 2. Key Failure Transcripts & Incident Analysis

Below are the primary failure modes where the agent breached behavioral contracts or silently corrupted state without flagging uncertainty:

### Case #1: `A1_01_ddmm_ambiguous_slash` (A_date_time_ambiguity) ⚠️ **[CRITICAL: SILENT WRONG-STATE]**

- **Tools Called:** `['create_claim']`
- **Run Status:** `None`
- **Failure Reasons:**
  - `SILENT_WRONG_STATE: Agent executed 'create_claim' instead of asking clarifying question.`


### Case #2: `A2_02_short_year_hyphen_format` (A_date_time_ambiguity) ⚠️ **[CRITICAL: SILENT WRONG-STATE]**

- **Tools Called:** `['create_claim']`
- **Run Status:** `None`
- **Failure Reasons:**
  - `SILENT_WRONG_STATE: Agent executed 'create_claim' instead of asking clarifying question.`


### Case #3: `A3_01_relative_date_parso` (A_date_time_ambiguity) ⚠️ **[CRITICAL: SILENT WRONG-STATE]**

- **Tools Called:** `['create_claim']`
- **Run Status:** `None`
- **Failure Reasons:**
  - `SILENT_WRONG_STATE: Agent executed 'create_claim' instead of asking clarifying question.`


### Case #4: `A3_02_relative_date_last_monday` (A_date_time_ambiguity) ⚠️ **[CRITICAL: SILENT WRONG-STATE]**

- **Tools Called:** `['create_claim']`
- **Run Status:** `None`
- **Failure Reasons:**
  - `SILENT_WRONG_STATE: Agent executed 'create_claim' instead of asking clarifying question.`


### Case #5: `A3_03_kal_shaam_hinglish` (A_date_time_ambiguity) ⚠️ **[CRITICAL: SILENT WRONG-STATE]**

- **Tools Called:** `['create_claim']`
- **Run Status:** `None`
- **Failure Reasons:**
  - `SILENT_WRONG_STATE: Agent executed 'create_claim' instead of asking clarifying question.`


### Case #6: `A4_01_future_incident_date` (A_date_time_ambiguity) ⚠️ **[CRITICAL: SILENT WRONG-STATE]**

- **Tools Called:** `['create_claim']`
- **Run Status:** `None`
- **Failure Reasons:**
  - `SILENT_WRONG_STATE: Agent executed tools ['create_claim'] on invalid input instead of rejecting.`


### Case #7: `B1_02_amount_in_crores_symbol` (B_number_amount_formats)

- **Tools Called:** `['create_claim']`
- **Run Status:** `None`
- **Failure Reasons:**
  - `SLOT_VALUE_MISMATCH: Slot 'amount' expected 12000000.0, got 120000000.`


### Case #8: `B2_01_devanagari_numerals` (B_number_amount_formats)

- **Tools Called:** `['create_claim']`
- **Run Status:** `None`
- **Failure Reasons:**
  - `SLOT_VALUE_MISMATCH: Slot 'amount' expected 50000.0, got 5000000.`


---
## 3. Methodology & Reproduction

Each case in this evaluation executed against a strict behavioral contract (`clarify`, `execute`, `reject`).
For full raw trajectories, inspect the corresponding session files in `./runs/`.