#!/usr/bin/env python3
# e2e_test.py -- improved end-to-end smoke test for OpsGuardian backend + agent
# Usage:
#   python e2e_test.py              # create ticket, wait for suggestions (expects agent already running)
#   python e2e_test.py --start-agent  # spawn run_suggester.py locally (debug only)
#
# Save in repo root and run from the .venv.

import os
import time
import logging
import json
import sys
import argparse
import subprocess
import threading
import atexit
from typing import Dict, Any, Optional

import requests

# Configure basic logging for the test entrypoint.
logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")
logger = logging.getLogger("e2e_test")

# Backend base URL derived from environment with sensible default.
BASE = os.getenv("OPS_BACKEND_URL", "http://localhost:8080/api").rstrip("/") + "/"
HEADERS = {"Content-Type": "application/json"}

# Global handle for agent subprocess used when running the agent inline for debug.
agent_proc = None

# -----------------------------------------------------------------------------
# Agent subprocess helpers
# -----------------------------------------------------------------------------
def start_agent_subprocess():
    """
    Spawn run_suggester.py as a subprocess and stream its stdout to the test console.
    This is intended for local debugging only — starts the agent runner in the same repo.
    The subprocess is registered with atexit to ensure it gets terminated on exit.
    """
    global agent_proc
    if agent_proc is not None:
        return

    cmd = [sys.executable, "run_suggester.py"]
    logger.info("Starting agent subprocess: %s", " ".join(cmd))

    # Start process and capture stdout/stderr for readable test logs.
    agent_proc = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)

    # Background thread that streams subprocess output to our stdout with a prefix.
    def stream_output():
        if agent_proc.stdout is None:
            return
        for line in agent_proc.stdout:
            # Prefix lines so operator can distinguish agent logs from test logs.
            print("[AGENT] " + line, end="")

    t = threading.Thread(target=stream_output, daemon=True)
    t.start()

    # Ensure subprocess is cleaned up on test exit.
    def stop_agent():
        global agent_proc
        if agent_proc and agent_proc.poll() is None:
            logger.info("Stopping agent subprocess...")
            agent_proc.terminate()
            try:
                agent_proc.wait(timeout=5)
            except Exception:
                agent_proc.kill()

    atexit.register(stop_agent)

# -----------------------------------------------------------------------------
# HTTP helpers for interacting with backend
# -----------------------------------------------------------------------------
def create_ticket(payload: Dict[str, Any]) -> Dict[str, Any]:
    """
    POST a ticket to the backend and return the created ticket JSON.
    Raises requests exceptions on non-2xx responses.
    """
    url = BASE + "tickets"
    logger.info("POST %s", url)
    logger.debug("BODY: %s", json.dumps(payload))
    resp = requests.post(url, json=payload, headers=HEADERS, timeout=10)
    logger.info("STATUS: %s", resp.status_code)
    logger.debug("RESPONSE HEADERS: %s", resp.headers)
    logger.debug("RESPONSE TEXT: %s", resp.text[:1000])
    resp.raise_for_status()
    return resp.json()

def get_ticket(ticket_id: int) -> Dict[str, Any]:
    """
    GET ticket by id and return its JSON representation.
    Raises requests exceptions on non-2xx responses.
    """
    url = BASE + f"tickets/{ticket_id}"
    logger.debug("GET %s", url)
    r = requests.get(url, timeout=10)
    r.raise_for_status()
    return r.json()

