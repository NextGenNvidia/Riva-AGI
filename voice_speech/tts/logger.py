"""
logger.py — Per-request structured logging for the TTS module.

Every synthesis request is appended as a single JSON line to the configured
log file (default: tts_requests.jsonl). This makes it easy to post-process
with jq, pandas, or any analytics tool.

Fields logged per request
-------------------------
timestamp       ISO-8601 UTC timestamp at request start
backend         Name of the backend that handled the request
char_count      Number of characters in the input text
ttfa_ms         Time-to-first-audio in milliseconds (None if not streaming)
total_ms        Total synthesis time (from call to last byte) in milliseconds
cost_usd        Estimated cost in USD (0.0 for local backends)
success         True if synthesis completed without exception
error           Error message if success=False, else null

Usage
-----
    logger = TTSLogger(config)
    with logger.record("openai", text, cost_usd=0.001) as rec:
        audio_chunk = backend.stream(text)
        rec.mark_first_audio()   # call when first chunk arrives
    # record is automatically finalised and written on __exit__
"""

from __future__ import annotations

import json
import logging
import time
from contextlib import contextmanager
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Generator

try:
    from voice_speech.tts.config import RouterConfig
except ImportError:
    from config import RouterConfig

_log = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Request record dataclass
# ---------------------------------------------------------------------------

@dataclass
class RequestRecord:
    timestamp: str = ""
    backend: str = ""
    char_count: int = 0
    ttfa_ms: float | None = None   # None until mark_first_audio() is called
    total_ms: float = 0.0
    cost_usd: float = 0.0
    success: bool = True
    error: str | None = None

    # Internal timing fields — not serialised to JSON
    _start: float = field(default_factory=time.monotonic, repr=False)
    _first_audio_time: float | None = field(default=None, repr=False)

    def mark_first_audio(self) -> None:
        """Call this the moment the first audio chunk is received."""
        if self._first_audio_time is None:
            self._first_audio_time = time.monotonic()
            self.ttfa_ms = (self._first_audio_time - self._start) * 1000

    def finalise(self) -> None:
        """Compute total_ms. Called automatically by TTSLogger.record()."""
        self.total_ms = (time.monotonic() - self._start) * 1000

    def to_dict(self) -> dict:
        d = asdict(self)
        # Strip private fields (those starting with '_')
        return {k: v for k, v in d.items() if not k.startswith("_")}


# ---------------------------------------------------------------------------
# Logger
# ---------------------------------------------------------------------------

class TTSLogger:
    """
    Structured per-request logger.

    Parameters
    ----------
    config : RouterConfig
        Used to locate the log file path and the per-request cost budget.
    """

    def __init__(self, config: RouterConfig) -> None:
        self._config = config
        self._log_path = Path(config.log_file)

    # ------------------------------------------------------------------
    # Context manager
    # ------------------------------------------------------------------

    @contextmanager
    def record(
        self,
        backend_name: str,
        text: str,
        cost_usd: float = 0.0,
    ) -> Generator[RequestRecord, None, None]:
        """
        Context manager that creates a RequestRecord, yields it to the
        caller, then finalises and persists it when the block exits.

            with logger.record("openai", text, cost_usd=0.001) as rec:
                rec.mark_first_audio()   # when first chunk arrives
                audio = backend.synthesize(text)
        """
        rec = RequestRecord(
            timestamp=datetime.now(timezone.utc).isoformat(),
            backend=backend_name,
            char_count=len(text),
            cost_usd=cost_usd,
        )
        try:
            yield rec
        except Exception as exc:
            rec.success = False
            rec.error = str(exc)
            raise
        finally:
            rec.finalise()
            self._write(rec)
            self._warn_if_over_budget(rec)

    # ------------------------------------------------------------------
    # Session summary
    # ------------------------------------------------------------------

    def get_summary(self) -> dict:
        """
        Parse the log file and return aggregated session stats:
            total_requests  — number of synthesis calls logged
            total_cost_usd  — sum of all estimated costs
            p50_ttfa_ms     — 50th percentile time-to-first-audio
            p95_ttfa_ms     — 95th percentile time-to-first-audio
            backends_used   — dict mapping backend name -> request count
        """
        if not self._log_path.exists():
            return {"total_requests": 0}

        records: list[dict] = []
        with open(self._log_path, encoding="utf-8") as fh:
            for line in fh:
                line = line.strip()
                if line:
                    try:
                        records.append(json.loads(line))
                    except json.JSONDecodeError:
                        pass

        if not records:
            return {"total_requests": 0}

        ttfas = sorted(
            r["ttfa_ms"] for r in records if r.get("ttfa_ms") is not None
        )

        def percentile(data: list[float], p: float) -> float | None:
            if not data:
                return None
            idx = int(len(data) * p / 100)
            return round(data[min(idx, len(data) - 1)], 2)

        backends: dict[str, int] = {}
        for r in records:
            b = r.get("backend", "unknown")
            backends[b] = backends.get(b, 0) + 1

        return {
            "total_requests": len(records),
            "total_cost_usd": round(sum(r.get("cost_usd", 0) for r in records), 6),
            "p50_ttfa_ms": percentile(ttfas, 50),
            "p95_ttfa_ms": percentile(ttfas, 95),
            "backends_used": backends,
        }

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _write(self, rec: RequestRecord) -> None:
        try:
            with open(self._log_path, "a", encoding="utf-8") as fh:
                fh.write(json.dumps(rec.to_dict()) + "\n")
        except OSError as exc:
            _log.warning(
                "TTS logger: could not write to %s — %s", self._log_path, exc
            )

    def _warn_if_over_budget(self, rec: RequestRecord) -> None:
        budget = self._config.cost_budget_per_request_usd
        if rec.cost_usd > budget:
            _log.warning(
                "TTS request cost $%.6f exceeded per-request budget $%.6f "
                "(backend=%s, chars=%d)",
                rec.cost_usd,
                budget,
                rec.backend,
                rec.char_count,
            )
