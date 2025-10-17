from fastapi.testclient import TestClient

from app.main import app


client = TestClient(app)


def test_create_and_get_project():
    r = client.post("/api/projects/create", json={"name": "demo"})
    assert r.status_code == 200
    data = r.json()
    pid = data["project_id"]
    assert data["version_count"] == 0

    r2 = client.get(f"/api/projects/{pid}")
    assert r2.status_code == 200
    d2 = r2.json()
    assert d2["project_id"] == pid

    r3 = client.get("/api/projects")
    assert r3.status_code == 200
    arr = r3.json()
    assert any(p["project_id"] == pid for p in arr)

