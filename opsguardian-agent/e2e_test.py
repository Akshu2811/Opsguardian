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

# Configure logging once (this file is an entrypoint)
logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")
logger = logging.getLogger("e2e_test")

BASE = os.getenv("OPS_BACKEND_URL", "http://localhost:8080/api").rstrip("/") + "/"
HEADERS = {"Content-Type": "application/json"}

agent_proc = None

def start_agent_subprocess():
    """Start run_suggester.py in a subprocess and stream its stdout to our console (debug only)."""
    global agent_proc
    if agent_proc is not None:
        return
    cmd = [sys.executable, "run_suggester.py"]
    logger.info("Starting agent subprocess: %s", " ".join(cmd))
    agent_proc = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)

    def stream_output():
        if agent_proc.stdout is None:
            return
        for line in agent_proc.stdout:
            # Prefix so logs are distinguishable
            print("[AGENT] " + line, end="")

    t = threading.Thread(target=stream_output, daemon=True)
    t.start()

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


def create_ticket(payload: Dict[str, Any]) -> Dict[str, Any]:
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
    url = BASE + f"tickets/{ticket_id}"
    logger.debug("GET %s", url)
    r = requests.get(url, timeout=10)
    r.raise_for_status()
    return r.json()


def wait_for_processing(ticket_id: int, timeout: int = 90, poll_interval: float = 2.0) -> Dict[str, Any]:
    """
    Wait until ticket reaches ASSIGNED and we have a non-empty suggestions list.
    This function is tolerant of multiple possible shapes where suggestions might be stored.
    On timeout it raises RuntimeError and returns the last-seen ticket JSON in the error message.
    """
    start = time.time()
    attempt = 0
    while True:
        attempt += 1
        t = get_ticket(ticket_id)

        status = (t.get("status") or "UNKNOWN")
        category = t.get("category")
        priority = t.get("priority")

        # Attempt to find suggestions in multiple shapes
        suggestions_obj = None
        if t.get("suggestions") is not None:
            suggestions_obj = t.get("suggestions")
        elif isinstance(t.get("resolver"), dict) and t["resolver"].get("suggestions") is not None:
            suggestions_obj = t["resolver"].get("suggestions")
        elif t.get("suggestions_present") is not None:
            # older boolean-style flag; keep for compatibility
            suggestions_obj = t.get("suggestions_present")

        suggestions_count = 0
        if isinstance(suggestions_obj, list):
            suggestions_count = len(suggestions_obj)
        elif isinstance(suggestions_obj, bool):
            suggestions_count = 1 if suggestions_obj else 0
        elif suggestions_obj is None:
            suggestions_count = 0

        logger.info("Ticket %s status=%s category=%s priority=%s suggestions_count=%s (attempt=%d)",
                    ticket_id, status, category, priority, suggestions_count, attempt)

        # success condition: assigned + non-empty suggestions list
        if status.upper() == "ASSIGNED" and suggestions_count > 0:
            logger.info("Ticket %s processed: assigned + suggestions present", ticket_id)
            return t

        if time.time() - start > timeout:
            pretty = json.dumps(t, indent=2, default=str)
            raise RuntimeError(f"Timeout waiting for ticket {ticket_id}. Last state:\n{pretty}")

        time.sleep(poll_interval)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--start-agent", action="store_true", help="Start run_suggester.py as a subprocess (debug only).")
    parser.add_argument("--timeout", type=int, default=90, help="Timeout seconds to wait for suggestions.")
    parser.add_argument("--poll-interval", type=float, default=2.0, help="Polling interval (seconds).")
    args = parser.parse_args()

    if args.start_agent:
        start_agent_subprocess()

    ts = int(time.time())
    payload = {
        "title": f"E2E Test Unique {ts}",
        "description": "Timeouts observed when users checkout. APM shows increased latency.",
        "reporter": "e2e@test.com"
    }

    logger.info("=== TIMESTAMP === %s", time.strftime("%Y-%m-%d %H:%M:%S %Z", time.localtime()))
    logger.info("Backend base url = %s", BASE)

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

    # Wait for processing (status + suggestions)
    try:
        processed_ticket = wait_for_processing(ticket_id, timeout=args.timeout, poll_interval=args.poll_interval)
    except Exception as e:
        logger.error("Ticket processing failed: %s", e)
        # Print the final ticket JSON if available in the exception
        if hasattr(e, "args") and e.args:
            logger.debug("Timeout dump: %s", e.args[0])
        sys.exit(5)

    logger.info("E2E test SUCCESS: ticket processed with suggestions")
    print(json.dumps({"status": "ok", "ticket": processed_ticket}, indent=2, default=str))
    sys.exit(0)


if __name__ == "__main__":
    main()
