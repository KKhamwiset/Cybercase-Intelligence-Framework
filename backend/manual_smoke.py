import asyncio
import sys
sys.path.insert(0, ".")

from fastapi.testclient import TestClient
from app.main import app as backend_app

client = TestClient(backend_app)

print("=== 1. Create case ===")
resp = client.post("/api/v1/cases", json={
    "title": "Manual smoke case",
    "severity": "medium",
    "incident_summary": "Short test case",
})
print("Status:", resp.status_code)
data = resp.json()
print("Case Response:", data)
case_id = data["case_id"]

print("\n=== 2. Generate case-owned report ===")
resp = client.post(f"/api/v1/cases/{case_id}/report", json={
    "report_type": "overview",
    "force_generate": True,
})
print("Status:", resp.status_code)
data = resp.json()
print("Generate Response:", data)
assert data["status"] in ("completed", "context_expired")

report_id = data.get("report_id", "")

if report_id:
    print("\n=== 3. Get Report By ID ===")
    resp = client.get(f"/api/v1/reports/{report_id}")
    print("Status:", resp.status_code)
    print("Get Report:", resp.json()["status"])

    print("\n=== 4. Update Review Status ===")
    resp = client.patch(f"/api/v1/reports/{report_id}/review-status", json={
        "review_status": "approved"
    })
    print("Status:", resp.status_code)
    print("Update Status:", resp.json()["report"]["review_status"])

print("\nSUCCESS!")
