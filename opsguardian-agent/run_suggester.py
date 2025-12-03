# run_suggester.py (updated: default process OPEN tickets, metrics, better logging)
import os
import logging
import traceback
import time
from typing import Optional

from tools.backend_client import BackendClient
from agents.router_agent import RouterAgent

LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO").upper()
logging.basicConfig(level=LOG_LEVEL, format="%(levelname)s %(name)s: %(message)s")
logger = logging.getLogger(__name__)

def try_init_adk_runner():
    try:
        from agents.adk_runtime import create_runner_with_agent
    except Exception as e:
        logger.debug("No adk_runtime.create_runner_with_agent available: %s", e)
        return False

    agent_class_candidates = ("AdkLlmAgent", "AdKllmAgent", "AdkAgent", "AdKAgent", "Adk_llm_agent")
    try:
        import importlib
        mod = importlib.import_module("agents.adk_agent")
    except Exception as e:
        logger.debug("agents.adk_agent module not importable: %s", e)
        return False

    agent_instance = None
    for cls_name in agent_class_candidates:
        cls = getattr(mod, cls_name, None)
        if cls:
            try:
                agent_instance = cls()
                logger.info("Found agents.adk_agent.%s — using it for runner creation.", cls_name)
                break
            except Exception as e:
                logger.debug("Failed to instantiate %s: %s", cls_name, e)

    if agent_instance is None:
        factory = getattr(mod, "create_agent", None)
        if callable(factory):
            try:
                agent_instance = factory()
                logger.info("Created agent_instance using agents.adk_agent.create_agent()")
            except Exception as e:
                logger.debug("agents.adk_agent.create_agent() failed: %s", e)

    if agent_instance is None:
        logger.info("No usable ADK agent found; continuing without ADK runner.")
        return False

    try:
        app_name = os.getenv("ADK_APP_NAME", "OpsGuardianAgentApp")
        create_runner_with_agent(agent_instance, app_name=app_name)
        logger.info("ADK runner initialized (app_name=%s).", app_name)
        return True
    except Exception as e:
        logger.warning("ADK runner not initialized: %s", e)
        return False

def process_all_tickets(backend: BackendClient, router: RouterAgent):
    """
    Fetch tickets and run router on each.
    By default processes only OPEN tickets (safe default). To process all tickets, set
    PROCESS_OPEN_ONLY=false in env.
    """
    process_open_only = os.getenv("PROCESS_OPEN_ONLY", "true").lower() not in ("0", "false", "no")
    if process_open_only:
        logger.info("Default behavior: processing only tickets with status=OPEN")
    else:
        logger.info("PROCESS_OPEN_ONLY=false -> will fetch all tickets")

    try:
        if process_open_only:
            tickets = backend.list_tickets(status="OPEN")
        else:
            tickets = backend.list_tickets()
    except Exception as e:
        logger.error("Failed to list tickets from backend: %s", e)
        return

    if not isinstance(tickets, list):
        logger.error("Unexpected tickets payload from backend: %r", tickets)
        return

    logger.info("Found %d ticket(s) in DB (filtered)", len(tickets))

    # metrics
    processed = 0
    fallback_classifications = 0
    fallback_suggestions = 0
    total_time = 0.0

    for t in tickets:
        ticket_id = t.get("id")
        if ticket_id is None:
            logger.warning("Skipping ticket with missing id: %r", t)
            continue

        status = (t.get("status") or "").upper()

        # ================================================================
        # NEW: HARD GUARD SO NON-OPEN TICKETS ARE NEVER REPROCESSED
        # If PROCESS_OPEN_ONLY is true (the default), skip any ticket whose
        # status is not OPEN. This prevents already-processed tickets
        # (ASSIGNED, CLOSED, etc.) from being re-run by mistake.
        # ================================================================
        if process_open_only and status != "OPEN":
            logger.info(
                "Skipping ticket id=%s because status=%s (PROCESS_OPEN_ONLY=true)",
                ticket_id, status
            )
            continue
        # ================================================================

        logger.info("Processing ticket id=%s status=%s", ticket_id, status)

        start = time.time()
        try:
            result = router.process_ticket(ticket_id)
            elapsed = time.time() - start
            processed += 1
            total_time += elapsed

            # check ADK usage flags in router result
            if not result.get("used_adk_classification", False):
                fallback_classifications += 1
            if not result.get("used_adk_suggestions", False):
                fallback_suggestions += 1

            logger.info("Finished processing ticket id=%s (%.2fs). ADK_classification=%s ADK_suggest=%s",
                        ticket_id, elapsed, result.get("used_adk_classification"), result.get("used_adk_suggestions"))

            print("\n=== RESULT FOR TICKET", ticket_id, "===\n")
            print(result)
        except Exception as e:
            logger.error("Error while processing ticket id=%s: %s", ticket_id, e)
            logger.debug("Traceback:\n%s", traceback.format_exc())
            continue

    # Print metrics summary
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
    try_init_adk_runner()

    base = os.getenv("OPS_BACKEND_URL", "http://localhost:8080/api").rstrip('/') + '/'
    logger.info("Backend base url = %s", base)
    backend = BackendClient(base)
    router = RouterAgent(backend)

    process_all_tickets(backend, router)

if __name__ == "__main__":
    main()
