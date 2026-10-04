"""Command-Line Interface for rag_knowledge.

Allows standalone testing and querying of the RAG knowledge base
independently of any other services.

Usage:
    python -m rag_knowledge "Do you know about Raj Ojha?"
    python -m rag_knowledge --list
    python rag_knowledge/cli.py "Who is Raj Ojha?"
"""

import argparse
import asyncio
import os
import sys

# Support running directly as a script
if __package__ is None or __package__ == "":
    sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from rag_knowledge.service import get_rag_service, query_rag


def list_knowledge_entries():
    """Prints all registered knowledge entries using the shared service retriever."""
    service = get_rag_service()
    docs = service.retriever.documents
    print(f"\n--- Registered Knowledge Documents ({len(docs)}) ---")
    for doc in docs:
        print(f" * [{doc.get('id')}] {doc.get('title')}")
        print(f"   Keywords: {', '.join(doc.get('keywords', []))}")
        print(f"   Summary:  {doc.get('summary')}")
        print()


async def run_query(query: str, verbose: bool = False):
    """Executes a query against the RAG service and prints results."""
    service = get_rag_service()
    if verbose:
        matches = service.retriever.retrieve(query, top_k=2)
        print(f"\n[Retrieval Matches for '{query}']:")
        if matches:
            for idx, m in enumerate(matches, 1):
                print(f"  {idx}. {m.get('title')} (score={m.get('score')})")
        else:
            print("  (No documents met the relevance threshold)")

    print(f"\n[Query]: {query}")
    answer = await service.query(query)
    print(f"\n[Answer]:\n{answer}\n")


def main():
    parser = argparse.ArgumentParser(
        description="RAG Knowledge Base - Standalone CLI & Retrieval Tool"
    )
    parser.add_argument(
        "query",
        nargs="?",
        default=None,
        help="Search query or question",
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
