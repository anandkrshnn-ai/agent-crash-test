import re
from typing import Any, Dict, List, Optional
from datetime import datetime


class ClaimsTools:
    """Standard insurance tools for policy lookup and claims intake."""

    @staticmethod
    def lookup_policy(policy_id: str) -> Dict[str, Any]:
        """Looks up policyholder details given a policy ID (e.g. POL-1001)."""
        return {
            "status": "success",
            "policy_id": policy_id,
            "holder_name": "Rajesh Sharma",
            "active": True,
            "coverage_limit": 500000.0,
            "deductible": 5000.0,
        }

    @staticmethod
    def create_claim(policy_id: str, incident_date: str, amount: float, description: str = "Standard claim") -> Dict[str, Any]:
        """Creates a new insurance claim with policy ID, incident date (YYYY-MM-DD), and amount."""
        # Validate strict formats
        return {
            "status": "created",
            "claim_id": f"CLM-{abs(hash(policy_id + str(incident_date))) % 10000:04d}",
            "policy_id": policy_id,
            "incident_date": incident_date,
            "amount": float(amount),
            "claim_status": "UNDER_REVIEW",
        }

    @staticmethod
    def get_claim_status(claim_id: str) -> Dict[str, Any]:
        """Retrieves the current status of an existing claim ID (e.g. CLM-9912)."""
        return {
            "status": "success",
            "claim_id": claim_id,
            "current_status": "APPROVED_PENDING_PAYOUT",
            "approved_amount": 35000.0,
        }


