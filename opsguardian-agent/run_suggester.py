# run_suggester.py (updated: default process OPEN tickets, metrics, better logging)
# Entrypoint script to fetch tickets from backend, run the RouterAgent on each ticket,
# optionally initialize an ADK runner if ADK modules are present, and emit run metrics.

import os
import logging
import traceback
import time
from typing import Optional

from tools.backend_client import BackendClient
from agents.router_agent import RouterAgent

# Configure logging from environment; default to INFO for normal runs
LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO").upper()
logging.basicConfig(level=LOG_LEVEL, format="%(levelname)s %(name)s: %(message)s")
logger = logging.getLogger(__name__)

def try_init_adk_runner():
    """
    Attempt to initialize an ADK runner if ADK runtime and agent modules exist.
    This function is intentionally tolerant: failure to initialize ADK is non-fatal.
    Returns True if runner initialization succeeded, False otherwise.
    """
    try:
        from agents.adk_runtime import create_runner_with_agent
    except Exception as e:
        # ADK runtime not available — this is expected in many deployments
        logger.debug("No adk_runtime.create_runner_with_agent available: %s", e)
        return False

    # Candidate class names to look for in the agents.adk_agent module.
    agent_class_candidates = ("AdkLlmAgent", "AdKllmAgent", "AdkAgent", "AdKAgent", "Adk_llm_agent")
    try:
        import importlib
        mod = importlib.import_module("agents.adk_agent")
    except Exception as e:
        # Module either missing or import failed — ADK not usable
        logger.debug("agents.adk_agent module not importable: %s", e)
        return False

    agent_instance = None

    # Try to instantiate a known agent class from the module.
    for cls_name in agent_class_candidates:
        cls = getattr(mod, cls_name, None)
        if cls:
            try:
                agent_instance = cls()
                logger.info("Found agents.adk_agent.%s — using it for runner creation.", cls_name)
                break
            except Exception as e:
                # If instantiation fails, continue trying other names
                logger.debug("Failed to instantiate %s: %s", cls_name, e)

    # Fall back to factory function create_agent() if class-based instantiation didn't work.
    if agent_instance is None:
        factory = getattr(mod, "create_agent", None)
        if callable(factory):
            try:
                agent_instance = factory()
                logger.info("Created agent_instance using agents.adk_agent.create_agent()")
            except Exception as e:
                logger.debug("agents.adk_agent.create_agent() failed: %s", e)

    if agent_instance is None:
        # No usable ADK agent discovered — continue without ADK runner.
        logger.info("No usable ADK agent found; continuing without ADK runner.")
        return False

    try:
        # Create the ADK runner and register the agent instance with an application name.
        app_name = os.getenv("ADK_APP_NAME", "OpsGuardianAgentApp")
        create_runner_with_agent(agent_instance, app_name=app_name)
        logger.info("ADK runner initialized (app_name=%s).", app_name)
        return True
    except Exception as e:
        # ADK initialization can fail at runtime; log a warning but keep process alive.
        logger.warning("ADK runner not initialized: %s", e)
        return False

def process_all_tickets(backend: BackendClient, router: RouterAgent):
    """
    Fetch tickets from backend and process them through the router.
    By default only tickets with status 'OPEN' are fetched to avoid reprocessing.
    Set PROCESS_OPEN_ONLY=false in environment to fetch all tickets.

    Emits simple run-time metrics and logs summary at the end.
    """
    # Determine whether to restrict processing to OPEN tickets (default true)
    process_open_only = os.getenv("PROCESS_OPEN_ONLY", "true").lower() not in ("0", "false", "no")
    if process_open_only:
        logger.info("Default behavior: processing only tickets with status=OPEN")
    else:
        logger.info("PROCESS_OPEN_ONLY=false -> will fetch all tickets")

    # Fetch tickets from backend with defensive error handling
    try:
        if process_open_only:
            tickets = backend.list_tickets(status="OPEN")
        else:
            tickets = backend.list_tickets()
    except Exception as e:
        logger.error("Failed to list tickets from backend: %s", e)
        return

    # Validate backend response shape
    if not isinstance(tickets, list):
        logger.error("Unexpected tickets payload from backend: %r", tickets)
        return

    logger.info("Found %d ticket(s) in DB (filtered)", len(tickets))

    # Metrics counters collected during the run
    processed = 0
    fallback_classifications = 0
    fallback_suggestions = 0
    total_time = 0.0

    # Iterate tickets and run routing logic for each
    for t in tickets:
        ticket_id = t.get("id")
        if ticket_id is None:
            # Defensive: skip malformed ticket entries
            logger.warning("Skipping ticket with missing id: %r", t)
            continue

        status = (t.get("status") or "").upper()

        # HARD GUARD: when PROCESS_OPEN_ONLY is true, never reprocess non-OPEN tickets.
        if process_open_only and status != "OPEN":
            logger.info(
                "Skipping ticket id=%s because status=%s (PROCESS_OPEN_ONLY=true)",
                ticket_id, status
            )
            continue

        logger.info("Processing ticket id=%s status=%s", ticket_id, status)

        start = time.time()
        try:
            # Core processing: hand ticket id to router and await a result dictionary.
            result = router.process_ticket(ticket_id)
            elapsed = time.time() - start
            processed += 1
            total_time += elapsed

            # Tally whether ADK was used for classification/suggestions (reported by router)
            if not result.get("used_adk_classification", False):
                fallback_classifications += 1
            if not result.get("used_adk_suggestions", False):
                fallback_suggestions += 1

            logger.info("Finished processing ticket id=%s (%.2fs). ADK_classification=%s ADK_suggest=%s",
                        ticket_id, elapsed, result.get("used_adk_classification"), result.get("used_adk_suggestions"))

            # Print human-readable result to stdout for operator visibility
            print("\n=== RESULT FOR TICKET", ticket_id, "===\n")
            print(result)
        except Exception as e:
            # Log errors per-ticket and continue processing remaining tickets.
            logger.error("Error while processing ticket id=%s: %s", ticket_id, e)
            logger.debug("Traceback:\n%s", traceback.format_exc())
            continue

    # Compute and emit summary metrics after processing completes
    avg_time = (total_time / processed) if processed else 0.0
    summary = {
        "processed": processed,
        "fallback_classifications": fallback_classifications,
        "fallback_suggestions": fallback_suggestions,
        "avg_time_s": round(avg_time, 3)
    }
    logger.info("Run summary: %s", summary)
    print("\n=== SUGGESTER RUN SUMMARY ===\n")
    print(summary)

def main():
    """
    Main entrypoint: try to initialize ADK runner (best-effort),
    create backend client and router, then process tickets.
    """
    try_init_adk_runner()

    # Build backend base URL from environment with a sensible default
    base = os.getenv("OPS_BACKEND_URL", "http://localhost:8080/api").rstrip('/') + '/'
    logger.info("Backend base url = %s", base)

    # Create service clients and run processing loop
    backend = BackendClient(base)
    router = RouterAgent(backend)

    process_all_tickets(backend, router)

if __name__ == "__main__":
    main()
