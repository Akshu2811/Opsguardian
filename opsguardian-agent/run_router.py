# run_router.py
from tools.backend_client import BackendClient
from agents.router_agent import RouterAgent

# If backend is running locally, BackendClient will call it;
# otherwise RouterAgent will simulate updates (no exceptions).
backend = BackendClient()  # uses OPS_BACKEND_URL or default http://localhost:8080
router = RouterAgent(backend=backend)

# Provide a quick sample payload or fetch actual tickets:
sample = {
    "id": 1,
    "title": "Payment gateway timeout during checkout",
    "description": "Customers see gateway timeout when checking out with card",
    "reporter": "test@example.com",
    "priority": None,
    "category": None,
    "status": "OPEN",
}


res = router.process_ticket(sample)
print(res)