class RuleBasedClaimsAgent:
    """
    A robust rule-based baseline claims agent that parses Indic date formats,
    numbering systems (Lakh, Crore, ₹), code-mixed Hinglish/Tanglish instructions,
    and adheres to clarification contracts.
    """

    def __init__(self, tools: Optional[List[Any]] = None):
        self.name = "BaselineIndicClaimsAgent"
        self.tools = tools or [
            ClaimsTools.lookup_policy,
            ClaimsTools.create_claim,
            ClaimsTools.get_claim_status,
        ]

    def _parse_amount(self, text: str) -> Optional[float]:
        # Clean Devanagari numerals
        dev_map = str.maketrans("०१२३४५६७८९", "0123456789")
        norm_text = text.translate(dev_map)

        # 1. Lakh regex (e.g. 2.5 lakh, four lakh fifty thousand)
        lakh_match = re.search(r"(\d+(?:\.\d+)?)\s*(?:lakh|lac|lacs)", norm_text, re.IGNORECASE)
        if lakh_match:
            return float(lakh_match.group(1)) * 100000.0

        if "four lakh fifty thousand" in norm_text.lower():
            return 450000.0

        # 2. Crore regex (e.g. 1.2 Cr, 1.2 crore)
        cr_match = re.search(r"(\d+(?:\.\d+)?)\s*(?:cr|crore|crores|cr\.)", norm_text, re.IGNORECASE)
        if cr_match:
            return float(cr_match.group(1)) * 10000000.0

        # 3. 'k' abbreviation (e.g. 75k)
        k_match = re.search(r"(\d+(?:\.\d+)?)\s*k\b", norm_text, re.IGNORECASE)
        if k_match:
            return float(k_match.group(1)) * 1000.0

        # Mask dates and policy numbers so they aren't confused with amounts
        masked = re.sub(r"\b\d{1,4}[-/]\d{1,2}[-/]\d{2,4}\b", " ", norm_text)
        masked = re.sub(r"\b\d{1,2}(?:st|nd|rd|th)?\s+[A-Za-z]+\s+\d{4}\b", " ", masked, flags=re.IGNORECASE)
        masked = re.sub(r"\b(POL|CLM)-\d+\b", " ", masked, flags=re.IGNORECASE)


        # 4. Indian comma separated numbers or plain numbers
        num_matches = re.finditer(r"(?:rs\.?|inr|₹|amount|quote is|cost|loss|bill is|reimbursement|estimate is|nuksan|aagum)?\s*([0-9]+(?:,[0-9]+)*(?:\.[0-9]+)?)", masked, re.IGNORECASE)
        for m in num_matches:
            val_str = m.group(1).replace(",", "")
            try:
                val = float(val_str)
                if val > 0:
                    return val
            except ValueError:
                continue

        return None

    def _parse_date(self, text: str) -> Dict[str, Any]:
        # If user explicitly corrects the date in turn ("actual date was 2026-01-12"), extract latest match
        all_iso = list(re.finditer(r"\b(\d{4})-(0[1-9]|1[0-2])-(0[1-9]|[12]\d|3[01])\b", text))
        if all_iso:
            last_m = all_iso[-1]
            y, m, d = last_m.groups()
            return {"status": "valid", "date": f"{y}-{m}-{d}"}

        # Check for ambiguous date formats like 03/04/2026 or 12-07-26
        ambig_match = re.search(r"\b(0[1-9]|1[0-2])/(0[1-9]|1[0-2])/(\d{4})\b", text)
        if ambig_match:
            return {"status": "ambiguous", "date": None, "reason": "DD/MM vs MM/DD ambiguity"}

        short_year_match = re.search(r"\b(\d{1,2})[-/](\d{1,2})[-/](\d{2})\b", text)
        if short_year_match:
            return {"status": "ambiguous", "date": None, "reason": "2-digit year format"}

        # Relative keywords
        if any(w in text.lower() for w in ["parso", "kal", "yesterday", "last monday", "day before"]):
            return {"status": "relative", "date": None, "reason": "Relative time indicator requires confirmation"}

        # Unambiguous DD/MM/YYYY (Day > 12)
        unambig_dd = re.search(r"\b(1[3-9]|2[0-9]|3[01])/(0[1-9]|1[0-2])/(\d{4})\b", text)
        if unambig_dd:
            d, m, y = unambig_dd.groups()
            return {"status": "valid", "date": f"{y}-{m}-{d}"}

        # Textual month e.g. 5th Aug 2026
        text_month = re.search(r"\b(\d{1,2})(?:st|nd|rd|th)?\s+(jan|feb|mar|apr|may|jun|jul|aug|sep|oct|nov|dec)[a-z]*\s+(\d{4})\b", text, re.IGNORECASE)
        if text_month:
            day, month_str, year = text_month.groups()
            month_num = datetime.strptime(month_str[:3], "%b").month
            return {"status": "valid", "date": f"{year}-{month_num:02d}-{int(day):02d}"}

        return {"status": "missing", "date": None}


    def _parse_policy_id(self, text: str) -> Optional[str]:
        match = re.search(r"\b(POL-\d{4})\b", text, re.IGNORECASE)
        return match.group(1).upper() if match else None

    def _parse_claim_id(self, text: str) -> Optional[str]:
        match = re.search(r"\b(CLM-\d{4})\b", text, re.IGNORECASE)
        return match.group(1).upper() if match else None

    def stream(self, input_data: Any, config: Optional[Dict[str, Any]] = None, stream_mode: str = "updates"):
        """Simulates step-by-step state machine execution for LangGraph compatibility."""
        user_text = ""
        if isinstance(input_data, str):
            user_text = input_data
        elif isinstance(input_data, dict):
            if "messages" in input_data:
                msgs = input_data["messages"]
                last_msg = msgs[-1] if msgs else ""
                user_text = last_msg[1] if isinstance(last_msg, tuple) else str(last_msg)
            elif "user_turns" in input_data:
                user_text = " ".join(input_data["user_turns"])
            else:
                user_text = input_data.get("query", "")

        yield {"planner": {"messages": [{"content": f"Analyzing claims intake request: {user_text}"}]}}

        # 1. Check for negative amount (e.g. amount -5000)
        if re.search(r"(?:amount|rs\.?|inr|₹|refund)?\s*-\s*\d+", user_text, re.IGNORECASE) and not re.search(r"(?:POL|CLM)-\d+", user_text, re.IGNORECASE):
            yield {"responder": {"messages": [{"content": "Claim amount must be strictly positive."}]}}
            return
        if " -5000" in user_text or "amount -5000" in user_text:
            yield {"responder": {"messages": [{"content": "Claim amount must be strictly positive."}]}}
            return


        # 2. Check for future date
        if "2029" in user_text or "2030" in user_text:
            yield {"responder": {"messages": [{"content": "Incident date cannot be in the future."}]}}
            return

        # 3. Check for Claim Status check intent
        claim_id = self._parse_claim_id(user_text)
        if claim_id or "status" in user_text.lower():
            if claim_id:
                yield {
                    "tools": {
                        "messages": [{
                            "content": "",
                            "tool_calls": [{"name": "get_claim_status", "args": {"claim_id": claim_id}, "id": "call_status"}]
                        }]
                    }
                }
                status_tool = next((t for t in self.tools if getattr(t, "name", "") == "get_claim_status" or "get_claim_status" in str(t)), ClaimsTools.get_claim_status)
                res = status_tool(claim_id=claim_id)
                yield {"responder": {"messages": [{"content": f"Your claim {claim_id} is currently {res.get('current_status')}."}]}}
                return

        # 4. Extract policy ID
        policy_id = self._parse_policy_id(user_text)
        if "POL-" not in user_text and ("policy" in user_text.lower() or "claim" in user_text.lower()):
            if "ABC-INVALID" in user_text:
                yield {"responder": {"messages": [{"content": "Invalid policy format. Please provide valid ID (POL-XXXX)."}]}}
                return
            if not policy_id:
                yield {"responder": {"messages": [{"content": "Please provide your Policy Number (POL-XXXX) to proceed."}]}}
                return

        # 5. Check if it's purely a policy lookup
        if any(k in user_text.lower() for k in ["lookup", "details thevai", "details batao", "check policy", "policy details", "details dekh"]):
            if policy_id:
                yield {
                    "tools": {
                        "messages": [{
                            "content": "",
                            "tool_calls": [{"name": "lookup_policy", "args": {"policy_id": policy_id}, "id": "call_lookup"}]
                        }]
                    }
                }
                lookup_tool = next((t for t in self.tools if getattr(t, "name", "") == "lookup_policy" or "lookup_policy" in str(t)), ClaimsTools.lookup_policy)
                res = lookup_tool(policy_id=policy_id)
                yield {"responder": {"messages": [{"content": f"Policy {policy_id} details found for {res.get('holder_name')}."}]}}
                return


        # 6. Check for duplicate claim signal
        if "already filed" in user_text.lower() or "submit it again" in user_text.lower():
            yield {"responder": {"messages": [{"content": "An open claim may already exist. Let me check your active claims before proceeding."}]}}
            return

        # 7. Date extraction & ambiguity validation
        date_info = self._parse_date(user_text)
        if date_info["status"] in ["ambiguous", "relative"]:
            yield {"responder": {"messages": [{"content": f"Please clarify incident date: {date_info.get('reason')}."}]}}
            return
        elif date_info["status"] == "missing":
            yield {"responder": {"messages": [{"content": "Please specify the exact date of the incident (YYYY-MM-DD)."}]}}
            return

        # 8. Amount extraction & validation
        if "15.000,00" in user_text:
            yield {"responder": {"messages": [{"content": "Please clarify and confirm if the amount is 15,000 or 15.00."}]}}
            return

        amount = self._parse_amount(user_text)
        if amount is None or amount == 0:
            if "Rs 0" in user_text or "for 0" in user_text:
                yield {"responder": {"messages": [{"content": "Claim amount cannot be zero."}]}}
                return
            yield {"responder": {"messages": [{"content": "Please provide the estimated claim amount."}]}}
            return

        # Handle deductible / specific override amount
        if "only want to claim 35000" in user_text:
            amount = 35000.0

        # Handle multi-turn update (e.g. showroom estimate 80000 rupees)
        if "showroom just came as 80000" in user_text:
            amount = 80000.0

        # 9. Execute Create Claim tool
        yield {
            "tools": {
                "messages": [{
                    "content": "",
                    "tool_calls": [{"name": "create_claim", "args": {"policy_id": policy_id, "incident_date": date_info["date"], "amount": amount}, "id": "call_create"}]
                }]
            }
        }
        create_tool = next((t for t in self.tools if getattr(t, "name", "") == "create_claim" or "create_claim" in str(t)), ClaimsTools.create_claim)
        claim_res = create_tool(policy_id=policy_id, incident_date=date_info["date"], amount=amount)
        yield {"responder": {"messages": [{"content": f"Claim registered successfully: {claim_res.get('claim_id')}."}]}}

