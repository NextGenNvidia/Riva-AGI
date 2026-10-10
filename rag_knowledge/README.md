# RAG Knowledge Subsystem (`rag_knowledge`)

Voice-optimized Retrieval-Augmented Generation (RAG) service powered by **Qdrant Vector Database** and **Google Gemini**.

---

## 1. Setup

Copy `.env.example` to `.env` in the root or package directory:

```bash
cp rag_knowledge/.env.example rag_knowledge/.env
```

Configure your environment variables in `.env`:

```ini
# Google Gemini (Separate keys prevent token/quota exhaustion)
GEMINI_API_KEY=your_gemini_api_key_here
GEMINI_VISION_API_KEY=your_gemini_vision_api_key_here  # Optional: dedicated key for vision OCR
GEMINI_TEXT_API_KEY=your_gemini_text_api_key_here      # Optional: dedicated key for answer synthesis

# Qdrant Vector Database
QDRANT_URL=https://your-cluster-id.us-east-1-1.aws.cloud.qdrant.io
QDRANT_API_KEY=your_qdrant_api_key_here
QDRANT_COLLECTION=riva_knowledge
QDRANT_TIMEOUT=60.0                                    # WAN connection timeout (seconds)
QDRANT_BATCH_SIZE=50                                   # Upsert chunk size

# Security & Data Integrity
RAG_ENTITY_SECRET=your_hmac_secret_salt_here           # Salt for hashing student IDs
LIVE_COLLECTION=riva_knowledge_prod                    # Safeguard: prevents accidental --clear on production

# Image OCR & Multimodal Vision
ALLOW_CLOUD_VISION=true                                # Opt-in to Gemini Cloud Vision OCR (or pass --cloud-vision)
# ALLOW_CLOUD_VISION_ALLOWLIST=raw/scans,diagrams      # Optional: whitelist specific paths for cloud vision
```

Install requirements:
```bash
pip install -r rag_knowledge/requirements.txt
```

---

## 2. Ingestion (Data Processing & Indexing)

Ingest raw files or entire directories into the vector database using `rag_knowledge.ingestion`:

```bash
# Ingest with automated PII redaction (recommended for student records)
python -m rag_knowledge.ingestion --source "rag_knowledge/data/raw/" --redact

# Dry run: parse and inspect documents without uploading to Qdrant
python -m rag_knowledge.ingestion --source "rag_knowledge/data/raw/" --dry-run

# Opt-in to Google Gemini Cloud Vision for OCR on complex diagrams/scans
python -m rag_knowledge.ingestion --source "rag_knowledge/data/raw/" --cloud-vision --redact

# Clear target collection (requires confirmation or --yes / -y)
python -m rag_knowledge.ingestion --clear --yes
```

### CLI Ingestion Options

| Flag | Description |
| :--- | :--- |
| `--source <path>` | Path to a single file or directory of documents to ingest |
| `--redact` | Automatically redacts detected emails and phone numbers (PRD S4 privacy gate) |
| `--cloud-vision` | Opt-in to Gemini Cloud Vision for images (or set `ALLOW_CLOUD_VISION=true` in `.env`) |
| `--batch-size <N>` | Points per upsert batch (default: `50`, with automatic sub-chunking on WAN timeout) |
| `--limit <N>` | Ingest only the first `N` extracted documents |
| `--dry-run` | Extract, chunk, and preview documents without modifying vector storage |
| `--clear`, `--delete-all` | Empties the target collection in Qdrant (blocked if matching `LIVE_COLLECTION`) |
| `--yes`, `-y` | Skips interactive confirmation prompt for `--clear` |

### Supported Data Formats

- **Spreadsheets (`.xlsx`, `.xls`, `.csv`, `.tsv`)**: Merges student master sheets and category rosters with opaque hash joins.
- **Documents (`.pdf`, `.docx`, `.txt`, `.md`, `.json`)**: Extracts text sections, headings, tables, and lists.
- **Images (`.png`, `.jpg`, `.jpeg`, `.webp`)**: Local Tesseract OCR (if installed in system PATH) or multimodal Gemini Cloud Vision (enabled via `--cloud-vision` CLI flag or `ALLOW_CLOUD_VISION=true` in `.env`).

---

## 3. Querying

### Terminal CLI
```bash
# Query with ranked retrieval matches displayed
python -m rag_knowledge "Tell me about Astitva Gupta"

# Query in quiet mode (returns answer only)
python -m rag_knowledge "What is the policy for hackathon registration?" -q

# List indexed documents
python -m rag_knowledge --list
```

### Python API
```python
import asyncio
from rag_knowledge import query_rag

async def main():
    response = await query_rag("Who won the first year coding competition?")
    print(response)

asyncio.run(main())
```

---

## 4. Security & Architecture Highlights

- **Privacy Gate & Entity Joiner**: PII such as contact details (emails, phone numbers) are stripped or hashed via `RAG_ENTITY_SECRET`. Direct unredacted ingestion is blocked by default unless `--redact` is passed.
- **Quota Separation**: Separate API keys for Vision and Text synthesis avoid starving conversational tokens during large document ingestions.
- **WAN Resilience**: Adaptive upsert retry logic with automated half-batch sub-chunking prevents socket timeouts against cloud vector instances.
- **Production Safeguards**: Destructive actions like `--clear` are blocked when pointing at `LIVE_COLLECTION`.

---

## 5. Running Tests

Run the full test suite with pytest:

```bash
pytest rag_knowledge/tests
```
