# agents/adk_classifier.py (updated: returns used_adk flag and uses retries)
# Lightweight classifier that prefers ADK-based classification when available,
# and falls back to a simple keyword heuristic otherwise.

import logging
from typing import Dict, Any, Optional

logger = logging.getLogger(__name__)

# Simple keyword -> (category, priority) mapping used by the fallback heuristic.
# Keep mappings conservative to avoid overly aggressive categorization.
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
    """
    Very small heuristic classifier that looks for keywords in title+description.
    Returns a dict with category, priority and used_adk=False to indicate fallback.
    """
    text = f"{title} {description}".lower()
    for kw, (cat, prio) in _KEYWORD_MAP.items():
        if kw in text:
            logger.debug("Heuristic matched keyword=%s -> (%s,%s)", kw, cat, prio)
            return {"category": cat, "priority": prio, "used_adk": False}
    # Default fallback if no keywords matched
    return {"category": "Other", "priority": "P2", "used_adk": False}

def _parse_adk_output(raw: Any) -> Optional[Dict[str, str]]:
    """
    Try several strategies to interpret raw ADK output:
      1. Use agents.adk_utils.parse_classification_output if available.
      2. Inspect common structures returned by LLM/ADK (dicts with 'classification',
         lists of 'parts'/'items', or plain string outputs).
    Returns a dict with category and priority, or None if parsing failed.
    """
    try:
        # Preferred parsing helper (keeps this module decoupled from ADK internals).
        from agents.adk_utils import parse_classification_output
        parsed = parse_classification_output(raw)
        if parsed and isinstance(parsed, dict) and parsed.get("priority"):
            return {"category": parsed.get("category") or "Other", "priority": parsed.get("priority")}
    except Exception:
        # Helper not available or failed — continue with generic parsing attempts.
        logger.debug("adk_utils.parse_classification_output not available or failed", exc_info=False)

    try:
        # Generic parsing attempts for various ADK output shapes.
        if isinstance(raw, dict):
            # Common shaped response: {"classification": {...}}
            if "classification" in raw and isinstance(raw["classification"], dict):
                c = raw["classification"]
                return {"category": c.get("category") or c.get("label") or "Other", "priority": c.get("priority") or "P2"}
            # Check for parts/items that may contain text fragments to re-run keyword heuristics.
            parts = raw.get("parts") or raw.get("items") or []
            for p in parts:
                text = (p.get("text") if isinstance(p, dict) else str(p)).lower()
                for kw, (cat, prio) in _KEYWORD_MAP.items():
                    if kw in text:
                        return {"category": cat, "priority": prio}
        elif isinstance(raw, list):
            # List-shaped responses: inspect elements for keyword matches.
            for itm in raw:
                text = str(itm).lower()
                for kw, (cat, prio) in _KEYWORD_MAP.items():
                    if kw in text:
                        return {"category": cat, "priority": prio}
        elif isinstance(raw, str):
            # Plain text output from LLM — run simple keyword checks.
            txt = raw.lower()
            for kw, (cat, prio) in _KEYWORD_MAP.items():
                if kw in txt:
                    return {"category": cat, "priority": prio}
    except Exception:
        logger.debug("Generic ADK parse attempts failed", exc_info=False)

    # Unable to derive a reliable classification from ADK output.
    return None

def classify_with_adk(normalized_ticket: Dict[str, Any]) -> Dict[str, str]:
    """
    Attempt to classify the ticket using an ADK runner (with retries).
    If ADK is unavailable or parsing fails, fall back to a lightweight heuristic.

    Returns a dict containing:
      - category: string
      - priority: string (e.g. "P0", "P1", "P2")
      - used_adk: boolean flag indicating whether ADK was used successfully
    """
    title = normalized_ticket.get("title", "") or ""
    description = normalized_ticket.get("description", "") or ""

    # Primary strategy: call into ADK runtime with retries (best-effort).
    try:
        from agents.adk_runtime import run_agent_sync_with_retries

        # Construct a concise prompt that instructs ADK to return JSON.
        prompt = (
            f"Classify this ticket into priority & category.\n"
            f"Title: {title}\n"
            f"Description: {description}\n"
            f"Return JSON: {{\"priority\":\"P0|P1|P2|P3\", \"category\":\"...\"}}"
        )
        logger.debug("Calling ADK runner for classification with retries")
        raw = run_agent_sync_with_retries("adk_llm_agent", prompt)
        logger.debug("ADK raw classification response: %r", raw)

        # Try to interpret the ADK response into the expected shape.
        parsed = _parse_adk_output(raw)
        if parsed:
            parsed["used_adk"] = True
            logger.info("Classified with ADK -> %s", parsed)
            return parsed
        else:
            # ADK responded but we couldn't parse a reliable classification.
            logger.warning("ADK parse incomplete — falling back to heuristic.")
    except Exception as e:
        # ADK runtime not present or call failed — log and fall back.
        logger.warning("ADK classification failed or not available: %s", e, exc_info=False)

    # Final fallback: use the deterministic heuristic classifier.
    fallback = _heuristic_classify(title, description)
    logger.info("Heuristic classification -> %s", fallback)
    return fallback

__all__ = ["classify_with_adk"]
