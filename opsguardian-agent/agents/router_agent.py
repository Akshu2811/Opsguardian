# agents/router_agent.py
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
      - read ticket (either from backend by id, or use provided dict)
      - classify via ADK
      - update ticket on backend
      - generate suggestions via ADK
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

    # agents/router_agent.py  (replace only the process_ticket method)
    def process_ticket(self, ticket_or_id: Union[int, Dict[str, Any]]):
        logger.info("RouterAgent processing ticket id=%s", ticket_or_id if isinstance(ticket_or_id, int) else ticket_or_id.get("id"))

        # 1) Ensure we have a ticket dict (call backend if caller only provided id)
        raw_ticket = self._ensure_ticket(ticket_or_id)

        # 2) Normalize / Read
        logger.info("ReaderAgent reading ticket id=%s", raw_ticket.get("id"))
        normalized = self.reader.read(raw_ticket)

        # 3) Classify with ADK
        logger.info("ClassifierAgent classifying with ADK")
        classification = classify_with_adk(normalized)

        # 4) Update ticket on backend (only fields we want to change)
        # Decide new status: if ticket already RESOLVED/CLOSED -> keep; otherwise mark TRIAGED (or ASSIGNED if you prefer)
        current_status = (normalized.get("status") or "").upper()
        if current_status in ("RESOLVED", "CLOSED"):
            new_status = current_status
        else:
            # set TRIAGED by default; change to "ASSIGNED" if you'd rather auto-assign
            new_status = "TRIAGED"

        update_payload = {
            "priority": classification.get("priority"),
            "category": classification.get("category"),
            "status": new_status
        }
        ticket_id = normalized.get("id")
        logger.info("ResolverAgent updating ticket=%s with %s", ticket_id, update_payload)
        resolver_update = self.backend.update_ticket(ticket_id, update_payload)

        # 5) Generate suggestions via ADK
        logger.info("SuggesterAgent generating suggestions via ADK")
        suggestions_list = suggest_with_adk(normalized)

        # 6) Send suggestions to backend
        suggestions_payload = {"id": ticket_id, "suggestions": suggestions_list}
        backend_response = None
        try:
            backend_response = self.backend.add_suggestions(ticket_id, suggestions_payload)
        except AttributeError:
            logger.info("BackendClient.add_suggestions missing — falling back to POST /tickets/{id}/suggestions")
            url = f"/tickets/{ticket_id}/suggestions"
            backend_response = self.backend.post_at_path(url, suggestions_payload) if hasattr(self.backend, "post_at_path") else {"status": "not_sent"}

        # 7) Return combined result for debug
        return {
            "normalized": normalized,
            "classification": classification,
            "resolver_update": resolver_update,
            "suggestions": suggestions_payload,
            "backend_response": backend_response
        }
