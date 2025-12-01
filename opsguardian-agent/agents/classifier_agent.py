# agents/classifier_agent.py
from typing import Dict, Any
import logging

logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO)


class ClassifierAgent:
    """
    Classify/label tickets. This is a simple rule-based placeholder.
    Replace or extend with ADK/LLM calls for production behavior.
    """

    def __init__(self):
        pass

    def classify(self, normalized_ticket: Dict[str, Any]) -> Dict[str, Any]:
        title = normalized_ticket.get("title", "").lower()
        desc = normalized_ticket.get("description", "").lower()
        priority = normalized_ticket.get("priority") or "P2"
        category = normalized_ticket.get("category") or "general"

        # Simple heuristics:
        if any(word in title + desc for word in ("database", "db", "sql", "disk")):
            category = "Database"
            priority = "P0" if "down" in title + desc or "outage" in title + desc else "P1"
        elif any(word in title + desc for word in ("login", "password", "unauthorized", "reset")):
            category = "Access"
            priority = "P1"
        elif "payment" in title + desc or "gateway" in title + desc:
            category = "Network"
            priority = "P0"
        elif "latency" in title + desc or "slow" in title + desc:
            category = "Application"
            priority = "P1"

        result = {"priority": priority, "category": category}
        logger.info("ClassifierAgent predicted %s for ticket %s", result, normalized_ticket.get("id"))
        return result
