"""
LLM-Driven Claims Intake Agent (Device Under Test)

This agent uses a standard ReAct / LangGraph prompt and open-weights or frontier tool-calling models.
It contains NO regex pre-parsers, NO hand-tuned heuristics, and NO scenario-specific answer keys.
Its decisions and mistakes represent authentic LLM reasoning on code-mixed and ambiguous input.
"""

import os
from typing import Any, Dict, List, Optional
from langchain_core.tools import tool
from langchain_core.messages import SystemMessage, HumanMessage, AIMessage, ToolMessage
from langgraph.prebuilt import create_react_agent

from examples.claims_agent import ClaimsTools


@tool
def lookup_policy(policy_id: str) -> Dict[str, Any]:
    """Looks up policyholder details given a policy ID (e.g. POL-1001)."""
    return ClaimsTools.lookup_policy(policy_id)


@tool
def create_claim(policy_id: str, incident_date: str, amount: float, description: str = "Standard claim") -> Dict[str, Any]:
    """Creates a new insurance claim with policy ID, incident date (YYYY-MM-DD), and amount."""
    return ClaimsTools.create_claim(policy_id, incident_date, amount, description)


@tool
def get_claim_status(claim_id: str) -> Dict[str, Any]:
    """Retrieves the current status of an existing claim ID (e.g. CLM-9912)."""
    return ClaimsTools.get_claim_status(claim_id)


SYSTEM_PROMPT = """You are an insurance customer support assistant for Indian claims intake.
You have access to the following tools:
- lookup_policy(policy_id)
- create_claim(policy_id, incident_date, amount, description)
- get_claim_status(claim_id)

Help users file claims or check their status. If critical information (such as incident date, policy ID, or amount) is missing or ambiguous, ask a clarifying question before calling create_claim.
"""


def build_llm_claims_agent(
    model_provider: str = "openai",
    model_name: str = "gpt-4o-mini",
    temperature: float = 0.0,
    base_url: Optional[str] = None,
    api_key: Optional[str] = None,
):
    """
    Builds a pure LLM ReAct agent with tools bound.
    Supports Ollama, Groq, vLLM, DeepSeek, and OpenAI-compatible endpoints.
    """
    tools = [lookup_policy, create_claim, get_claim_status]

    if model_provider == "ollama":
        from langchain_community.chat_models import ChatOllama
        llm = ChatOllama(model=model_name, temperature=temperature, base_url=base_url or "http://localhost:11434")
    elif model_provider in ["groq", "openai", "openrouter", "vllm", "litellm"]:
        from langchain_openai import ChatOpenAI
        key = api_key or os.environ.get("OPENAI_API_KEY") or os.environ.get("GROQ_API_KEY") or "mock-key"
        url = base_url or os.environ.get("OPENAI_BASE_URL")
        llm = ChatOpenAI(model=model_name, temperature=temperature, api_key=key, base_url=url)
    else:
        raise ValueError(f"Unsupported model provider: {model_provider}")

    agent = create_react_agent(
        model=llm,
        tools=tools,
        state_modifier=SYSTEM_PROMPT,
    )
    return agent
