"""Command-Line Interface for rag_knowledge.

Allows standalone testing and querying of the RAG knowledge base
independently of any other services.

Usage:
    python -m rag_knowledge "Do you know about Alex Doe?"
    python -m rag_knowledge --list
    python rag_knowledge/cli.py "Who is Alex Doe?"
"""

import argparse
import asyncio
import os
import sys

# Support running directly as a script
if __package__ is None or __package__ == "":
    sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from rag_knowledge import load_env
from rag_knowledge.service import get_rag_service, query_rag


def list_knowledge_entries():
    """Prints all registered knowledge entries using the shared service retriever."""
    service = get_rag_service()
    docs = service.retriever.documents
    total_str = f"{len(docs)}" if len(docs) < 100 else f"{len(docs)}+ (limit 100 reached)"
    print(f"\n--- Registered Knowledge Documents ({total_str}) ---")
    for doc in docs:
        print(f" * [{doc.get('id')}] {doc.get('title')}")
        print(f"   Keywords: {', '.join(doc.get('keywords', []))}")
        print(f"   Summary:  {doc.get('summary')}")
        print()


async def run_query(query: str, verbose: bool = False):
    """Executes a query against the RAG service and prints results."""
    service = get_rag_service()
    pre_matches = None
    if verbose:
        pre_matches = await asyncio.to_thread(service.retriever.retrieve, query, top_k=2)
        print(f"\n[Retrieval Matches for '{query}']:")
        if pre_matches:
            for idx, m in enumerate(pre_matches, 1):
                print(f"  {idx}. {m.get('title')} (score={m.get('score')})")
        else:
            print("  (No documents met the relevance threshold)")

    print(f"\n[Query]: {query}")
    answer = await service.query(query, pre_retrieved=pre_matches)
    print(f"\n[Answer]:\n{answer}\n")


def main():
    load_env()
    parser = argparse.ArgumentParser(
        description="RAG Knowledge Base - Standalone CLI & Retrieval Tool"
    )
    parser.add_argument(
        "query",
        nargs="?",
        default=None,
        help="Search query or question (e.g. 'Who is Alex Doe?')",
    )
    parser.add_argument(
        "--list",
        action="store_true",
        help="List all documents in the knowledge base",
    )
    parser.add_argument(
        "-v", "--verbose",
        action="store_true",
        help="Print retrieval scoring and matching details",
    )

    args = parser.parse_args()

    if args.list:
        list_knowledge_entries()
        return

    if not args.query:
        parser.print_help()
        sys.exit(1)

    asyncio.run(run_query(args.query, verbose=args.verbose))


if __name__ == "__main__":
    main()
