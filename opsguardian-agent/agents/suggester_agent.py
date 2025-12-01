# agents/suggester_agent.py
import logging

logger = logging.getLogger(__name__)


class SuggesterAgent:
    """
    Generates helpful suggestions for ops engineers based on the ticket.
    For now uses simple heuristics (pure Python).
    In Step 4 we will replace this with Gemini LLM.
    """

    def generate(self, ticket: dict) -> dict:
        title = ticket.get("title", "").lower()
        description = ticket.get("description", "").lower()

        suggestions = []

        # Very simple placeholder rules
        if "database" in title or "db" in description:
            suggestions.append("Check database connectivity, credentials, and slow queries.")
            suggestions.append("Review recent migrations or schema changes.")

        if "network" in title or "timeout" in description:
            suggestions.append("Check network latency and packet loss.")
            suggestions.append("Verify gateway/Load balancer health.")

        if "login" in title or "auth" in description:
            suggestions.append("Check authentication service logs.")
            suggestions.append("Check user provisioning or permission issues.")

        if not suggestions:
            suggestions.append("Review logs around the time of failure.")
            suggestions.append("Check service health metrics and alerts.")

        logger.info("SuggesterAgent produced %s suggestions", len(suggestions))
        return {
            "id": ticket["id"],
            "suggestions": suggestions
        }