# -----------------------------------------------------------------------------
# Polling / wait logic
# -----------------------------------------------------------------------------
def wait_for_processing(ticket_id: int, timeout: int = 90, poll_interval: float = 2.0) -> Dict[str, Any]:
    """
    Poll the backend until the specified ticket is processed.

    Success condition:
      - ticket.status == "ASSIGNED"
      - suggestions exist (supports multiple shapes: list, boolean flag, nested resolver.suggestions)

    On timeout this raises RuntimeError and includes the last-seen ticket JSON for debugging.
    """
    start = time.time()
    attempt = 0

    while True:
        attempt += 1
        t = get_ticket(ticket_id)

        # Read common metadata fields for logging
        status = (t.get("status") or "UNKNOWN")
        category = t.get("category")
        priority = t.get("priority")

        # Support different shapes for where suggestions may be stored.
        suggestions_obj = None
        if t.get("suggestions") is not None:
            suggestions_obj = t.get("suggestions")
        elif isinstance(t.get("resolver"), dict) and t["resolver"].get("suggestions") is not None:
            suggestions_obj = t["resolver"].get("suggestions")
        elif t.get("suggestions_present") is not None:
            # Backwards-compatible boolean flag used by older implementations.
            suggestions_obj = t.get("suggestions_present")

        # Normalize suggestions to a simple count for acceptance criteria.
        suggestions_count = 0
        if isinstance(suggestions_obj, list):
            suggestions_count = len(suggestions_obj)
        elif isinstance(suggestions_obj, bool):
            suggestions_count = 1 if suggestions_obj else 0
        elif suggestions_obj is None:
            suggestions_count = 0

        logger.info(
            "Ticket %s status=%s category=%s priority=%s suggestions_count=%s (attempt=%d)",
            ticket_id, status, category, priority, suggestions_count, attempt
        )

        # Success condition: assigned + non-empty suggestions
        if status.upper() == "ASSIGNED" and suggestions_count > 0:
            logger.info("Ticket %s processed: assigned + suggestions present", ticket_id)
            return t

        # Timeout handling: include last-seen ticket state in the raised error.
        if time.time() - start > timeout:
            pretty = json.dumps(t, indent=2, default=str)
            raise RuntimeError(f"Timeout waiting for ticket {ticket_id}. Last state:\n{pretty}")

        time.sleep(poll_interval)

# -----------------------------------------------------------------------------
# Main CLI / test flow
# -----------------------------------------------------------------------------
def main():
    """
    CLI entrypoint:
      - Optionally starts agent subprocess for local debug (--start-agent).
      - Creates a unique test ticket.
      - Polls until the agent processes the ticket or timeout occurs.
      - Exits with non-zero code on failures for CI compatibility.
    """
    parser = argparse.ArgumentParser()
    parser.add_argument("--start-agent", action="store_true", help="Start run_suggester.py as a subprocess (debug only).")
    parser.add_argument("--timeout", type=int, default=90, help="Timeout seconds to wait for suggestions.")
    parser.add_argument("--poll-interval", type=float, default=2.0, help="Polling interval (seconds).")
    args = parser.parse_args()

    if args.start_agent:
        # Spawn agent runner in a subprocess when developer wants an integrated debug run.
        start_agent_subprocess()

    # Build a simple unique ticket payload using epoch seconds to avoid collisions.
    ts = int(time.time())
    payload = {
        "title": f"E2E Test Unique {ts}",
        "description": "Timeouts observed when users checkout. APM shows increased latency.",
        "reporter": "e2e@test.com"
    }

    logger.info("=== TIMESTAMP === %s", time.strftime("%Y-%m-%d %H:%M:%S %Z", time.localtime()))
    logger.info("Backend base url = %s", BASE)

    # Create ticket and fail fast if backend is unreachable or returns error.
    try:
        created = create_ticket(payload)
    except Exception as e:
        logger.error("Failed to create ticket: %s", e)
        try:
            import traceback
            traceback.print_exc()
        except Exception:
            pass
        sys.exit(2)

    ticket_id = created.get("id")
    logger.info("Created ticket id=%s", ticket_id)

    # Wait for the agent to process and enrich the ticket, otherwise exit non-zero.
    try:
        processed_ticket = wait_for_processing(ticket_id, timeout=args.timeout, poll_interval=args.poll_interval)
    except Exception as e:
        logger.error("Ticket processing failed: %s", e)
        # If the exception includes the last-seen JSON, surface it at debug level for triage.
        if hasattr(e, "args") and e.args:
            logger.debug("Timeout dump: %s", e.args[0])
        sys.exit(5)

    logger.info("E2E test SUCCESS: ticket processed with suggestions")
    print(json.dumps({"status": "ok", "ticket": processed_ticket}, indent=2, default=str))
    sys.exit(0)


if __name__ == "__main__":
    main()
