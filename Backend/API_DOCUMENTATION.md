# Riva-AGI Backend API & Route Reference Manual

This document provides a single, complete reference for all routes, endpoints, protocols, inputs, outputs, and handlers in the **Riva-AGI** central backend server (`http://localhost:8000`).

---

## 1. Master Route Directory Table Chart

| # | Route (Method & Path) | Handler Function & Subsystem | Purpose & Why It Exists | What It Needs As Input & How | What It Outputs & How |
| :---: | :--- | :--- | :--- | :--- | :--- |
| **1** | `GET /api` | `api_info`<br>*(Backend/main.py)* | **Service Discovery & Catalog Root**<br>Provides runtime discovery, operational state, version, and a catalog of all primary routes for frontend apps. | **None**<br>Standard HTTP GET request. | **HTTP 200 OK (`application/json`)**<br>`{"service": str, "status": str, "version": str, "endpoints": dict}` |
| **2** | `GET /` | `get_index`<br>*(Backend/routers/web.py)* | **Voice Interface Web Application**<br>Serves the primary Single-Page Application (SPA) HTML for the real-time browser voice cockpit. | **None**<br>Standard HTTP GET request. | **HTTP 200 OK (`text/html`)**<br>Serves `voice_speech/web/index.html` (or fallback message if file missing). |
| **3** | `GET /app.js` | `get_app_js`<br>*(Backend/routers/web.py)* | **Client Voice Interface Logic**<br>Serves the JavaScript controlling Web Audio, Three.js 3D visualizer, microphone lifecycle, and WebSocket communication. | **None**<br>Standard HTTP GET request. | **HTTP 200 OK (`application/javascript`)**<br>Serves `voice_speech/web/app.js`. |
| **4** | `GET /worklet.js` | `get_worklet_js`<br>*(Backend/routers/web.py)* | **AudioWorklet Processor Script**<br>Serves the browser AudioWorklet processor that downsamples browser microphone input into 16kHz PCM16 audio buffers. | **None**<br>Standard HTTP GET request. | **HTTP 200 OK (`application/javascript`)**<br>Serves `voice_speech/web/worklet.js`. |
| **5** | `GET /favicon.ico` | `get_favicon`<br>*(Backend/routers/web.py)* | **Browser Tab Icon**<br>Serves application brand favicon to eliminate 404 browser noise. | **None**<br>Standard HTTP GET request. | **HTTP 200 OK (`image/svg+xml`)**<br>SVG icon payload. |
| **6** | `WS /ws` | `audio_websocket_endpoint`<br>*(Backend/routers/voice.py)* | **Real-Time Voice Streaming Gateway**<br>Full-duplex bidirectional audio bridge connecting browser Web Audio to Google Gemini Live API. | **WebSocket Connection**<br>- **Header**: `Origin` *(must match allowed origins)*<br>- **Query Params**: `?voice=Aoede&language=auto`<br>- **Inbound Frames**: Binary PCM16 audio buffers from microphone. | **Bidirectional WebSocket Stream**<br>- **Outbound Frames**: Raw PCM16 audio binary chunks from Gemini Live.<br>- **JSON Control Events**: `{"type": "error", "message": "..."}` on errors, rate limits (4029), or unauthorized origins (4003). |
| **7** | `GET /api/voice/status` | `get_voice_status`<br>*(Backend/routers/voice.py)* | **Voice Gateway Health & Metrics**<br>Monitors active voice sessions, capacity limits, circuit breaker cooldown, and configured model info. | **None**<br>Standard HTTP GET request. | **HTTP 200 OK (`application/json`)**<br>`VoiceStatusResponse` with `status`, `active_sessions`, `max_concurrent_sessions`, `circuit_breaker_open`, `circuit_cooldown_remaining_sec`, `model`, `default_voice`. |
| **8** | `POST /api/chat` | `chat_endpoint`<br>*(Backend/routers/chat.py)* | **Synchronous Multi-Agent Task Execution**<br>Receives a user task, optionally pre-fetches RAG knowledge, executes the multi-agent hierarchy (Intent &rarr; DAG Planner &rarr; Executor &rarr; Agents &rarr; Reviewer), and persists session turns. | **JSON Body (`application/json`)**<br>`ChatRequest`: <br>- `message` *(str, required)*<br>- `session_id` *(str, optional)*<br>- `use_rag` *(bool, optional, default: true)* | **HTTP 200 OK (`application/json`)**<br>`ChatResponse`: <br>- `task_id` *(str)*<br>- `agent_used` *(str)*<br>- `intent` *(str)*<br>- `content` *(str)*<br>- `status` *(str)*<br>- `execution_time_ms` *(float)*<br>- `tool_calls` *(list)*<br>- `session_id` *(str)*<br><br>**HTTP 422 Unprocessable Entity** if body invalid. |
| **9** | `WS /api/chat/stream` | `chat_stream_endpoint`<br>*(Backend/routers/chat.py)* | **Real-Time Token Streaming Gateway**<br>Streams multi-agent thinking status, RAG progress, and generated text token-by-token for interactive chat UIs. | **Inbound WebSocket JSON Frame**<br>`{"message": "prompt", "session_id": "optional", "use_rag": true}` | **Outbound WebSocket JSON Event Sequence**<br>1. `{"type": "start", "session_id": "...", "message": "..."}`<br>2. `{"type": "status", "data": "Searching knowledge base..."}`<br>3. `{"type": "status", "data": "Orchestrating agents..."}`<br>4. `{"type": "token", "data": "<chunk>"}` *(word-by-word)*<br>5. `{"type": "done", "data": <ChatResponse>}`<br>6. `{"type": "error", "message": "..."}` *(if failed)* |
| **10** | `GET /api/agents/list` | `list_agents`<br>*(Backend/routers/agents.py)* | **Agent Capability Registry**<br>Returns all autonomous registered agents in the platform (`coder`, `researcher`, etc.), descriptions, tools, and hierarchical levels. | **None**<br>Standard HTTP GET request. | **HTTP 200 OK (`application/json`)**<br>`AgentsListResponse`:<br>`{"agents": [{"name": str, "description": str, "tools": list[str], "level": "CEO"|"MANAGER"|"TASK_DOER"}]}` |
| **11** | `GET /api/tasks/{task_id}` | `get_task_status`<br>*(Backend/routers/tasks.py)* | **Task State & History Tracking**<br>Polls execution status, currently active agent owner, and transition step history for asynchronous and background tasks. | **Path Parameter**<br>- `task_id` *(str, in URL path)*<br>Example: `/api/tasks/task-a1b2c3d4` | **HTTP 200 OK (`application/json`)**<br>`TaskStatusResponse`:<br>`{"task_id": str, "status": "in_progress"|"processing"|"completed"|"failed", "current_step": int, "owner": str, "data": dict, "history": list}`<br><br>**HTTP 404 Not Found** if `task_id` is unknown:<br>`{"detail": "Task '...' not found."}` |
| **12** | `GET /api/system/health` | `health_check`<br>*(Backend/routers/system.py)* | **System Health & Uptime Probe**<br>Checks global health and connectivity for orchestrator, RAG retriever, MongoDB, and Gemini voice service. | **None**<br>Standard HTTP GET request. | **HTTP 200 OK (`application/json`)**<br>`HealthResponse`:<br>`{"status": "ok", "services": {"orchestrator": "ready", "rag": "ready"|"connected", "mongodb": "connected"|"disconnected", "voice": "ready"|"degraded"}, "timestamp": "ISO-UTC"}` |
| **13** | `GET /api/system/metrics` | `system_metrics`<br>*(Backend/routers/system.py)* | **Hardware Telemetry Diagnostics**<br>Collects real-time CPU, RAM, Battery, and GPU metrics for performance dashboards and host telemetry. | **None**<br>Standard HTTP GET request. | **HTTP 200 OK (`application/json`)**<br>`MetricsResponse`:<br>`{"cpu": {"percent": float, "cores_logical": int, ...}, "memory": {"percent": float, "used_gb": float, ...}, "battery": {"percent": float, "power_plugged": bool, ...}, "gpu": [...]}` |
| **14** | `POST /api/rag/query` | `query_knowledge_base`<br>*(Backend/routers/rag.py)* | **Direct Knowledge Retrieval & Synthesis**<br>Searches the RAG knowledge vector store directly and returns synthesized answers with citations without invoking full agent orchestration. | **JSON Body (`application/json`)**<br>`RAGQueryRequest`: <br>- `query` *(str, required)*<br>- `top_k` *(int, optional, default: 2)* | **HTTP 200 OK (`application/json`)**<br>`RAGQueryResponse`:<br>`{"answer": str, "sources": [{"title": str, "score": float, "summary": str|null}]}`<br><br>**HTTP 422 Unprocessable Entity** if body invalid. |

