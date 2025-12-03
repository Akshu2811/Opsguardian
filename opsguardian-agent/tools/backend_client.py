# tools/backend_client.py (updated)
# Thin HTTP client for interacting with the OpsGuardian backend API.
# Provides small helper methods that hide URL construction and REST details.

import requests
import os
import logging

logger = logging.getLogger(__name__)

class BackendClient:
    """
    BackendClient abstracts HTTP communication with the OpsGuardian backend.
    It provides typed helper methods for common operations such as:
      - listing tickets
      - retrieving a ticket
      - creating or updating tickets
      - posting suggestions
    """

    def __init__(self, base_url=None):
        """
        Initialize client with a base backend URL.
        When base_url is not provided, fall back to OPS_BACKEND_URL env var
        or default to http://localhost:8080/api.
        """
        base = base_url or os.getenv("OPS_BACKEND_URL", "http://localhost:8080/api")
        self.base = base.rstrip('/') + '/'
        logger.debug("BackendClient initialized with base=%s", self.base)

    def list_tickets(self, status: str = None):
        """
        Fetch a list of tickets from backend.
        Optional status param (e.g., "OPEN") filters the tickets on backend side.
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
        """
        Retrieve a ticket by its ID.
        Returns None if backend responds with 404, otherwise returns JSON.
        """
        r = requests.get(self.base + f"tickets/{ticket_id}")
        if r.status_code == 404:
            return None
        r.raise_for_status()
        return r.json()

    def create_ticket(self, ticket):
        """
        POST a new ticket to backend and return the created ticket JSON.
        """
        r = requests.post(self.base + "tickets", json=ticket)
        r.raise_for_status()
        return r.json()

    def update_ticket(self, ticket_id, changes):
        """
        PUT an update payload (priority/category/status) to an existing ticket.
        Returns updated ticket JSON.
        """
        r = requests.put(self.base + f"tickets/{ticket_id}", json=changes)
        r.raise_for_status()
        return r.json()

    def add_suggestions(self, ticket_id, payload):
        """
        POST suggestions to /tickets/{id}/suggestions.
        Backend is expected to process and merge them accordingly.
        """
        r = requests.post(self.base + f"tickets/{ticket_id}/suggestions", json=payload)
        r.raise_for_status()
        return r.json()

    def post_at_path(self, path, payload):
        """
        Generic POST helper for backward compatibility.
        Used when add_suggestions() may not exist or fails, so caller can POST directly
        to a known backend path such as "/tickets/123/suggestions".
        """
        if path.startswith("/"):
            path = path[1:]
        url = self.base + path
        logger.debug("POST %s", url)
        r = requests.post(url, json=payload)
        r.raise_for_status()
        return r.json()
