# RAG Knowledge Subsystem (`rag_knowledge`)

A modular, database-backed, self-contained Retrieval-Augmented Generation (RAG) package. Designed to provide fast factual knowledge retrieval and Google Gemini synthesis for conversational agents, voice assistants, and multi-agent platforms.

---

## Highlights

- **Completely Self-Contained**: Can be run, tested, and imported independently or merged with other systems without impacting other directories.
- **Database-Backed RAG Storage**: Powered by MongoDB (`riva_knowledge.knowledge_documents`) with weighted full-text search and alias matching.
- **Dynamic Live Updates**: Add, modify, or delete knowledge documents directly in MongoDB without server restarts or redeployments.
- **Auto `.env` Discovery**: Automatically detects and loads `.env` from package or workspace roots on import.
- **Google Gemini Synthesis**: Uses Gemini Flash (`gemini-flash-lite-latest` by default) via standard Python `urllib` with strict grounding prompts to generate concise, 2–3 sentence spoken answers.
- **Resilient Fallback**: If `GEMINI_API_KEY` is omitted, rate-limited, or unavailable, it immediately returns the factual grounded text directly so conversational pipelines never fail.

---

## Directory Structure

```text
rag_knowledge/
├── __init__.py                # Package exports (query_rag, KnowledgeRetriever, GeminiRAGClient, RAGService)
├── __main__.py                # Package entrypoint (python -m rag_knowledge)
├── cli.py                     # Command-line query tool & inspector
├── gemini_client.py           # Gemini API synthesis client with standard urllib
├── retriever.py               # Database-backed search retriever over MongoDB
├── service.py                 # RAG orchestrator coordinating retrieval & generation
├── storage/                   # Database storage layer
│   ├── __init__.py
│   └── mongo.py               # MongoDB connection pooling & full-text indexing
├── requirements.txt           # Package requirements
├── README.md                  # Main documentation
├── docs/
│   ├── architecture.md        # Technical architecture details
│   └── integration_guide.md   # Guide on integrating into any system / voice agent
└── tests/
    ├── __init__.py
    ├── conftest.py            # Hermetic test isolation fixtures
    ├── test_retriever.py      # Unit tests for retriever
    ├── test_mongo_storage.py  # Unit tests for MongoDB storage layer
    ├── test_gemini_client.py  # Unit tests for Gemini API client and fallbacks
    └── test_service.py        # Unit tests for RAG service coordination
```

---

## Quick Start

### 1. Standalone CLI Usage

Query the knowledge base directly from your terminal:

```bash
# Ask a question
python -m rag_knowledge "Do you know about Alex Doe?"

# List all stored knowledge documents
python -m rag_knowledge --list

# Query with retrieval match scores
python -m rag_knowledge "Who is Alex Doe?" -v
```
  
### 2. Python API Usage

Import into any Python application:

```python
import asyncio
from rag_knowledge import query_rag

async def main():
    # Asynchronously query the RAG service
    answer = await query_rag("Who is Alex Doe?")
    print("Answer:", answer)

asyncio.run(main())
```

---

## Configuration & Environment Variables

Add these to your `.env` file or environment:

| Variable | Required | Default | Description |
| :--- | :--- | :--- | :--- |
| `MONGODB_URI` | Yes (for DB) | *(None)* | MongoDB Atlas or local connection string (`mongodb+srv://...`). |
| `MONGODB_DB_NAME` | No | `riva_knowledge` | Target database name. |
| `MONGODB_COLLECTION` | No | `knowledge_documents` | Target collection name. |
| `MONGODB_TIMEOUT_MS` | No | `5000` | Connection and socket timeout in milliseconds. |
| `MONGODB_DNS_SERVERS` | No | `8.8.8.8,1.1.1.1,8.8.4.4` | Fallback public DNS servers for `mongodb+srv://` SRV resolution. |
| `MONGODB_DNS_FALLBACK` | No | `1` | Set to `0` to disable the DNS fallback override. |
| `MONGODB_DISABLE_DNS_OVERRIDE` | No | `0` | Set to `1` to disable the DNS fallback override. |
| `GEMINI_API_KEY` | No (has fallback) | *(None)* | Google AI Studio API key. Sent securely in `x-goog-api-key` header. If unset, returns raw structured facts. |
| `GEMINI_RAG_MODEL` | No | *(None)* | Specific Gemini model for RAG synthesis. Takes precedence over `GEMINI_MODEL`. |
| `GEMINI_MODEL` | No | `gemini-flash-lite-latest` | Model ID for RAG response synthesis (`gemini-flash-lite-latest`, `gemini-3-flash-preview`). |
| `GEMINI_TIMEOUT` | No | `4.0` | API request timeout in seconds (optimized for voice latency). |
| `RAG_LOAD_CWD_ENV` | No | `false` | Set to `true` to allow auto-loading `.env` from the current working directory. |

---

## Adding or Modifying Knowledge

Documents are stored in MongoDB collection `knowledge_documents`. Each document follows this format:

```json
{
  "_id": "person_or_topic_id",
  "id": "person_or_topic_id",
  "title": "Full Name / Title",
  "aliases": ["alias 1", "alias 2"],
  "keywords": ["keyword1", "keyword2"],
  "summary": "Short one-sentence summary.",
  "content": "Detailed facts and background information to be used as context.",
  "is_active": true
}
```

New or modified documents in MongoDB are immediately queryable without restarting applications.

---

## Running Tests

The test suite is fully isolated under `rag_knowledge/tests/`:

```bash
python -m pytest rag_knowledge/tests/ -v
```
