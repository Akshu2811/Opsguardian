# agents/adk_suggester.py (updated: returns used_adk flag and uses retries)
# Suggestion generator that prefers ADK-based suggestions, with fallback to a static heuristic list.

import logging
from typing import Dict, Any, List

logger = logging.getLogger(__name__)

def _heuristic_suggestions() -> List[str]:
    """
    Fallback suggestion set used when ADK is unavailable
    or when ADK output cannot be parsed reliably.
    Recommendations are intentionally generic and safe.
    """
    return [
        "Check service logs for exceptions and stack traces.",
        "Verify recent deployments and config changes.",
        "Check upstream/downstream dependency availability (DB, third-party APIs)."
    ]

def suggest_with_adk(normalized_ticket: Dict[str, Any]) -> Dict[str, Any]:
    """
    Attempt to produce actionable troubleshooting suggestions using the ADK runtime.
    If ADK succeeds, returns JSON shape:
        { "suggestions": [...], "used_adk": True }
    Otherwise falls back to heuristic suggestions with:
        { "suggestions": [...], "used_adk": False }

    Parameters expected in normalized_ticket:
      - title: str
      - description: str
    Missing fields default to empty strings.
    """
    title = normalized_ticket.get("title", "") or ""
    description = normalized_ticket.get("description", "") or ""

    # Primary strategy: use ADK LLM agent with retry support.
    try:
        from agents.adk_runtime import run_agent_sync_with_retries
        from agents.adk_utils import extract_suggestions_from_adk_response

        # Prompt clearly instructs ADK to return only a JSON array.
        prompt = (
            f"Generate 3-6 short, actionable troubleshooting suggestions for this issue.\n"
            f"Title: {title}\n"
            f"Description: {description}\n"
            f"Return ONLY a JSON array: [\"...\"]"
        )

        logger.debug("Calling ADK runner for suggestions (with retries)")
        raw = run_agent_sync_with_retries("adk_llm_agent", prompt)
        logger.debug("ADK raw suggester response: %r", raw)

        # Attempt to extract suggestions from various ADK output shapes.
        try:
            suggestions = extract_suggestions_from_adk_response(raw)
            if suggestions:
                logger.info("ADK returned %d suggestions", len(suggestions))
                return {"suggestions": suggestions, "used_adk": True}
        except Exception:
            # Extraction helper existed but still failed — fall back gracefully.
            logger.debug("extract_suggestions_from_adk_response failed", exc_info=False)

    except Exception as e:
        # Either ADK runtime is unavailable or the call failed.
        logger.warning("ADK suggester failed or not available: %s", e, exc_info=False)

    # Final fallback: return generic troubleshooting suggestions.
    logger.info("Returning heuristic suggestions")
    return {"suggestions": _heuristic_suggestions(), "used_adk": False}

__all__ = ["suggest_with_adk"]
