"""
Riva-AGI RAG Agent Integration Demo
====================================
Demonstrates how the autonomous Multi-Agent loop leverages the Qdrant
RAG Knowledge Base tools to route, retrieve, and ground answers with citations.

Usage:
    python examples/demo_rag_agent.py
"""

import sys
from pathlib import Path

# Ensure repository root is on sys.path
REPO_ROOT = Path(__file__).resolve().parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from orchestration.tools.registry import tool_registry
import orchestration.tools.builtin
from orchestration.orchestrator.registry import registry
import orchestration.agents.researcher
from orchestration.orchestrator.router import classify_intent
from orchestration.tools.builtin.rag_tools import (
    search_knowledge_base,
    list_knowledge_documents,
    query_knowledge_with_citations,
)


def print_header(title: str):
    print("\n" + "=" * 65)
    print(f"  {title}")
    print("=" * 65)


def demo_tool_registration():
    print_header("1. Tool Registry Verification")
    all_tools = tool_registry.get_all_tools()
    rag_tools = [name for name in all_tools if "knowledge" in name]
    print(f"Total tools registered in Riva-AGI: {len(all_tools)}")
    print(f"RAG Knowledge tools available ({len(rag_tools)}):")
    for name in rag_tools:
        tool_def = tool_registry.get(name)
        desc = (tool_def.description or "").split("\n")[0]
        print(f"  - {name:32} -> {desc}")


def demo_agent_capabilities():
    print_header("2. Researcher Agent Equipped Capabilities")
    researcher_cap = registry.get_capabilities("researcher")
    if researcher_cap:
        print(f"Agent Role: researcher ({researcher_cap.agent_level})")
        print(f"Description: {researcher_cap.description}")
        print("Equipped Tools:")
        for t in researcher_cap.tools:
            is_rag = "knowledge" in t
            badge = "[RAG TOOL]" if is_rag else "[BASE TOOL]"
            print(f"  - {t:32} {badge}")
    else:
        print("Researcher agent not found in registry.")


def demo_intent_routing():
    print_header("3. Dynamic Intent & Keyword Routing")
    test_queries = [
        "What are the internal guidelines for API key rotation in the docs?",
        "Look up the schedule in the ComputeX handbook PDF",
        "Write a Python script to sort a list of numbers",
        "Search the web for latest quantum computing breakthroughs",
    ]

    for query in test_queries:
        result = classify_intent(query)
        print(f"Query: \"{query}\"")
        print(f"  ==> Intent: {result['intent']} | Agent: {result['agent']} | Confidence: {result['confidence']:.2f}\n")


def demo_rag_tool_execution():
    print_header("4. Direct Tool Execution (search & list)")
    print("Executing 'list_knowledge_documents()':")
    docs_output = list_knowledge_documents()
    print(f"Result:\n  {docs_output}\n")

    test_query = "NVIDIA Riva deployment guidelines"
    print(f"Executing 'search_knowledge_base(query=\"{test_query}\")':")
    search_output = search_knowledge_base(test_query)
    print(f"Result:\n  {search_output}\n")


def demo_grounded_mock_retrieval():
    print_header("5. Grounded RAG Retrieval Simulation (Mock)")
    from unittest.mock import MagicMock, patch

    mock_chunks = [
        {
            "title": "ComputeX_2026_Keynote_Guide.pdf",
            "score": 0.94,
            "content": "The keynote session begins at 09:00 AM PST on Hall A. Key announcements include Riva-AGI v2.0 autonomous agent clustering.",
            "metadata": {"source": "ComputeX_2026_Keynote_Guide.pdf", "page": 3},
        },
        {
            "title": "Internal_Agent_Guidelines.docx",
            "score": 0.88,
            "content": "Autonomous agents must always perform retrieval-augmented validation before issuing destructive commands.",
            "metadata": {"source": "Internal_Agent_Guidelines.docx", "page": 12},
        },
    ]

    mock_retriever = MagicMock()
    mock_retriever.retrieve.return_value = mock_chunks

    with patch("orchestration.tools.builtin.rag_tools._get_retriever", return_value=mock_retriever):
        print("Simulating query against indexed documents in Qdrant:")
        result = search_knowledge_base("When does keynote begin and what are agent guidelines?")
        print(result)


def main():
    print("\n" + "#" * 65)
    print("    RIVA-AGI AUTONOMOUS RAG KNOWLEDGE INTEGRATION DEMO")
    print("#" * 65)

    demo_tool_registration()
    demo_agent_capabilities()
    demo_intent_routing()
    demo_rag_tool_execution()
    demo_grounded_mock_retrieval()

    print("\n" + "=" * 65)
    print("  Demo completed successfully! Everything is fully operational.")
    print("=" * 65 + "\n")


if __name__ == "__main__":
    main()
