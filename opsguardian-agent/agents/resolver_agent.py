# agents/resolver_agent.py
from typing import Dict, Any
import logging

logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO)


class ResolverAgent:
    """
    Responsible for executing actions to resolve or update tickets.
    Uses a backend client (injected by caller) to persist changes.
    """

    def __init__(self, backend_client=None):
        self.backend = backend_client

    def resolve(self, normalized_ticket: Dict[str, Any], classification: Dict[str, Any]) -> Dict[str, Any]:
        ticket_id = normalized_ticket.get("id")
        if not ticket_id:
            raise ValueError("Missing ticket id")

        payload = {
            "priority": classification.get("priority"),
            "category": classification.get("category"),
            # example status transition - adjust to your backend API
            "status": "OPEN" if normalized_ticket.get("status") == "OPEN" else normalized_ticket.get("status"),
        }

        logger.info("ResolverAgent updating ticket=%s with %s", ticket_id, payload)
        if self.backend:
            updated = self.backend.update_ticket(ticket_id, payload)
            return updated
        else:
            logger.warning("No backend client provided — returning simulated update")
            # simulated result if backend is not configured
            simulated = dict(normalized_ticket["raw"])
            simulated.update(payload)
            return simulated
