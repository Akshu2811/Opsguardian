# agents/adk_runtime.py (updated with retry wrapper)
import asyncio
import logging
import time
import random
from typing import Optional

from google.adk.runners import InMemoryRunner  # optional; keep as before
from google.adk.sessions.in_memory_session_service import InMemorySessionService

from agents import adk_utils  # local utils
logger = logging.getLogger(__name__)

_RUNNER: Optional[InMemoryRunner] = None

def get_runner() -> Optional[InMemoryRunner]:
    return _RUNNER

def create_runner_with_agent(agent_instance, *, app_name: Optional[str] = None) -> InMemoryRunner:
    global _RUNNER
    if _RUNNER is not None:
        return _RUNNER
    _RUNNER = InMemoryRunner(agent=agent_instance, app_name=app_name)
    logger.info("Created global ADK InMemoryRunner with app_name=%s", app_name or _RUNNER.app_name)
    return _RUNNER

async def run_agent_async(agent_name: str, prompt: str, *, quiet: bool = True, verbose: bool = False) -> str:
    if _RUNNER is None:
        raise RuntimeError("Runner not initialized. Call create_runner_with_agent(agent_instance) first.")
    logger.debug("Calling runner.run_debug for agent=%s prompt=%s", agent_name, prompt[:120])
    try:
        events = await _RUNNER.run_debug(prompt, user_id="debug_user", session_id=agent_name, run_config=None,
                                         quiet=quiet, verbose=verbose)
    except Exception as e:
        logger.exception("ADK run_debug raised: %s", e)
        raise
    logger.debug("Raw events returned from runner: %r", events)
    try:
        text = adk_utils.extract_text_from_adk_response(events)
        if text is None:
            text = ""
    except Exception as e:
        logger.exception("Failed to extract text from ADK response: %s", e)
        try:
            text = repr(events)
        except Exception:
            text = "ADK response (unserializable)"
    logger.debug("Flattened ADK text (first 300 chars): %s", text[:300])
    return text

def run_agent_sync(agent_name: str, prompt: str, *, quiet: bool = True, verbose: bool = False) -> str:
    return asyncio.run(run_agent_async(agent_name, prompt, quiet=quiet, verbose=verbose))

def run_agent_sync_with_retries(agent_name: str, prompt: str,
                                retries: int = 4, base_delay: float = 1.0, max_delay: float = 8.0,
                                *, quiet: bool = True, verbose: bool = False) -> str:
    """
    Calls run_agent_sync with exponential backoff on rate-limit-like errors.
    Retries when exception message contains 429/RateLimit/quota (case-insensitive).
    """
    last_exc = None
    for attempt in range(1, retries + 1):
        try:
            logger.debug("ADK attempt %d/%d for agent=%s", attempt, retries, agent_name)
            return run_agent_sync(agent_name, prompt, quiet=quiet, verbose=verbose)
        except Exception as e:
            last_exc = e
            msg = str(e).lower()
            # detect rate limit / quota-like failures heuristically
            if '429' in msg or 'ratelimit' in msg or 'rate limit' in msg or 'quota' in msg:
                if attempt == retries:
                    logger.warning("ADK rate-limited and retries exhausted: %s", e)
                    raise
                # exponential backoff with jitter
                delay = min(max_delay, base_delay * (2 ** (attempt - 1))) + random.random() * 0.5
                logger.warning("ADK rate limit detected. Retry %d/%d after %.1fs", attempt, retries, delay)
                time.sleep(delay)
                continue
            # if not recognized as rate-limit, re-raise immediately
            logger.exception("ADK call failed (non-rate-limit): %s", e)
            raise
    # If we get here, raise last exception
    raise last_exc
