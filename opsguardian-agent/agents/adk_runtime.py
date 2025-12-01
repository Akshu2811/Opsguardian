# agents/adk_runtime.py
import asyncio
import logging
from typing import Optional, Any

from google.adk.runners import InMemoryRunner  # use InMemoryRunner to simplify local runs
from google.adk.sessions.in_memory_session_service import InMemorySessionService

from agents import adk_utils  # local utils (extract_text_from_adk_response)
logger = logging.getLogger(__name__)

# Global runner instance
_RUNNER: Optional[InMemoryRunner] = None


def get_runner() -> Optional[InMemoryRunner]:
    """Return the currently created runner (or None)."""
    return _RUNNER


def create_runner_with_agent(agent_instance, *, app_name: Optional[str] = None) -> InMemoryRunner:
    """
    Create the global in-memory runner for the provided agent instance.
    This is idempotent: if a runner already exists, returns it.
    """
    global _RUNNER
    if _RUNNER is not None:
        return _RUNNER

    # Use InMemoryRunner which bundles in-memory artifact/session/memory services.
    # Provide the agent instance and optional app_name.
    _RUNNER = InMemoryRunner(agent=agent_instance, app_name=app_name)
    logger.info("Created global ADK InMemoryRunner with app_name=%s", app_name or _RUNNER.app_name)
    return _RUNNER


async def run_agent_async(agent_name: str, prompt: str, *, quiet: bool = True, verbose: bool = False) -> str:
    """
    Run the ADK runner in debug mode and return a flattened plain string response.

    - agent_name: used as session_id so responses are grouped per-agent.
    - prompt: message (string) to send to the root agent.
    Returns a plain string (best-effort extracted).
    """
    if _RUNNER is None:
        raise RuntimeError("Runner not initialized. Call create_runner_with_agent(agent_instance) first.")

    # run_debug returns a list of Event objects collected from the run.
    # We call run_debug which creates/uses in-memory session and returns events.
    logger.debug("Calling runner.run_debug for agent=%s prompt=%s", agent_name, prompt[:120])
    try:
        events = await _RUNNER.run_debug(prompt, user_id="debug_user", session_id=agent_name, run_config=None,
                                         quiet=quiet, verbose=verbose)
    except Exception as e:
        logger.exception("ADK run_debug raised: %s", e)
        # Give a readable error back to callers
        return f"Error calling ADK model: {e}"

    # events might be a list (collected_events) - flatten and extract text
    logger.debug("Raw events returned from runner: %r", events)
    try:
        # use helper to extract best textual content from events/list
        text = adk_utils.extract_text_from_adk_response(events)
        if text is None:
            text = ""
    except Exception as e:
        logger.exception("Failed to extract text from ADK response: %s", e)
        # return repr as fallback
        try:
            text = repr(events)
        except Exception:
            text = "ADK response (unserializable)"
    # For debugging keep a short raw debug log
    logger.debug("Flattened ADK text (first 300 chars): %s", text[:300])
    return text


def run_agent_sync(agent_name: str, prompt: str, *, quiet: bool = True, verbose: bool = False) -> str:
    """
    Synchronous wrapper around run_agent_async; returns a plain string.
    Safe to call from normal sync code (not inside an existing event loop).
    """
    # asyncio.run is fine for scripts and tests (we assume you're not inside an asyncio loop).
    # If you are inside an event loop, callers should call run_agent_async directly.
    return asyncio.run(run_agent_async(agent_name, prompt, quiet=quiet, verbose=verbose))
