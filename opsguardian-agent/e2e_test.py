#!/usr/bin/env python3
# e2e_test.py -- end-to-end smoke test for Opsguardian backend + agent
# Save this file in the repo root and run from the same .venv:
# (.venv) PS> python e2e_test.py

import os
import time
import logging
import json
import sys
from typing import Dict, Any

import requests

# Configure logging once (this file is an entrypoint)
logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")
logger = logging.getLogger("e2e_test")

BASE = os.getenv("OPS_BACKEND_URL", "http://localhost:8080/api").rstrip("/") + "/"
HEADERS = {"Content-Type": "application/json"}


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


def get_ticket_list() -> Dict[str, Any]:
    url = BASE + "tickets"
    r = requests.get(url, timeout=10)
    r.raise_for_status()
    return r.json()


def main():
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
        # print brief server response (if any)
        try:
            import traceback
            traceback.print_exc()
        except Exception:
            pass
        sys.exit(2)

    ticket_id = created.get("id")
    logger.info("Created ticket id=%s", ticket_id)

    # simple verification: fetch list and verify our ticket id or unique title exists
    try:
        tickets = get_ticket_list()
        # Check either by id or by title substring
        found = False
        for t in tickets:
            if t.get("id") == ticket_id or (isinstance(t.get("title"), str) and payload["title"] in t.get("title")):
                found = True
                break
        if not found:
            logger.error("Created ticket not found in GET /tickets result.")
            logger.debug("GET /tickets returned: %s", tickets)
            sys.exit(3)
    except Exception as e:
        logger.error("Failed to list tickets: %s", e)
        sys.exit(4)

    logger.info("E2E test SUCCESS: ticket created and visible via GET /tickets")
    # print concise JSON result for external processing if needed
    print(json.dumps({"status": "ok", "ticket": created}, indent=2))
    sys.exit(0)


if __name__ == "__main__":
    main()
