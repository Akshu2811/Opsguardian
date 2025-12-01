# post_debug.py
import os, requests, json

BASE = os.getenv("OPS_BACKEND_URL", "http://localhost:8080/api").rstrip("/") + "/"
url = BASE + "tickets"
payload = {
    "title": "E2E Test: High latency in payment gateway",
    "description": "Timeouts observed when users checkout. APM shows increased latency.",
    "reporter": "e2e@test.com"
}
resp = requests.post(url, json=payload)
print("POST", url)
print("STATUS:", resp.status_code)
print("HEADERS:", resp.headers)
print("RESPONSE TEXT:", resp.text)
try:
    resp.raise_for_status()
except Exception as e:
    print("raise_for_status ->", e)
    # exit nonzero so CI / terminal shows failure
    raise