---

## 2. Detailed Subsystem Specifications & Schemas

### Subsystem 1: Discovery

#### `GET /api`
- **Purpose**: Root service status discovery and route catalog.
- **Input**: None.
- **Output Sample (HTTP 200)**:
```json
{
  "service": "Riva-AGI Central Backend",
  "status": "running",
  "version": "1.0.0",
  "endpoints": {
    "web_ui": "GET /",
    "voice_gateway": "WS /ws",
    "voice_status": "GET /api/voice/status",
    "chat_rest": "POST /api/chat",
    "chat_stream": "WS /api/chat/stream",
    "agents_list": "GET /api/agents/list",
    "tasks_status": "GET /api/tasks/{task_id}",
    "system_health": "GET /api/system/health",
    "system_metrics": "GET /api/system/metrics",
    "rag_query": "POST /api/rag/query"
  }
}
```

---

### Subsystem 2: Voice & Speech Gateway

#### `WS /ws`
- **Purpose**: Low-latency bidirectional audio link between browser microphone/speakers and Google Gemini Live.
- **Connection Handshake**:
  - `ws://localhost:8000/ws?voice=Aoede&language=auto`
  - Validates `Origin` header against `config.allowed_ws_origins`.
  - Checks if `GEMINI_API_KEY` is configured (closes with code `4001` if missing).
  - Checks session quota via `SessionManager.try_acquire()` (closes with code `4029` if full).
