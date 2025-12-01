# agents/adk_utils.py
import json
import logging
import re
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)

# Regex helpers
_JSON_OBJ_RE = re.compile(r'\{[\s\S]*?\}', re.MULTILINE)
_JSON_ARR_RE = re.compile(r'\[[\s\S]*?\]', re.MULTILINE)
CODE_FENCE_RE = re.compile(r'```(?:json)?\s*(.*?)```', re.DOTALL)
TEXT_WRAPPER_RE = re.compile(r'text\s*=\s*("""|\'\'\')?(.*?)(\1)?$', re.DOTALL)
LEADING_TRIPLE_QUOTE_RE = re.compile(r'^("""|\'\'\')')
TRAILING_TRIPLE_QUOTE_RE = re.compile(r'("""|\'\'\')$')

def _coerce_to_str(obj: Any) -> str:
    """Try multiple routes to extract text from the ADK response object."""
    if obj is None:
        return ""
    # If already a string
    if isinstance(obj, str):
        return obj
    # If raw ADK runner event object with 'text' or 'content' keys
    if isinstance(obj, dict):
        # common fields to check
        for key in ("text", "content", "output", "message", "result"):
            if key in obj and isinstance(obj[key], str):
                return obj[key]
        # some ADK responses include candidates / parts lists
        if "candidates" in obj and isinstance(obj["candidates"], list):
            parts = []
            for cand in obj["candidates"]:
                parts.append(_coerce_to_str(cand))
            return "\n".join(p for p in parts if p)
        if "items" in obj and isinstance(obj["items"], list):
            parts = []
            for it in obj["items"]:
                parts.append(_coerce_to_str(it))
            return "\n".join(p for p in parts if p)
        # as a last resort try JSON dump (useful for debugging)
        try:
            return json.dumps(obj)
        except Exception:
            return str(obj)
    # If it's a list, join elements
    if isinstance(obj, (list, tuple)):
        parts = []
        for el in obj:
            parts.append(_coerce_to_str(el))
        return "\n".join(p for p in parts if p)
    # fallback
    return str(obj)

def _strip_code_fence_and_wrappers(text: str) -> str:
    if not text:
        return ""
    original = text
    # If code fence present, take content inside first fence
    m = CODE_FENCE_RE.search(text)
    if m:
        text = m.group(1).strip()
    # Remove leading text=""" ... """ wrappers commonly seen
    m2 = TEXT_WRAPPER_RE.search(text)
    if m2:
        # group 2 is inner content
        text = m2.group(2).strip()
    # Strip leading/trailing triple quotes if present
    text = LEADING_TRIPLE_QUOTE_RE.sub("", text)
    text = TRAILING_TRIPLE_QUOTE_RE.sub("", text)
    # Trim
    text = text.strip()
    if original != text:
        logger.debug("Stripped wrapper/code-fence. Before (truncated): %s\nAfter (truncated): %s",
                     original[:200].replace("\n", "\\n"), text[:200].replace("\n", "\\n"))
    return text

def extract_text_from_adk_response(events: Any) -> str:
    """
    Universal extractor that accepts whatever the ADK runner returned (string, dict, list).
    Returns a cleaned string (code fences and text wrappers removed).
    """
    text = _coerce_to_str(events)
    text = _strip_code_fence_and_wrappers(text)
    return text

def _find_json_in_text(text: str) -> Optional[str]:
    """Try to find a JSON object or array embedded in the text using regex heuristics."""
    if not text:
        return None
    # Try array first (suggestions)
    arr_match = _JSON_ARR_RE.search(text)
    if arr_match:
        candidate = arr_match.group(1)
        logger.debug("Found JSON array in text (truncated): %s", candidate[:200].replace("\n", "\\n"))
        return candidate
    # Try object
    obj_match = _JSON_OBJ_RE.search(text)
    if obj_match:
        candidate = obj_match.group(1)
        logger.debug("Found JSON object in text (truncated): %s", candidate[:200].replace("\n", "\\n"))
        return candidate
    return None

