# agents/router_agent.py (updated: status logic ASSIGNED for P0/P1, include used_adk flags)
# Orchestrator that reads a ticket, classifies it, updates backend, generates suggestions,
# and posts suggestions back to the backend. Prefers ADK-driven behavior but gracefully
# falls back to heuristics when ADK is unavailable.

import logging
from typing import Union, Dict, Any

from agents.reader_agent import ReaderAgent
from agents.adk_classifier import classify_with_adk
from agents.adk_suggester import suggest_with_adk
from tools.backend_client import BackendClient

logger = logging.getLogger(__name__)

class RouterAgent:
    """
    RouterAgent coordinates the end-to-end processing of a ticket:
      1. Ensure we have a ticket dict (fetch from backend if only id provided).
      2. Normalize/read ticket fields via ReaderAgent.
      3. Classify using ADK (or heuristic fallback) and decide a new status.
      4. Update ticket on backend with classification results.
      5. Generate suggestions using ADK (or fallback heuristic).
      6. Push suggestions to backend and return a detailed result summary.
    """

    def __init__(self, backend: BackendClient):
        # Backend client used for GET/PUT/POST operations.
        self.backend = backend
        # ReaderAgent encapsulates normalization/parsing of raw ticket payloads.
        self.reader = ReaderAgent()

    def _ensure_ticket(self, ticket_or_id: Union[int, Dict[str, Any]]) -> Dict[str, Any]:
        """
        Ensure we operate on a ticket dictionary.
        If given an integer ID, fetch the ticket from backend; if already a dict, return it.
        Raises TypeError for unsupported input types.
        """
        if isinstance(ticket_or_id, int):
            logger.debug("Fetching ticket from backend id=%s", ticket_or_id)
            return self.backend.get_ticket(ticket_or_id)
        if isinstance(ticket_or_id, dict):
            return ticket_or_id
        raise TypeError("ticket_or_id must be int or dict")

    def process_ticket(self, ticket_or_id: Union[int, Dict[str, Any]]):
        """
        Main processing pipeline for a single ticket.

        Returns a dictionary containing:
          - normalized: normalized ticket dict (ReaderAgent output)
          - classification: classification dict from classifier (may include used_adk flag)
          - used_adk_classification: boolean derived from classification
          - resolver_update: backend response from updating classification/status
          - suggestions: payload sent to backend for suggestions
          - used_adk_suggestions: boolean indicating if ADK produced suggestions
          - backend_response: response from backend when posting suggestions

        Notes:
          - Tickets already RESOLVED/CLOSED are preserved and not re-triaged.
          - Priority-driven status rule: P0/P1 -> ASSIGNED, otherwise -> TRIAGED.
          - All ADK usage is best-effort; boolean flags indicate whether ADK produced usable outputs.
        """
        ticket_id = ticket_or_id if isinstance(ticket_or_id, int) else ticket_or_id.get("id")
        logger.info("RouterAgent processing ticket id=%s", ticket_id)

        # Obtain full ticket dict and normalize its fields for downstream agents.
        raw_ticket = self._ensure_ticket(ticket_or_id)
        normalized = self.reader.read(raw_ticket)

        # Classification step (ADK preferred). The classifier returns a 'used_adk' flag.
        logger.info("ClassifierAgent classifying ticket id=%s", normalized.get("id"))
        classification = classify_with_adk(normalized)
        used_adk_classification = bool(classification.get("used_adk"))

        # Determine new status using a simple business rule:
        # - Keep RESOLVED/CLOSED as-is
        # - If priority is P0 or P1 => ASSIGNED
        # - Otherwise => TRIAGED
        current_status = (normalized.get("status") or "").upper()
        if current_status in ("RESOLVED", "CLOSED"):
            new_status = current_status
        else:
            pr = (classification.get("priority") or "").upper()
            if pr in ("P0", "P1"):
                new_status = "ASSIGNED"
            else:
                new_status = "TRIAGED"

        # Prepare payload to update ticket metadata on backend (priority/category/status).
        update_payload = {
            "priority": classification.get("priority"),
            "category": classification.get("category"),
            "status": new_status
        }
        logger.info("Updating ticket id=%s with %s", normalized.get("id"), update_payload)
        resolver_update = self.backend.update_ticket(normalized.get("id"), update_payload)

        # Suggestions step: prefer ADK suggester but fall back when necessary.
        logger.info("Generating suggestions for ticket id=%s", normalized.get("id"))
        suggester_result = suggest_with_adk(normalized)
        suggestions_list = suggester_result.get("suggestions") or []
        used_adk_suggestions = bool(suggester_result.get("used_adk"))

        # Send suggestions to backend; attempt a direct client helper first, then fallback to POST path.
        suggestions_payload = {"id": normalized.get("id"), "suggestions": suggestions_list}
        backend_response = None
        try:
            backend_response = self.backend.add_suggestions(normalized.get("id"), suggestions_payload)
        except Exception:
            # Fallback: construct the REST path and POST manually via the backend client's generic method.
            logger.info("Fallback: POSTing to /tickets/{id}/suggestions")
            url = f"/tickets/{normalized.get('id')}/suggestions"
            try:
                backend_response = self.backend.post_at_path(url, suggestions_payload)
            except Exception as e:
                # If posting fails, log and return an error-shaped backend_response for visibility.
                logger.warning("Failed to POST suggestions to backend: %s", e)
                backend_response = {"status": "failed", "error": str(e)}

        # Return a comprehensive result summary to the caller for logging/metrics.
        return {
            "normalized": normalized,
            "classification": classification,
            "used_adk_classification": used_adk_classification,
            "resolver_update": resolver_update,
            "suggestions": suggestions_payload,
            "used_adk_suggestions": used_adk_suggestions,
            "backend_response": backend_response
        }