- **Audio Format**:
  - Inbound: 16-bit Linear PCM, 16000Hz / 24000Hz, Little Endian, Mono.
  - Outbound: 16-bit Linear PCM, 24000Hz, Little Endian, Mono.

#### `GET /api/voice/status`
- **Purpose**: Voice subsystem telemetry and circuit breaker state.
- **Output Sample (HTTP 200)**:
```json
{
  "status": "ready",
  "active_sessions": 0,
  "max_concurrent_sessions": 5,
  "circuit_breaker_open": false,
  "circuit_cooldown_remaining_sec": 0.0,
  "model": "gemini-3.1-flash-live-preview",
  "default_voice": "Aoede"
}
```

---

### Subsystem 3: Chat & Multi-Agent Orchestration

#### `POST /api/chat`
- **Purpose**: Synchronous task execution across the multi-agent pipeline.
- **Input Sample (`application/json`)**:
```json
{
  "message": "Write a python function to compute Fibonacci numbers efficiently.",
  "session_id": "sess-user-001",
  "use_rag": true
}
```
- **Output Sample (HTTP 200)**:
```json
{
  "task_id": "task-7b8f9a0c",
  "agent_used": "coder",
  "intent": "code_generation",
  "content": "def fib(n: int) -> int:\n    a, b = 0, 1\n    for _ in range(n):\n        a, b = b, a + b\n    return a",
  "status": "success",
  "execution_time_ms": 1420.5,
  "tool_calls": [
    {
      "tool": "file_writer",
      "args": {"path": "fib.py"}
    }
  ],
  "session_id": "sess-user-001"
}
```

