from fastapi.testclient import TestClient
from app.main import app

client = TestClient(app)


def test_health():
    response = client.get("/api/health")
    assert response.status_code == 200
    assert response.json()["status"] == "ok"


def test_pipeline_workflow():
    response = client.post("/api/pipelines/run", json={"scenario": "test_failure"})
    assert response.status_code == 200
    body = response.json()
    assert body["pipeline"]["status"] == "failed"
    assert body["decision"] == "HUMAN_REVIEW"


def test_hitl():
    response = client.post("/api/pipelines/run", json={"scenario": "test_failure"})
    pid = response.json()["pipeline_id"]
    decision = client.post(f"/api/pipelines/{pid}/decision", json={"action": "approve"})
    assert decision.status_code == 200
    assert decision.json()["decision"] == "APPROVED_FOR_RELEASE"
