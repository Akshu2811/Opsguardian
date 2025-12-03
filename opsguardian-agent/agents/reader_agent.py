import logging
from typing import Dict, Any, Optional

logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO)


class ReaderAgent:
    """
    ReaderAgent is responsible for normalizing ticket input into a consistent structure.

    It accepts raw ticket dictionaries coming from:
      - backend JSON responses
      - test harnesses
      - ad-hoc dicts used in agent pipelines

    It transforms them into a stable internal format:
      {
        "id": int | None,
        "title": str,
        "description": str,
        "reporter": str,
        "priority": Optional[str],
        "category": Optional[str],
        "status": str,
        "raw": { ...original payload... }
      }

    This normalization reduces branching logic in downstream classifier/suggester components.
    """

    def read(self, raw: Dict[str, Any]) -> Dict[str, Any]:
        """
        Normalize a raw ticket dictionary into a consistent ticket structure.

        Behaviors:
          - Accepts dicts or backend Response-like objects (.json()).
          - Unwraps "ticket" nesting if present (some API variants wrap payloads).
          - Extracts ID from multiple possible fields (id, ticketId, ticket_id).
          - Falls back to safe defaults for missing title/description/reporter fields.
          - Preserves original raw payload under "raw" for debugging and tracing.
        """
        if raw is None:
            raise ValueError("ReaderAgent.read() received None")

        # Allow backend Response-like objects that expose .json()
        if hasattr(raw, "json") and callable(raw.json):
            try:
                raw = raw.json()
            except Exception:
                # If .json() fails, keep raw untouched
                pass

        # Support older or alternative wrappers where payload is nested:
        # { "ticket": { ...actual ticket... } }
        if isinstance(raw, dict) and "ticket" in raw and isinstance(raw["ticket"], dict):
            raw = raw["ticket"]

        # Extract ticket_id from various historically-used fields
        ticket_id = raw.get("id") or raw.get("ticketId") or raw.get("ticket_id")
        try:
            ticket_id = int(ticket_id) if ticket_id is not None else None
        except (TypeError, ValueError):
            # If the ID isn't numeric, keep the raw value rather than failing
            pass

        # Build normalized structure with safe fallbacks for missing fields
        normalized = {
            "id": ticket_id,
            "title": raw.get("title") or raw.get("subject") or "",
            "description": raw.get("description") or raw.get("body") or "",
            "reporter": raw.get("reporter") or raw.get("createdBy") or raw.get("reporterEmail") or "",
            "priority": raw.get("priority"),
            "category": raw.get("category"),
            "status": raw.get("status") or "OPEN",
            "raw": raw,  # preserve original payload for debugging/inspection
        }

        logger.info("ReaderAgent normalized ticket id=%s title=%s", normalized["id"], normalized["title"])
        return normalized