def parse_classification_output(raw: Any) -> Optional[Dict[str, str]]:
    """
    Given an ADK raw response (events/dict/string), attempt to extract {"priority": "...", "category": "..."}.
    Returns None if parsing fails.
    """
    try:
        text = extract_text_from_adk_response(raw)
        if not text:
            return None

        # Try direct JSON parse if the whole text is JSON
        try:
            parsed = json.loads(text)
            if isinstance(parsed, dict):
                priority = parsed.get("priority")
                category = parsed.get("category")
                if priority or category:
                    return {"priority": priority, "category": category}
        except Exception:
            # Not pure JSON — continue
            pass

        # Try to find JSON embedded in noisy text
        embedded = _find_json_in_text(text)
        if embedded:
            try:
                parsed = json.loads(embedded)
                if isinstance(parsed, dict):
                    return {"priority": parsed.get("priority"), "category": parsed.get("category")}
            except Exception:
                logger.debug("Failed to json.loads embedded JSON candidate", exc_info=True)

        # Heuristic fallback: look for "P0"/"P1"/"P2"/"P3" and capitalized category words
        priority_match = re.search(r'\b(P0|P1|P2|P3)\b', text, re.IGNORECASE)
        category_match = re.search(r'\b(Database|Network|Application|Access|Security|Payments|Performance|Other|General)\b', text, re.IGNORECASE)
        if priority_match or category_match:
            return {
                "priority": priority_match.group(1).upper() if priority_match else None,
                "category": category_match.group(1) if category_match else None
            }

    except Exception as e:
        logger.debug("parse_classification_output error", exc_info=True)
    return None

def extract_suggestions_from_adk_response(raw: Any) -> List[str]:
    """
    Attempt to pull a JSON-array of suggestions from the ADK output.
    Fallback to line-based heuristics if JSON array isn't present.
    Always returns a list (may be empty).
    """
    out: List[str] = []
    try:
        text = extract_text_from_adk_response(raw)
        if not text:
            return out

        # 1) If the text is directly a JSON array
        try:
            parsed = json.loads(text)
            if isinstance(parsed, list):
                # ensure all entries are strings
                return [str(x).strip() for x in parsed if str(x).strip()]
        except Exception:
            pass

        # 2) Try to find embedded JSON array
        embedded = _find_json_in_text(text)
        if embedded:
            try:
                parsed = json.loads(embedded)
                if isinstance(parsed, list):
                    return [str(x).strip() for x in parsed if str(x).strip()]
            except Exception:
                logger.debug("Failed to parse embedded json array", exc_info=True)

        # 3) Line-based heuristics: split by lines, remove numbering/leading bullets
        lines = [ln.strip() for ln in re.split(r'\r?\n', text) if ln.strip()]
        # collect lines that look like suggestions (not headings)
        candidates = []
        for ln in lines:
            # skip lines that look like JSON keys only or too short
            if len(ln) < 6:
                continue
            # strip leading bullets/numbers
            ln = re.sub(r'^\s*[\-\*\d\.\)\:]+\s*', '', ln)
            # ignore lines like "suggestions:" or "Return ONLY..."
            if re.match(r'^(suggestions|return only)', ln, re.IGNORECASE):
                continue
            candidates.append(ln)
        # if there are clearly multiple candidate lines, return top 3-6
        if candidates:
            # remove duplicates while preserving order
            seen = set()
            uniq = []
            for c in candidates:
                if c not in seen:
                    seen.add(c)
                    uniq.append(c)
            return uniq[:6]

    except Exception:
        logger.debug("extract_suggestions_from_adk_response failed", exc_info=True)

    # final fallback (empty list)
    logger.warning("Could not extract suggestions cleanly.")
    return out

# Expose a small helper used by older code that might expect a JSON-ish string wrapped in backticks
def sanitize_json_like_text(s: str) -> str:
    """Remove stray quotes/backticks and return trimmed string."""
    if not s:
        return ""
    s = s.strip()
    # remove surrounding triple backticks or triple quotes
    s = _strip_code_fence_and_wrappers(s)
    # remove any surrounding single backticks or stray leading/trailing quote characters
    if s.startswith("`") and s.endswith("`"):
        s = s[1:-1].strip()
    if (s.startswith('"') and s.endswith('"')) or (s.startswith("'") and s.endswith("'")):
        # only strip if it looks like the whole string is quoted
        inner = s[1:-1].strip()
        # if inner looks like JSON, return it
        if inner.startswith("{") or inner.startswith("["):
            return inner
    return s
