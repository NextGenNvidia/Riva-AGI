# RAG Knowledge Architecture

This document describes the internal design of the `rag_knowledge` subsystem.

```
                    +-----------------------+
                    |      User Query       |
                    +-----------+-----------+
                                |
                                v
                    +-----------------------+
                    |    RAGService         |
                    | (service.py)          |
                    +-----------+-----------+
                                |
             +------------------+------------------+
             |                                     |
             v                                     v
  +-----------------------+             +-----------------------+
  |  KnowledgeRetriever   |             |   MistralRAGClient    |
  |  (retriever.py)       |             |  (mistral_client.py)  |
  +-----------+-----------+             +-----------+-----------+
              |                                     |
              v                                     v
  +-----------------------+             +-----------------------+
  |   knowledge.json      |             |   Mistral Chat API    |
  | (data/knowledge.json) |             | (api.mistral.ai)      |
  +-----------------------+             +-----------------------+
```

## Components

### 1. `KnowledgeRetriever` (`retriever.py`)
- Loads documents from JSON storage on startup.
- Multi-tier scoring:
  - **Exact Keyword Match (+10.0)**: Matches full query against configured keyword aliases.
  - **Keyword Token Match (+4.0)**: Matches individual user query tokens against keyword terms.
  - **Title Token Match (+3.0)**: Matches tokens against the document title.
  - **Content Token Match (+0.5)**: Matches tokens against body text.
- Returns top-k matching documents ranked by score.

### 2. `MistralRAGClient` (`mistral_client.py`)
- Communicates directly with `https://api.mistral.ai/v1/chat/completions`.
- Uses standard library `urllib.request` inside an async worker executor to ensure zero event loop blocking.
- Injects a voice-tuned prompt directing Mistral to answer within 2–3 spoken sentences.
- Fail-safe: if request fails or key is missing, returns `None` so the caller gracefully falls back.

### 3. `RAGService` (`service.py`)
- Coordinates the retrieval and generation workflow.
- Falls back gracefully to raw document content if Mistral is unconfigured or encounters an error.
