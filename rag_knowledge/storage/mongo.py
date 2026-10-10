"""MongoDB Storage & Retrieval Backend for rag_knowledge.

Provides resilient connection pooling, text search indexing, and document
upserting with graceful timeout handling and certifi TLS integration.
"""

import logging
import os
import re
import threading
import time
from typing import Any, Dict, List, Optional, Tuple

logger = logging.getLogger("rag_knowledge.storage.mongo")

# Optional dependencies
try:
    import certifi
    _HAS_CERTIFI = True
except ImportError:
    _HAS_CERTIFI = False

try:
    import pymongo
    from pymongo import MongoClient
    from pymongo.errors import OperationFailure
    _HAS_PYMONGO = True
except ImportError:
    _HAS_PYMONGO = False


def _ensure_dns_resolvers() -> None:
    """Configures dnspython default resolver with reliable public fallbacks.
    
    Prevents SRV resolution timeouts on institutional / campus networks (e.g. KIET)
    where internal DNS drops or throttles DNS SRV queries on port 53.
    Can be configured via MONGODB_DNS_SERVERS or disabled via MONGODB_DISABLE_DNS_OVERRIDE=1.
    """
    if os.getenv("MONGODB_DISABLE_DNS_OVERRIDE", "").lower() in ("1", "true", "yes") or \
       os.getenv("MONGODB_DNS_FALLBACK", "").lower() in ("0", "false", "no"):
        logger.debug("MongoDB DNS override is explicitly disabled.")
        return

    try:
        import dns.resolver
        resolver = dns.resolver.get_default_resolver()
        raw_servers = os.getenv("MONGODB_DNS_SERVERS", "8.8.8.8,1.1.1.1,8.8.4.4").strip()
        public_servers = [s.strip() for s in raw_servers.split(",") if s.strip()]
        for srv in reversed(public_servers):
            if srv in resolver.nameservers:
                resolver.nameservers.remove(srv)
            resolver.nameservers.insert(0, srv)
        resolver.lifetime = max(float(getattr(resolver, "lifetime", 5.0)), 10.0)
    except Exception as e:
        logger.debug("DNS resolver configuration skipped: %s", e)


