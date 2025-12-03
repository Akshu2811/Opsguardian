import json
import logging
import re
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)

# Regex helpers used to locate JSON objects/arrays and common wrapper patterns
_JSON_OBJ_RE = re.compile(r'\{[\s\S]*?\}', re.MULTILINE)
_JSON_ARR_RE = re.compile(r'\[[\s\S]*?\]', re.MULTILINE)
CODE_FENCE_RE = re.compile(r'```(?:json)?\s*(.*?)```', re.DOTALL)
TEXT_WRAPPER_RE = re.compile(r'text\s*=\s*("""|\'\'\')?(.*?)(\1)?$', re.DOTALL)
LEADING_TRIPLE_QUOTE_RE = re.compile(r'^("""|\'\'\')')
TRAILING_TRIPLE_QUOTE_RE = re.compile(r'("""|\'\'\')$')

# ---------------------------------------------------------------------
# Low-level coercion & cleaning utilities
# ---------------------------------------------------------------------
def _coerce_to_str(obj: Any) -> str:
    """
    Convert a variety of ADK runner event shapes into a single string.

    Strategy:
      - Return early for None and plain strings.
      - Inspect dicts for common text-like keys (text, content, output, message, result).
      - If dict contains lists under 'candidates' or 'items', recurse and join parts.
      - If no textual key is found, fall back to json.dumps(obj) for debugging or str(obj).
      - For lists/tuples, recurse and join elements with newlines.
    This function centralizes tolerance for many ADK event shapes.
    """
    if obj is None:
        return ""
    if isinstance(obj, str):
        return obj
    if isinstance(obj, dict):
        # common fields to check
        for key in ("text", "content", "output", "message", "result"):
            if key in obj and isinstance(obj[key], str):
                return obj[key]
        # Handle lists of candidate responses
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
        # As a last resort try JSON dump (useful for debugging)
        try:
            return json.dumps(obj)
        except Exception:
            return str(obj)
    if isinstance(obj, (list, tuple)):
        parts = []
        for el in obj:
            parts.append(_coerce_to_str(el))
        return "\n".join(p for p in parts if p)
    # fallback to generic string conversion
    return str(obj)

def _strip_code_fence_and_wrappers(text: str) -> str:
    """
    Remove common wrappers around ADK textual output:

      - Extract content inside first ``` ``` code fence if present.
      - Remove "text = '''...'''" style wrappers.
      - Strip leading/trailing triple quotes.
      - Trim whitespace.

    This helps normalize outputs where the LLM returned code blocks or quoted JSON.
    """
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
    # Trim whitespace
    text = text.strip()
    if original != text:
        logger.debug("Stripped wrapper/code-fence. Before (truncated): %s\nAfter (truncated): %s",
                     original[:200].replace("\n", "\\n"), text[:200].replace("\n", "\\n"))
    return text

# ---------------------------------------------------------------------
# Public extraction helpers
# ---------------------------------------------------------------------
def extract_text_from_adk_response(events: Any) -> str:
    """
    Universal extractor that accepts whatever the ADK runner returned (string, dict, list).
    Returns a cleaned string with code fences and text wrappers removed.
    """
    text = _coerce_to_str(events)
    text = _strip_code_fence_and_wrappers(text)
    return text

def _find_json_in_text(text: str) -> Optional[str]:
    """
    Heuristically locate an embedded JSON array or object inside noisy text.

    Preference order:
      1. JSON array (useful for suggestion lists)
      2. JSON object (useful for classification outputs)
    Returns the matched substring or None.
    """
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
    Attempt to extract {"priority": "...", "category": "..."} from raw ADK output.

    Steps:
      - Normalize raw input to text and try json.loads if the whole text is JSON.
      - Search for embedded JSON and parse it.
      - Fallback to regex heuristics to find priority tokens (P0..P3) and common category words.
    Returns None when unable to infer a reliable classification.
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

        # Heuristic fallback: look for priority tokens and a known category word
        priority_match = re.search(r'\b(P0|P1|P2|P3)\b', text, re.IGNORECASE)
        category_match = re.search(
            r'\b(Database|Network|Application|Access|Security|Payments|Performance|Other|General)\b',
            text, re.IGNORECASE
        )
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
    Attempt to extract a JSON-array of suggestions from ADK output.

    Strategy:
      1. If whole text is a JSON array, parse and return stringified entries.
      2. Look for an embedded JSON array and parse it.
      3. As a fallback, split text into lines and apply heuristics:
         - remove numbering/bullets
         - ignore very short lines and headings
         - preserve order and deduplicate
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

# ---------------------------------------------------------------------
# Misc helpers
# ---------------------------------------------------------------------
def sanitize_json_like_text(s: str) -> str:
    """
    Remove stray wrappers like code fences, triple quotes, or surrounding single backticks/quotes,
    and return a trimmed string suitable for JSON parsing or display.

    Behavior:
      - Uses the shared _strip_code_fence_and_wrappers to remove the most common wrappers.
      - Strips surrounding single backticks.
      - If the remaining string is quoted and inner content looks like JSON, return inner content.
    """
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
