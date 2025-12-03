# agents/adk_suggester.py (updated: returns used_adk flag and uses retries)
import logging
from typing import Dict, Any, List

logger = logging.getLogger(__name__)

def _heuristic_suggestions() -> List[str]:
    return [
        "Check service logs for exceptions and stack traces.",
        "Verify recent deployments and config changes.",
        "Check upstream/downstream dependency availability (DB, third-party APIs)."
    ]

def suggest_with_adk(normalized_ticket: Dict[str, Any]) -> Dict[str, Any]:
    """
    Returns dict: {'suggestions': [...], 'used_adk': True|False}
    """
    title = normalized_ticket.get("title", "") or ""
    description = normalized_ticket.get("description", "") or ""

    try:
        from agents.adk_runtime import run_agent_sync_with_retries
        from agents.adk_utils import extract_suggestions_from_adk_response
        prompt = (
            f"Generate 3-6 short, actionable troubleshooting suggestions for this issue.\n"
            f"Title: {title}\n"
            f"Description: {description}\n"
            f"Return ONLY a JSON array: [\"...\"]"
        )
        logger.debug("Calling ADK runner for suggestions (with retries)")
        raw = run_agent_sync_with_retries("adk_llm_agent", prompt)
        logger.debug("ADK raw suggester response: %r", raw)
        try:
            suggestions = extract_suggestions_from_adk_response(raw)
            if suggestions:
                logger.info("ADK returned %d suggestions", len(suggestions))
                return {"suggestions": suggestions, "used_adk": True}
        except Exception:
            logger.debug("extract_suggestions_from_adk_response failed", exc_info=False)
    except Exception as e:
        logger.warning("ADK suggester failed or not available: %s", e, exc_info=False)

    # fallback
    logger.info("Returning heuristic suggestions")
    return {"suggestions": _heuristic_suggestions(), "used_adk": False}

__all__ = ["suggest_with_adk"]