class MongoKnowledgeStore:
    """Manages MongoDB connection, full-text search, and document storage for RAG."""

    def __init__(
        self,
        uri: Optional[str] = None,
        db_name: Optional[str] = None,
        collection_name: Optional[str] = None,
        timeout_ms: Optional[int] = None,
    ) -> None:
        self.uri = uri if uri is not None else os.getenv("MONGODB_URI", "").strip()
        self.db_name = db_name or os.getenv("MONGODB_DB_NAME", "riva_knowledge").strip() or "riva_knowledge"
        self.collection_name = collection_name or os.getenv("MONGODB_COLLECTION", "knowledge_documents").strip() or "knowledge_documents"
        
        env_timeout = os.getenv("MONGODB_TIMEOUT_MS", "5000").strip()
        default_timeout = int(env_timeout) if env_timeout.isdigit() else 5000
        self.timeout_ms = timeout_ms if timeout_ms is not None else default_timeout

        self._client: Optional[Any] = None
        self._db: Optional[Any] = None
        self._collection: Optional[Any] = None
        self._is_connected: Optional[bool] = None
        self._closed: bool = False
        self._last_fail_time: float = 0.0
        self._fail_cooldown_seconds: float = 60.0
        self._lock = threading.Lock()

    def connect(self) -> bool:
        """Attempts to initialize client and verify server connectivity."""
        with self._lock:
            if self._closed:
                return False

            if not _HAS_PYMONGO:
                logger.debug("pymongo is not installed; MongoDB storage is unavailable.")
                self._is_connected = False
                return False

            if not self.uri:
                logger.debug("MONGODB_URI is not set; skipping MongoDB storage initialization.")
                self._is_connected = False
                return False

            # If connection failed recently, avoid blocking in cooldown window
            if self._is_connected is False and (time.time() - self._last_fail_time < self._fail_cooldown_seconds):
                return False

            try:
                client_kwargs: Dict[str, Any] = {
                    "serverSelectionTimeoutMS": self.timeout_ms,
                    "connectTimeoutMS": self.timeout_ms,
                    "socketTimeoutMS": self.timeout_ms,
                }
                is_tls = "mongodb+srv://" in self.uri.lower() or "tls=true" in self.uri.lower() or "ssl=true" in self.uri.lower()
                is_srv = "mongodb+srv://" in self.uri.lower()
                if _HAS_CERTIFI and is_tls:
                    client_kwargs["tlsCAFile"] = certifi.where()

                try:
                    self._client = MongoClient(self.uri, **client_kwargs)
                    self._client.admin.command("ping")
                except Exception as initial_err:
                    err_text = str(initial_err).lower()
                    # Apply DNS fallback resolver only on SRV resolution errors
                    if is_srv and ("srv" in err_text or "dns" in err_text or "configurationerror" in type(initial_err).__name__.lower()):
                        logger.warning("SRV resolution failed (%s). Applying DNS fallback resolvers and retrying...", initial_err)
                        _ensure_dns_resolvers()
                        if self._client:
                            try:
                                self._client.close()
                            except Exception:
                                pass
                        self._client = MongoClient(self.uri, **client_kwargs)
                        self._client.admin.command("ping")
                    else:
                        raise

                self._db = self._client[self.db_name]
                self._collection = self._db[self.collection_name]
                self._is_connected = True
                logger.info("Connected to MongoDB successfully (db: %s, col: %s)", self.db_name, self.collection_name)
                # Auto-ensure indexes on successful connection
                self.ensure_indexes()
                return True
            except Exception as e:
                logger.warning("MongoDB connection failed (%s: %s). RAG will operate without database.", type(e).__name__, e)
                self._is_connected = False
                self._last_fail_time = time.time()
                if self._client:
                    try:
                        self._client.close()
                    except Exception:
                        pass
                    self._client = None
                return False

    def is_available(self) -> bool:
        """Returns True if MongoDB is configured and responsive."""
        if self._closed:
            return False
        with self._lock:
            if self._is_connected:
                return True
        return self.connect()

    def ensure_indexes(self) -> None:
        """Creates unique ID and weighted text indexes for optimal query ranking."""
        if not self._is_connected or self._collection is None:
            return

        try:
            # 1. Unique index on document ID
            self._collection.create_index([("id", pymongo.ASCENDING)], unique=True)

            # 2. Full-text search index with weighted fields (default_language='none' for proper names)
            text_weights = {
                "aliases": 10,
                "title": 8,
                "keywords": 5,
                "summary": 3,
                "content": 1,
            }
            self._collection.create_index(
                [
                    ("title", pymongo.TEXT),
                    ("aliases", pymongo.TEXT),
                    ("keywords", pymongo.TEXT),
                    ("summary", pymongo.TEXT),
                    ("content", pymongo.TEXT),
                ],
                name="knowledge_text_index",
                weights=text_weights,
                default_language="none",
            )
            logger.info("MongoDB indexes verified on '%s'", self.collection_name)
        except Exception as e:
            # Code 85: IndexOptionsConflict - an equivalent index already exists (e.g. default_language difference)
            if getattr(e, "code", None) == 85 or "IndexOptionsConflict" in str(e):
                logger.debug("Existing MongoDB text index preserved: %s", e)
            else:
                logger.warning("Notice on MongoDB index creation: %s", e)

    def upsert_documents(self, documents: List[Dict[str, Any]]) -> int:
        """Upserts a list of knowledge documents into the collection."""
        if not self.is_available() or self._collection is None:
            raise RuntimeError("MongoDB is not available for upsert operation.")

        count = 0
        for doc in documents:
            doc_id = doc.get("id")
            if not doc_id:
                continue

            payload = dict(doc)
            payload.pop("_id", None)

            update_doc: Dict[str, Any] = {"$set": payload}
            if "is_active" not in payload:
                update_doc["$setOnInsert"] = {"is_active": True}

            self._collection.update_one(
                {"_id": doc_id},
                update_doc,
                upsert=True,
            )
            count += 1

        logger.info("Upserted %d document(s) into MongoDB collection '%s'", count, self.collection_name)
        return count

    def search_text(self, query: str, top_k: int = 3, min_score: float = 1.0) -> List[Dict[str, Any]]:
        """Searches MongoDB using text score ranking, falling back to word-bounded regex match."""
        if not self.is_available() or self._collection is None:
            return []

        clean_query = query.strip()
        if not clean_query:
            return []

        results: List[Dict[str, Any]] = []
        seen_ids = set()

        # 1. Primary Text Search using textScore
        try:
            cursor = self._collection.find(
                {"$text": {"$search": clean_query}, "is_active": {"$ne": False}},
                {"score": {"$meta": "textScore"}},
            ).sort([("score", {"$meta": "textScore"})]).limit(top_k)

            for doc in cursor:
                doc_id = doc.get("id") or str(doc.get("_id"))
                score = float(doc.get("score", 0.0))
                if score >= min_score and doc_id not in seen_ids:
                    seen_ids.add(doc_id)
                    results.append(self._format_doc(doc, score))

            if results:
                return results[:top_k]
        except Exception as text_err:
            logger.debug("MongoDB text search error (%s), attempting token fallback", text_err)

        # 2. Token-level Regex / Alias fallback (with stopwords filter and word boundaries)
        stopwords = {
            "the", "is", "at", "which", "on", "who", "what", "where", "how",
            "and", "or", "to", "in", "for", "with", "a", "an", "of", "about",
            "are", "was", "were", "tell", "know", "me", "you"
        }
        tokens = [t.lower() for t in re.findall(r"\w+", clean_query) if len(t) >= 2 and t.lower() not in stopwords]
        if tokens:
            try:
                regex_pattern = "|".join([r"\b" + re.escape(t) + r"\b" for t in tokens])
                cursor = self._collection.find(
                    {
                        "$or": [
                            {"aliases": {"$regex": regex_pattern, "$options": "i"}},
                            {"keywords": {"$regex": regex_pattern, "$options": "i"}},
                            {"title": {"$regex": regex_pattern, "$options": "i"}},
                        ],
                        "is_active": {"$ne": False},
                    }
                ).limit(top_k * 2)

                fallback_candidates: List[Tuple[float, Dict[str, Any]]] = []
                for doc in cursor:
                    doc_id = doc.get("id") or str(doc.get("_id"))
                    if doc_id in seen_ids:
                        continue

                    # Score candidate by token occurrences in aliases/title/keywords
                    score = 0.0
                    aliases_text = " ".join(doc.get("aliases", [])).lower()
                    title_text = str(doc.get("title", "")).lower()
                    keywords_text = " ".join(doc.get("keywords", [])).lower()

                    for tok in tokens:
                        if re.search(r"\b" + re.escape(tok) + r"\b", aliases_text):
                            score += 4.0
                        if re.search(r"\b" + re.escape(tok) + r"\b", title_text):
                            score += 3.0
                        if re.search(r"\b" + re.escape(tok) + r"\b", keywords_text):
                            score += 2.0

                    if score >= min_score:
                        seen_ids.add(doc_id)
                        fallback_candidates.append((score, doc))

                # Sort fallback matches by relevance score descending
                fallback_candidates.sort(key=lambda x: x[0], reverse=True)
                for score, doc in fallback_candidates[:top_k]:
                    results.append(self._format_doc(doc, score=score))

            except Exception as regex_err:
                logger.warning("MongoDB token fallback search failed: %s", regex_err)

        return results[:top_k]

    def _format_doc(self, doc: Dict[str, Any], score: float) -> Dict[str, Any]:
        """Normalizes document structure to match KnowledgeRetriever standard."""
        return {
            "id": doc.get("id") or str(doc.get("_id")),
            "title": doc.get("title", ""),
            "summary": doc.get("summary", ""),
            "content": doc.get("content", ""),
            "score": round(score, 2),
        }

    def list_documents(self, filter_query: Optional[Dict[str, Any]] = None, limit: int = 100) -> List[Dict[str, Any]]:
        """Lists documents from the MongoDB knowledge collection."""
        if not self.is_available() or self._collection is None:
            return []
        query = filter_query or {"is_active": {"$ne": False}}
        try:
            cursor = self._collection.find(query, {"_id": 0}).limit(limit)
            return list(cursor)
        except Exception as e:
            logger.warning("Error listing MongoDB documents: %s", e)
            return []

    def close(self) -> None:
        """Closes the active MongoDB client connection."""
        self._closed = True
        self._is_connected = False
        if self._client:
            try:
                self._client.close()
            except Exception:
                pass
            self._client = None


_GLOBAL_STORE: Optional[MongoKnowledgeStore] = None


def get_global_mongo_store() -> MongoKnowledgeStore:
    """Returns a shared MongoKnowledgeStore instance with pooled connection."""
    global _GLOBAL_STORE
    if _GLOBAL_STORE is None:
        _GLOBAL_STORE = MongoKnowledgeStore()
    return _GLOBAL_STORE
