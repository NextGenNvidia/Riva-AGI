"""Mistral AI Client for RAG Knowledge Synthesis.

Uses Mistral's Chat Completion API to synthesize conversational, voice-optimized
responses based on retrieved context.
"""

import asyncio
import json
import logging
import os
import urllib.request
from typing import Optional

logger = logging.getLogger("rag.mistral")

MISTRAL_API_URL = "https://api.mistral.ai/v1/chat/completions"
DEFAULT_MISTRAL_MODEL = "mistral-small-latest"


class MistralRAGClient:
    """Client for querying Mistral API with RAG context."""

    def __init__(
        self,
        api_key: Optional[str] = None,
        model: Optional[str] = None,
        timeout: float = 4.0,
    ):
        self.api_key = api_key if api_key is not None else os.getenv("MISTRAL_API_KEY", "").strip()
        self.model = model if model is not None else os.getenv("MISTRAL_MODEL", DEFAULT_MISTRAL_MODEL)
        self.timeout = timeout

    @property
    def is_configured(self) -> bool:
        """Returns True if a Mistral API key is set."""
        return bool(self.api_key)

    async def generate_answer(self, query: str, context: str) -> Optional[str]:
        """Synthesizes a voice-friendly answer using Mistral API.

        Args:
            query: The user's original question.
            context: Retrieved facts/knowledge context from knowledge store.

        Returns:
            Synthesized response text, or None if key is missing or call fails.
        """
        api_key = self.api_key or os.getenv("MISTRAL_API_KEY", "").strip()
        if not api_key:
            logger.info("MISTRAL_API_KEY is not set. Using retrieved context directly.")
            return None

        system_prompt = (
            "You are Riva's voice knowledge assistant. Answer the user's question directly, warmly, "
            "and concisely using ONLY the provided reference context in <context>. "
            "If the context does not contain enough information to answer the question, state that you do not have that information. "
            "Do not fabricate facts. Keep the answer to 2-3 natural sentences suitable for spoken conversation."
        )

        user_content = (
            f"<context>\n{context}\n</context>\n\n"
            f"<user_question>\n{query}\n</user_question>\n\n"
            f"Please provide a concise, spoken answer based strictly on the reference context."
        )

        payload = {
            "model": self.model,
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_content},
            ],
            "max_tokens": 180,
            "temperature": 0.3,
        }

        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {api_key}",
            "User-Agent": "RivaRAG/1.0",
        }

        loop = asyncio.get_running_loop()

        def _call_api() -> Optional[str]:
            req = urllib.request.Request(
                MISTRAL_API_URL,
                data=json.dumps(payload).encode("utf-8"),
                headers=headers,
                method="POST",
            )
            try:
                with urllib.request.urlopen(req, timeout=self.timeout) as resp:
                    if resp.status == 200:
                        raw = resp.read().decode("utf-8")
                        data = json.loads(raw)
                        choices = data.get("choices", [])
                        if choices:
                            return choices[0].get("message", {}).get("content", "").strip()
            except Exception as e:
                logger.warning(f"Mistral API call error: {e}")
                return None
            return None

        try:
            answer = await loop.run_in_executor(None, _call_api)
            if answer:
                logger.info(f"Mistral generated response: {answer[:80]}...")
                return answer
        except Exception as e:
            logger.error(f"Async executor error calling Mistral: {e}")

        return None
