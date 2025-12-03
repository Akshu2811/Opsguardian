# tools/backend_client.py (updated)
import requests
import os
import logging

logger = logging.getLogger(__name__)

class BackendClient:
    def __init__(self, base_url=None):
        base = base_url or os.getenv("OPS_BACKEND_URL", "http://localhost:8080/api")
        self.base = base.rstrip('/') + '/'
        logger.debug("BackendClient initialized with base=%s", self.base)

    def list_tickets(self, status: str = None):
        """
        List tickets. If status is provided (e.g. "OPEN") it will be sent as query param.
        """
        url = self.base + "tickets"
        params = {}
        if status:
            params["status"] = status
        logger.debug("GET %s params=%s", url, params)
        r = requests.get(url, params=params)
        r.raise_for_status()
        return r.json()

    def get_ticket(self, ticket_id):
        r = requests.get(self.base + f"tickets/{ticket_id}")
        if r.status_code == 404:
            return None
        r.raise_for_status()
        return r.json()

    def create_ticket(self, ticket):
        r = requests.post(self.base + "tickets", json=ticket)
        r.raise_for_status()
        return r.json()

    def update_ticket(self, ticket_id, changes):
        r = requests.put(self.base + f"tickets/{ticket_id}", json=changes)
        r.raise_for_status()
        return r.json()

    def add_suggestions(self, ticket_id, payload):
        r = requests.post(self.base + f"tickets/{ticket_id}/suggestions", json=payload)
        r.raise_for_status()
        return r.json()

    def post_at_path(self, path, payload):
        """
        Generic POST helper in case add_suggestions is not available on older clients.
        path should be something like "/tickets/123/suggestions"
        """
        if path.startswith("/"):
            path = path[1:]
        url = self.base + path
        logger.debug("POST %s", url)
        r = requests.post(url, json=payload)
        r.raise_for_status()
        return r.json()
