# agents/reader_agent.py
import logging
from typing import Dict, Any, Optional

logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO)


class ReaderAgent:
    """
    Simple reader/normalizer for a ticket input.
    Accepts a ticket dict (raw from backend or test) and returns a normalized dict:
    {
      "id": int,
      "title": str,
      "description": str,
      "reporter": str,
      "priority": Optional[str],
      "category": Optional[str],
      "status": str,
      "raw": {...}   # original payload for debugging
    }
    """

    def read(self, raw: Dict[str, Any]) -> Dict[str, Any]:
        if raw is None:
            raise ValueError("ReaderAgent.read() received None")

        # If the backend client returned a Response-like object, handle that too
        if hasattr(raw, "json") and callable(raw.json):
            try:
                raw = raw.json()
            except Exception:
                # fallback: keep original
                pass

        # Some codepaths previously passed the whole "sample" as nested under 'ticket'
        # so try to unwrap common wrappers
        if isinstance(raw, dict) and "ticket" in raw and isinstance(raw["ticket"], dict):
            raw = raw["ticket"]

        # Build normalized dict with safe fallbacks
        ticket_id = raw.get("id") or raw.get("ticketId") or raw.get("ticket_id")
        try:
            ticket_id = int(ticket_id) if ticket_id is not None else None
        except (TypeError, ValueError):
            # leave as-is if not convertible
            pass

        normalized = {
            "id": ticket_id,
            "title": raw.get("title") or raw.get("subject") or "",
            "description": raw.get("description") or raw.get("body") or "",
            "reporter": raw.get("reporter") or raw.get("createdBy") or raw.get("reporterEmail") or "",
            "priority": raw.get("priority"),
            "category": raw.get("category"),
            "status": raw.get("status") or "OPEN",
            "raw": raw,
        }

        logger.info("ReaderAgent normalized ticket id=%s title=%s", normalized["id"], normalized["title"])
        return normalized