#### `WS /api/chat/stream`
- **Purpose**: Word-by-word streaming for real-time chat frontends.
- **Client Inbound Message**:
```json
{
  "message": "Explain quantum computing in simple terms.",
  "session_id": "stream-sess-99",
  "use_rag": true
}
```
- **Server Stream Sequence**:
```json
{"type": "start", "session_id": "stream-sess-99", "message": "Explain quantum computing in simple terms."}
{"type": "status", "data": "Searching knowledge base..."}
{"type": "status", "data": "Orchestrating agents..."}
{"type": "token", "data": "Quantum "}
{"type": "token", "data": "computing "}
{"type": "token", "data": "uses "}
{"type": "token", "data": "qubits..."}
{"type": "done", "data": {"task_id": "...", "content": "Quantum computing uses qubits...", "status": "success"}}
```

---

### Subsystem 4: Agent Registry & Tasks

#### `GET /api/agents/list`
- **Purpose**: Returns the list of registered agents, tools, and hierarchy.
- **Output Sample (HTTP 200)**:
```json
{
  "agents": [
    {
      "name": "coder",
      "description": "Specialized in software development, syntax generation, refactoring, and code review.",
      "tools": ["execute_command", "read_file", "write_file", "search_files"],
      "level": "TASK_DOER"
    },
    {
      "name": "researcher",
      "description": "Specialized in internet discovery, web fetching, and research synthesis.",
      "tools": ["duckduckgo_search", "fetch_web_page", "wikipedia_summary"],
      "level": "TASK_DOER"
    }
  ]
}
```

#### `GET /api/tasks/{task_id}`
- **Purpose**: Polls execution state and transition history for a task.
- **Output Sample (HTTP 200)**:
```json
{
  "task_id": "task-7b8f9a0c",
  "status": "completed",
  "current_step": 3,
  "owner": "coder",
  "data": {
    "query": "Write a python function"
  },
  "history": [
    {"step": 1, "owner": "orchestrator", "status": "in_progress"},
    {"step": 2, "owner": "planner", "status": "processing"},
    {"step": 3, "owner": "coder", "status": "completed"}
  ]
}
```
- **Error Output (HTTP 404)**:
```json
{
  "detail": "Task 'non-existent-task' not found."
}
```

---

### Subsystem 5: System Telemetry & RAG Knowledge

#### `GET /api/system/health`
- **Purpose**: Probes overall system health and subsystem availability.
- **Output Sample (HTTP 200)**:
```json
{
  "status": "ok",
  "services": {
    "orchestrator": "ready",
    "rag": "ready",
    "mongodb": "disconnected",
    "voice": "ready"
  },
  "timestamp": "2026-10-10T13:30:00.000000+00:00"
}
```

#### `GET /api/system/metrics`
- **Purpose**: Hardware metrics diagnostics.
- **Output Sample (HTTP 200)**:
```json
{
  "cpu": {
    "percent": 14.2,
    "cores_logical": 16,
    "cores_physical": 8,
    "freq_mhz": 3400.0
  },
  "memory": {
    "total_gb": 31.85,
    "used_gb": 12.45,
    "available_gb": 19.40,
    "percent": 39.1
  },
  "battery": {
    "percent": 100.0,
    "power_plugged": true,
    "secsleft": null
  },
  "gpu": []
}
```

#### `POST /api/rag/query`
- **Purpose**: Direct knowledge store query without multi-agent execution.
- **Input Sample (`application/json`)**:
```json
{
  "query": "How is memory isolation implemented in Riva-AGI?",
  "top_k": 2
}
```
- **Output Sample (HTTP 200)**:
```json
{
  "answer": "Memory isolation in Riva-AGI is managed through dedicated WhiteboardContext sessions and isolated worker threads...",
  "sources": [
    {
      "title": "Architecture Overview - Riva AGI",
      "score": 0.89,
      "summary": "Describes session isolation, thread-safe task queues, and context bounds."
    }
  ]
}
```
