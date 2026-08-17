"""
Minimal CrewAI example for verifying the harness.

Note: CrewAI pulls in a larger dependency set and usually needs an LLM key.
This example is structured so that once you have CREWAI / OpenAI / Ollama
configured it can be run. For pure offline verification prefer the
LangGraph math example.
"""

from __future__ import annotations

from pathlib import Path
from typing import Optional

from chaos.base import ChaosConfig
from harness.runner import CrashTestRunner


def build_simple_crew(llm: Optional[object] = None):
    """Build a tiny two-agent crew (researcher + writer)."""
    try:
        from crewai import Agent, Crew, Process, Task
        from crewai_tools import SerperDevTool  # optional; may not be installed
    except ImportError as e:
        raise ImportError(
            "CrewAI (and optionally crewai-tools) must be installed to run this example.\n"
            "pip install crewai crewai-tools"
        ) from e

    # Use a dummy search tool if Serper is not available
    try:
        search_tool = SerperDevTool()
    except Exception:
        # Fallback no-op tool
        from langchain_core.tools import tool

        @tool
        def dummy_search(query: str) -> str:
            """Dummy search that returns a fixed string."""
            return f"[dummy search results for: {query}]"

        search_tool = dummy_search

    researcher = Agent(
        role="Researcher",
        goal="Find accurate facts",
        backstory="You are a careful researcher.",
        tools=[search_tool],
        llm=llm,
        verbose=False,
        allow_delegation=False,
    )

    writer = Agent(
        role="Writer",
        goal="Write clear short summaries",
        backstory="You turn research into concise text.",
        llm=llm,
        verbose=False,
        allow_delegation=False,
    )

    task1 = Task(
        description="Research the topic: {input}",
        expected_output="A short bullet list of facts",
        agent=researcher,
    )
    task2 = Task(
        description="Write a 3-sentence summary from the research",
        expected_output="A 3-sentence paragraph",
        agent=writer,
        context=[task1],
    )

    crew = Crew(
        agents=[researcher, writer],
        tasks=[task1, task2],
        process=Process.sequential,
        verbose=False,
    )
    return crew


def main():
    print("CrewAI example – requires a configured LLM (OpenAI, Ollama, etc.).")
    print("Skipping actual execution in the scaffold; structure is ready.")
    print("Once you have an LLM, uncomment the run block below.")

    # Uncomment when LLM is available:
    #
    # from langchain_ollama import ChatOllama
    # llm = ChatOllama(model="llama3.1")
    # crew = build_simple_crew(llm=llm)
    #
    # chaos = ChaosConfig(
    #     enabled=True,
    #     malformed_arguments_prob=0.5,
    #     tool_error_prob=0.3,
    #     max_chaos_per_run=2,
    # )
    # runner = CrashTestRunner(framework="crewai", chaos=chaos)
    # traj = runner.run(
    #     agent=crew,
    #     input_message="Latest developments in agent evaluation 2026",
    #     model_name="llama3.1",
    #     agent_name="research-writer-crew",
    #     tags=["demo", "crewai"],
    # )
    # print(traj.summary())
    # runner.save(traj, Path("runs") / "crewai_writer_chaos.json")


if __name__ == "__main__":
    main()
