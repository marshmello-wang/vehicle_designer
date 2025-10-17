from fastapi.testclient import TestClient

from app.main import app


client = TestClient(app)

PNG_1x1 = "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8/x8AAwMB/axuE9sAAAAASUVORK5CYII="


def _mk_project():
    r = client.post("/api/projects/create", json={"name": "v"})
    assert r.status_code == 200
    return r.json()["project_id"]


def test_submit_version_and_list_detail_revert():
    pid = _mk_project()
    # submit first version
    r = client.post(
        f"/api/projects/{pid}/versions/create",
        json={
            "image": {"base64": PNG_1x1, "mime": "image/png"},
            "interface_name": "TextToImage",
        },
    )
    assert r.status_code == 200
    v1 = r.json()["version"]["id"]

    # submit second version based on v1
    r2 = client.post(
        f"/api/projects/{pid}/versions/create",
        json={
            "image": {"base64": PNG_1x1, "mime": "image/png"},
            "interface_name": "SketchTo3D",
            "base_version_id": v1,
        },
    )
    assert r2.status_code == 200
    v2 = r2.json()["version"]["id"]

    # list
    r3 = client.get(f"/api/projects/{pid}/versions")
    assert r3.status_code == 200
    arr = r3.json()
    assert len(arr) == 2
    assert arr[0]["index"] == 1
    assert arr[1]["index"] == 2

    # detail
    r4 = client.get(f"/api/projects/{pid}/versions/{v2}")
    assert r4.status_code == 200
    d2 = r4.json()
    assert d2["image"]["mime"] == "image/png"

    # revert
    r5 = client.post(f"/api/projects/{pid}/versions/{v1}/revert")
    assert r5.status_code == 200
    assert r5.json()["version"]["index"] == 3

