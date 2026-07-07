import asyncio
import sys
sys.path.insert(0, ".")

from fastapi.testclient import TestClient
from app.main import app as backend_app
from app.schemas.report import ReportRequest, ReportResumeRequest, ReviewStatusUpdate

client = TestClient(backend_app)

print("=== 1. Generate Report with dummy retrieval context ===")
# We don't have RAG running, but we can simulate RagServiceClient failure 
# which returns a followup status.
resp = client.post("/api/v1/reports/generate", json={
    "query": "Short test case",
    "retrieval_context_id": "dummy-ctx"
})
print("Status:", resp.status_code)
data = resp.json()
print("Generate Response:", data)
assert data["status"] == "context_expired"

session_id = data.get("session_id", "")

print("\n=== 2. Resume Report ===")
if session_id:
    resp = client.post("/api/v1/reports/resume", json={
        "session_id": session_id,
        "answer": "test answer"
    })
    print("Status:", resp.status_code)
    data = resp.json()
    print("Resume Response:", data)
    assert data["status"] in ("completed", "followup")

report_id = data.get("report_id", "")

if report_id:
    print("\n=== 3. Get Report ===")
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
