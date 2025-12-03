# agents/adk_runtime.py (updated with retry wrapper)
# Provides an ADK InMemoryRunner and helper methods for running ADK agents
# synchronously or asynchronously, including exponential-backoff retry logic.

import asyncio
import logging
import time
import random
from typing import Optional

from google.adk.runners import InMemoryRunner  # Optional: used if ADK is available
from google.adk.sessions.in_memory_session_service import InMemorySessionService

from agents import adk_utils  # Utilities for extracting text from ADK responses
logger = logging.getLogger(__name__)

# Global runner instance — created once per process.
_RUNNER: Optional[InMemoryRunner] = None

def get_runner() -> Optional[InMemoryRunner]:
    """
    Return the global ADK runner instance if it has been initialized.
    """
    return _RUNNER

def create_runner_with_agent(agent_instance, *, app_name: Optional[str] = None) -> InMemoryRunner:
    """
    Create a global InMemoryRunner bound to the provided agent instance.
    If already initialized, returns the existing runner.
    Used during startup when ADK agent integration is present.
    """
    global _RUNNER
    if _RUNNER is not None:
        return _RUNNER

    _RUNNER = InMemoryRunner(agent=agent_instance, app_name=app_name)
    logger.info("Created global ADK InMemoryRunner with app_name=%s", app_name or _RUNNER.app_name)
    return _RUNNER

async def run_agent_async(agent_name: str, prompt: str, *, quiet: bool = True, verbose: bool = False) -> str:
    """
    Run an ADK agent asynchronously using the runner's debug mode.
    Returns flattened text extracted from ADK events.

    Raises RuntimeError if the runner is not initialized.
    """
    if _RUNNER is None:
        raise RuntimeError("Runner not initialized. Call create_runner_with_agent(agent_instance) first.")

    logger.debug("Calling runner.run_debug for agent=%s prompt=%s", agent_name, prompt[:120])
    try:
        events = await _RUNNER.run_debug(
            prompt,
            user_id="debug_user",
            session_id=agent_name,
            run_config=None,
            quiet=quiet,
            verbose=verbose
        )
    except Exception as e:
        logger.exception("ADK run_debug raised: %s", e)
        raise

    logger.debug("Raw events returned from runner: %r", events)

    # Flatten ADK response into text for downstream parsers
    try:
        text = adk_utils.extract_text_from_adk_response(events)
        if text is None:
            text = ""
    except Exception as e:
        # If extraction fails, fall back to repr or safe string
        logger.exception("Failed to extract text from ADK response: %s", e)
        try:
            text = repr(events)
        except Exception:
            text = "ADK response (unserializable)"

    logger.debug("Flattened ADK text (first 300 chars): %s", text[:300])
    return text

def run_agent_sync(agent_name: str, prompt: str, *, quiet: bool = True, verbose: bool = False) -> str:
    """
    Blocking wrapper around run_agent_async — executes in a private event loop.
    """
    return asyncio.run(run_agent_async(agent_name, prompt, quiet=quiet, verbose=verbose))

def run_agent_sync_with_retries(
        agent_name: str,
        prompt: str,
        retries: int = 4,
        base_delay: float = 1.0,
        max_delay: float = 8.0,
        *,
        quiet: bool = True,
        verbose: bool = False
) -> str:
    """
    Run an ADK agent with retry logic intended to handle transient rate-limit or quota failures.

    - Retries when the exception message contains 429 / "ratelimit" / "quota" (case-insensitive).
    - Uses exponential backoff with jitter.
    - Raises immediately for non-rate-limit failures.
    - Returns the text output from ADK if successful.

    Parameters:
      retries     : max retry attempts
      base_delay  : initial delay for exponential backoff
      max_delay   : upper bound on backoff delay
    """
    last_exc = None

    for attempt in range(1, retries + 1):
        try:
            logger.debug("ADK attempt %d/%d for agent=%s", attempt, retries, agent_name)
            return run_agent_sync(agent_name, prompt, quiet=quiet, verbose=verbose)

        except Exception as e:
            last_exc = e
            msg = str(e).lower()

            # Detect rate-limit-like errors heuristically
            if '429' in msg or 'ratelimit' in msg or 'rate limit' in msg or 'quota' in msg:
                if attempt == retries:
                    logger.warning("ADK rate-limited and retries exhausted: %s", e)
                    raise

                # Exponential backoff with random jitter
                delay = min(max_delay, base_delay * (2 ** (attempt - 1))) + random.random() * 0.5
                logger.warning("ADK rate limit detected. Retry %d/%d after %.1fs", attempt, retries, delay)
                time.sleep(delay)
                continue

            # Non-rate-limit errors are not retried
            logger.exception("ADK call failed (non-rate-limit): %s", e)
            raise

    # If exhausted attempts without returning, re-raise the last exception
    raise last_exc
