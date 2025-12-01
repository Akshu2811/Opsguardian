# agents/adk_classifier.py
import logging
from typing import Dict, Any, Optional

logger = logging.getLogger(__name__)

# small heuristic fallback map
_KEYWORD_MAP = {
    "payment": ("Payments", "P0"),
    "pay": ("Payments", "P0"),
    "db": ("Database", "P0"),
    "database": ("Database", "P0"),
    "sql": ("Database", "P1"),
    "timeout": ("Network", "P1"),
    "latency": ("Network", "P1"),
    "login": ("Application", "P1"),
    "auth": ("Access", "P1"),
    "password": ("Access", "P2"),
    "disk": ("Database", "P0"),
    "vpn": ("Network", "P1"),
    "security": ("Security", "P0"),
}


def _heuristic_classify(title: str, description: str) -> Dict[str, str]:
    text = f"{title} {description}".lower()
    for kw, (cat, prio) in _KEYWORD_MAP.items():
        if kw in text:
            logger.debug("Heuristic matched keyword=%s -> (%s,%s)", kw, cat, prio)
            return {"category": cat, "priority": prio}
    return {"category": "Other", "priority": "P2"}


def _parse_adk_output(raw: Any) -> Optional[Dict[str, str]]:
    """
    Try to coerce ADK response into {'category':..., 'priority':...}
    This is intentionally forgiving — ADK shapes vary.
    """
    try:
        # If adk_utils available, prefer it (keeps parsing centralized)
        from agents.adk_utils import parse_classification_output  # local import for safety
        parsed = parse_classification_output(raw)
        if parsed and isinstance(parsed, dict) and parsed.get("priority"):
            return {"category": parsed.get("category") or "Other", "priority": parsed.get("priority")}
    except Exception:
        logger.debug("adk_utils.parse_classification_output not available or failed", exc_info=False)

    # Generic attempts:
    try:
        if isinstance(raw, dict):
            # common shapes: raw['classification'], raw['parts']
            if "classification" in raw and isinstance(raw["classification"], dict):
                c = raw["classification"]
                return {"category": c.get("category") or c.get("label") or "Other", "priority": c.get("priority") or "P2"}
            # look inside parts list
            parts = raw.get("parts") or raw.get("items") or []
            for p in parts:
                text = (p.get("text") if isinstance(p, dict) else str(p)).lower()
                for kw, (cat, prio) in _KEYWORD_MAP.items():
                    if kw in text:
                        return {"category": cat, "priority": prio}
        elif isinstance(raw, list):
            for itm in raw:
                text = str(itm).lower()
                for kw, (cat, prio) in _KEYWORD_MAP.items():
                    if kw in text:
                        return {"category": cat, "priority": prio}
        elif isinstance(raw, str):
            txt = raw.lower()
            for kw, (cat, prio) in _KEYWORD_MAP.items():
                if kw in txt:
                    return {"category": cat, "priority": prio}
    except Exception:
        logger.debug("Generic ADK parse attempts failed", exc_info=False)

    return None


def classify_with_adk(normalized_ticket: Dict[str, Any]) -> Dict[str, str]:
    """
    Public function expected by router_agent.
    Tries ADK via run_agent_sync; falls back to heuristics.
    Returns dict with keys: 'category' and 'priority'.
    """
    title = normalized_ticket.get("title", "") or ""
    description = normalized_ticket.get("description", "") or ""

    # Attempt to call ADK runner (import inside function to avoid import-time cycles)
    try:
        from agents.adk_runtime import run_agent_sync  # local import
        prompt = (
            f"Classify this ticket into priority & category.\n"
            f"Title: {title}\n"
            f"Description: {description}\n"
            f"Return JSON: {{\"priority\":\"P0|P1|P2|P3\", \"category\":\"...\"}}"
        )
        logger.debug("Calling ADK runner for classification")
        raw = run_agent_sync("adk_llm_agent", prompt)
        logger.debug("ADK raw classification response: %r", raw)
        parsed = _parse_adk_output(raw)
        if parsed:
            logger.info("Classified with ADK -> %s", parsed)
            return parsed
        else:
            logger.warning("ADK parse incomplete — falling back to heuristic.")
    except Exception as e:
        logger.warning("ADK classification failed or not available: %s", e, exc_info=False)

    # Fallback
    fallback = _heuristic_classify(title, description)
    logger.info("Heuristic classification -> %s", fallback)
    return fallback


# export
__all__ = ["classify_with_adk"]
