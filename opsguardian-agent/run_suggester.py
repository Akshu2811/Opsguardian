# run_suggester.py
import os
import logging
import traceback
from typing import Optional

from tools.backend_client import BackendClient
from agents.router_agent import RouterAgent

# --- Logging (single config only) ---
LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO").upper()
logging.basicConfig(level=LOG_LEVEL, format="%(levelname)s %(name)s: %(message)s")
logger = logging.getLogger(__name__)

# --- Try to initialize ADK runner (optional) ---
def try_init_adk_runner():
    """
    Attempt to import common helper functions / agent classes and create the ADK runner.
    This is intentionally tolerant: different repos sometimes name the agent class slightly differently.
    """
    try:
        from agents.adk_runtime import create_runner_with_agent
    except Exception as e:
        logger.debug("No adk_runtime.create_runner_with_agent available: %s", e)
        return False

    # Try a few likely agent class names exported from agents.adk_agent
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
        # fallback: if module itself exposes a factory function create_agent() try that
        factory = getattr(mod, "create_agent", None)
        if callable(factory):
            try:
                agent_instance = factory()
                logger.info("Created agent_instance using agents.adk_agent.create_agent()")
            except Exception as e:
                logger.debug("agents.adk_agent.create_agent() failed: %s", e)

    if agent_instance is None:
        logger.info("No usable ADK agent class found in agents.adk_agent; continuing without ADK runner.")
        return False

    # create the runner (idempotent)
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
    Fetch all tickets and run the router agent on each.
    By default processes all tickets. To process only OPEN tickets set env PROCESS_OPEN_ONLY=true
    """
    try:
        tickets = backend.list_tickets()
    except Exception as e:
        logger.error("Failed to list tickets from backend: %s", e)
        return

    if not isinstance(tickets, list):
        logger.error("Unexpected tickets payload from backend: %r", tickets)
        return

    logger.info("Found %d ticket(s) in DB", len(tickets))

    process_open_only = os.getenv("PROCESS_OPEN_ONLY", "false").lower() in ("1", "true", "yes")
    if process_open_only:
        logger.info("PROCESS_OPEN_ONLY=true -> will only process tickets with status OPEN")

    for t in tickets:
        ticket_id = t.get("id")
        if ticket_id is None:
            logger.warning("Skipping ticket with missing id: %r", t)
            continue

        status = (t.get("status") or "").upper()
        if process_open_only and status != "OPEN":
            logger.info("Skipping ticket id=%s status=%s", ticket_id, status)
            continue

        logger.info("Processing ticket id=%s status=%s", ticket_id, status)

        try:
            result = router.process_ticket(ticket_id)
            # keep a concise printed output for inspection in CI / terminal
            logger.info("Finished processing ticket id=%s", ticket_id)
            # also print full result for debugging convenience
            print("\n=== RESULT FOR TICKET", ticket_id, "===\n")
            print(result)
        except Exception as e:
            logger.error("Error while processing ticket id=%s: %s", ticket_id, e)
            logger.debug("Traceback:\n%s", traceback.format_exc())
            # continue with next ticket
            continue


def main():
    # 1) Init ADK runner (best-effort)
    try_init_adk_runner()

    # 2) Setup backend client + router
    base = os.getenv("OPS_BACKEND_URL", "http://localhost:8080/api").rstrip('/') + '/'
    logger.info("Backend base url = %s", base)
    backend = BackendClient(base)
    router = RouterAgent(backend)

    # 3) Run over tickets
    process_all_tickets(backend, router)


if __name__ == "__main__":
    main()
