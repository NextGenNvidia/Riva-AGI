# RAG Knowledge Subsystem (`rag_knowledge`)

A modular, zero-dependency, self-contained Retrieval-Augmented Generation (RAG) package. Designed to provide fast factual knowledge retrieval and Mistral AI synthesis for conversational agents, voice assistants, and multi-agent platforms.

---

## Highlights

- **Completely Self-Contained**: Can be run, tested, and imported independently or merged with other systems without impacting other directories.
- **Zero Heavy Runtime Dependencies**: Built entirely with Python standard library (`urllib.request`, `json`, `asyncio`, `re`, `logging`). No mandatory external SDKs.
- **Mistral API Synthesis**: Uses Mistral Chat Completion (`mistral-small-latest` by default) to generate natural, conversational 2–3 sentence spoken answers.
- **Resilient Fallback**: If `MISTRAL_API_KEY` is omitted or API is unavailable, it immediately returns the factual grounded text directly so conversational pipelines never fail.
- **Customizable Knowledge Base**: Knowledge is stored in a clean JSON format in [`data/knowledge.json`](./data/knowledge.json), making it easy to add or edit facts about people, teams, and projects.

---

## Directory Structure

```text
rag_knowledge/
├── __init__.py                # Package exports (query_rag, KnowledgeRetriever, MistralRAGClient, RAGService)
├── __main__.py                # Package entrypoint (python -m rag_knowledge)
├── cli.py                     # Command-line query tool & inspector
├── mistral_client.py          # Mistral API synthesis client with standard urllib
├── retriever.py               # In-memory keyword, alias & token scoring retriever
├── service.py                 # RAG orchestrator coordinating retrieval & generation
├── requirements.txt           # Package requirements
├── README.md                  # Main documentation
├── data/
│   └── knowledge.json         # Hardcoded knowledge documents (editable)
├── docs/
│   ├── architecture.md        # Technical architecture & scoring details
│   └── integration_guide.md   # Guide on integrating into any system / voice agent
└── tests/
    ├── __init__.py
    ├── test_retriever.py      # Unit tests for tokenization and retrieval
    ├── test_mistral_client.py # Unit tests for Mistral API client and fallbacks
    └── test_service.py        # Unit tests for RAG service coordination
```

---

## Quick Start

### 1. Standalone CLI Usage

Query the knowledge base directly from your terminal:

```bash
# Ask a question
python -m rag_knowledge "Do you know about Raj Ojha?"

# List all stored knowledge documents
python -m rag_knowledge --list

# Query with retrieval match scores
python -m rag_knowledge "Who is Raj Ojha?" -v
```

### 2. Python API Usage

Import into any Python application:

```python
import asyncio
from rag_knowledge import query_rag

async def main():
    # Asynchronously query the RAG service
    answer = await query_rag("Who is Raj Ojha?")
    print("Answer:", answer)

asyncio.run(main())
```

---

## Configuration & Environment Variables

Add these to your `.env` file or environment (all are optional):

| Variable | Default | Description |
| :--- | :--- | :--- |
| `MISTRAL_API_KEY` | *(None)* | Your Mistral AI API key. If unset, fallback mode returns raw structured facts. |
| `MISTRAL_MODEL` | `mistral-small-latest` | Mistral model identifier to use for response synthesis. |

---

## Adding or Modifying Knowledge

Edit [`rag_knowledge/data/knowledge.json`](./data/knowledge.json). Each entry follows this simple format:

```json
[
  {
    "id": "person_or_topic_id",
    "title": "Full Name / Title",
    "keywords": ["keyword1", "keyword2", "alias"],
    "summary": "Short one-sentence summary.",
    "content": "Detailed facts and background information to be used as context."
  }
]
```

Changes take effect immediately on next query.

---

## Running Tests

The test suite is fully isolated under `rag_knowledge/tests/`:

```bash
python -m pytest rag_knowledge/tests/ -v
```
