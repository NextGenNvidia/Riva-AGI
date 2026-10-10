# Integration Guide: Merging `rag_knowledge` into Other Systems

Because `rag_knowledge` is designed as a standalone, self-contained Python package, integrating or merging it into another repository or service takes only a few lines of code.

---

## 1. How to Import

Copy or symlink the `rag_knowledge/` folder into your target project root.

```python
from rag_knowledge import query_rag, KnowledgeRetriever, GeminiRAGClient, RAGService

# Simple one-liner query:
answer = await query_rag("Who is Alex Doe?")
```

---

## 2. Integrating into LLM Function Calling (e.g. Gemini Live, OpenAI, Anthropic)

### OpenAI Function Calling / Tools Schema:
```python
RAG_TOOL_SCHEMA = {
    "type": "function",
    "function": {
        "name": "query_knowledge_base",
        "description": "Query internal knowledge base for facts about people (e.g. Alex Doe) and club projects.",
        "parameters": {
            "type": "object",
            "properties": {
                "query": {"type": "string", "description": "The search query or entity name"}
            },
            "required": ["query"],
        }
    }
}

async def handle_tool_call(name: str, args: dict) -> str:
    if name == "query_knowledge_base":
        return await query_rag(args.get("query", ""))
```

### Google Gemini Live Tool Definition:
```python
from google.genai import types
from rag_knowledge.service import query_rag

KNOWLEDGE_TOOL = types.FunctionDeclaration(
    name="query_knowledge_base",
    description="Query internal RAG facts about team members and projects.",
    parameters=types.Schema(
        type="OBJECT",
        properties={"query": types.Schema(type="STRING", description="Search query")},
        required=["query"],
    ),
)
```

---

## 3. Integrating with FastAPI / REST Endpoints

```python
from fastapi import FastAPI, Query
from rag_knowledge import query_rag

app = FastAPI()

@app.get("/api/rag")
async def rag_endpoint(q: str = Query(..., description="Query string")):
    answer = await query_rag(q)
    return {"query": q, "answer": answer}
```

---

## 4. Extending Storage Backends to Vector DBs in Future

When your knowledge base requires embedding-based semantic vector search, simply subclass or extend `KnowledgeRetriever` in `rag_knowledge/retriever.py` with your vector store (ChromaDB, Pinecone, FAISS, etc.) without altering the public `query_rag` interface.
