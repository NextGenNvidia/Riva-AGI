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
  |  KnowledgeRetriever   |             |    GeminiRAGClient    |
  |  (retriever.py)       |             |  (gemini_client.py)   |
  +-----------+-----------+             +-----------+-----------+
              |                                     |
              v                                     v
  +-----------------------+             +-----------------------+
  |  MongoDB Database     |             |  Google Gemini API    |
  | (knowledge_documents) |             | (generativelanguage)  |
  +-----------------------+             +-----------------------+
```

## Components

### 1. `KnowledgeRetriever` (`retriever.py`)
- Database-backed search engine querying MongoDB collection `knowledge_documents`.
- Weighted full-text search indexing on `aliases` (10x), `title` (8x), `keywords` (5x), `summary` (3x), and `content` (1x).
- Low-latency token & regex alias lookup fallback with word boundaries and stopwords filtering.
- Returns top-k matching documents ranked by relevance score.

### 2. `GeminiRAGClient` (`gemini_client.py`)
- Communicates directly with Google Generative Language REST API (`models/{model}:generateContent`).
- Uses standard library `urllib.request` inside an async worker executor to ensure zero event loop blocking and zero third-party dependencies.
- Injects a voice-tuned prompt directing Gemini to answer within 2–3 spoken sentences strictly grounded in retrieved facts.
- Fail-safe: if request fails or key is missing, returns `None` so the caller gracefully falls back.

### 3. `RAGService` (`service.py`)
- Coordinates the retrieval and generation workflow.
- Falls back gracefully to raw document content if Gemini is unconfigured or encounters an error.
