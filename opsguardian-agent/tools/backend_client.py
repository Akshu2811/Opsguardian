# tools/backend_client.py (relevant parts)
import requests
import os

class BackendClient:
    def __init__(self, base_url=None):
        base = base_url or os.getenv("OPS_BACKEND_URL", "http://localhost:8080/api")
        self.base = base.rstrip('/') + '/'

    def list_tickets(self):
        r = requests.get(self.base + "tickets")
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
