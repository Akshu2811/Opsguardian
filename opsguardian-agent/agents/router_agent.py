# agents/router_agent.py (updated: status logic ASSIGNED for P0/P1, include used_adk flags)
import logging
from typing import Union, Dict, Any

from agents.reader_agent import ReaderAgent
from agents.adk_classifier import classify_with_adk
from agents.adk_suggester import suggest_with_adk
from tools.backend_client import BackendClient

logger = logging.getLogger(__name__)

class RouterAgent:
    """
    Orchestrates:
      - read ticket
      - classify via ADK (or heuristic)
      - update ticket on backend
      - generate suggestions via ADK (or heuristic)
      - send suggestions to backend
    """

    def __init__(self, backend: BackendClient):
        self.backend = backend
        self.reader = ReaderAgent()

    def _ensure_ticket(self, ticket_or_id: Union[int, Dict[str, Any]]) -> Dict[str, Any]:
        if isinstance(ticket_or_id, int):
            logger.debug("Fetching ticket from backend id=%s", ticket_or_id)
            return self.backend.get_ticket(ticket_or_id)
        if isinstance(ticket_or_id, dict):
            return ticket_or_id
        raise TypeError("ticket_or_id must be int or dict")

    def process_ticket(self, ticket_or_id: Union[int, Dict[str, Any]]):
        ticket_id = ticket_or_id if isinstance(ticket_or_id, int) else ticket_or_id.get("id")
        logger.info("RouterAgent processing ticket id=%s", ticket_id)

        raw_ticket = self._ensure_ticket(ticket_or_id)
        normalized = self.reader.read(raw_ticket)

        # Classification (may use ADK or heuristic). classifier returns used_adk flag.
        logger.info("ClassifierAgent classifying ticket id=%s", normalized.get("id"))
        classification = classify_with_adk(normalized)
        used_adk_classification = bool(classification.get("used_adk"))

        # Determine new status based on priority (ASSIGNED for P0/P1; TRIAGED otherwise)
        current_status = (normalized.get("status") or "").upper()
        if current_status in ("RESOLVED", "CLOSED"):
            new_status = current_status
        else:
            pr = (classification.get("priority") or "").upper()
            if pr in ("P0", "P1"):
                new_status = "ASSIGNED"
            else:
                new_status = "TRIAGED"

        update_payload = {
            "priority": classification.get("priority"),
            "category": classification.get("category"),
            "status": new_status
        }
        logger.info("Updating ticket id=%s with %s", normalized.get("id"), update_payload)
        resolver_update = self.backend.update_ticket(normalized.get("id"), update_payload)

        # Generate suggestions
        logger.info("Generating suggestions for ticket id=%s", normalized.get("id"))
        suggester_result = suggest_with_adk(normalized)
        suggestions_list = suggester_result.get("suggestions") or []
        used_adk_suggestions = bool(suggester_result.get("used_adk"))

        # Send suggestions to backend
        suggestions_payload = {"id": normalized.get("id"), "suggestions": suggestions_list}
        backend_response = None
        try:
            backend_response = self.backend.add_suggestions(normalized.get("id"), suggestions_payload)
        except Exception:
            logger.info("Fallback: POSTing to /tickets/{id}/suggestions")
            url = f"/tickets/{normalized.get('id')}/suggestions"
            try:
                backend_response = self.backend.post_at_path(url, suggestions_payload)
            except Exception as e:
                logger.warning("Failed to POST suggestions to backend: %s", e)
                backend_response = {"status": "failed", "error": str(e)}

        return {
            "normalized": normalized,
            "classification": classification,
            "used_adk_classification": used_adk_classification,
            "resolver_update": resolver_update,
            "suggestions": suggestions_payload,
            "used_adk_suggestions": used_adk_suggestions,
            "backend_response": backend_response
        }
