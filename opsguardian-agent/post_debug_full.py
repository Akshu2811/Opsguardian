# post_debug_full.py  (run with: python post_debug_full.py)
import os, requests, json

BASE = os.getenv("OPS_BACKEND_URL", "http://localhost:8080/api").rstrip("/") + "/"
url = BASE + "tickets"

payloads = [
    # Minimal payload (what you used previously)
    {
        "title": "E2E Test: High latency in payment gateway",
        "description": "Timeouts observed when users checkout. APM shows increased latency.",
        "reporter": "e2e@test.com"
    },
    # Full payload: include fields the server might expect (priority/category/status)
    {
        "title": "E2E Test (full): High latency in payment gateway",
        "description": "Timeouts observed when users checkout. APM shows increased latency.",
        "reporter": "e2e@test.com",
        "priority": "P1",
        "category": "Payments",
        "status": "OPEN"
    },
]

for i, payload in enumerate(payloads, 1):
    print("\n=== POST attempt", i, "===")
    resp = requests.post(url, json=payload)
    print("POST", url)
    print("STATUS:", resp.status_code)
    print("HEADERS:", dict(resp.headers))
    print("RESPONSE TEXT:", resp.text)
    try:
        resp.raise_for_status()
        print("Created object:", json.dumps(resp.json(), indent=2))
    except Exception as e:
        print("raise_for_status ->", e)
