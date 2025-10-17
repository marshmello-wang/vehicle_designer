from fastapi.testclient import TestClient

from app.main import app


client = TestClient(app)

PNG_1x1 = "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8/x8AAwMB/axuE9sAAAAASUVORK5CYII="


def _mk_project():
    r = client.post("/api/projects/create", json={"name": "g"})
    assert r.status_code == 200
    return r.json()["project_id"]


def test_text_to_image_candidates():
    pass
    # pid = _mk_project()
    # r = client.post(
    #     f"/api/projects/{pid}/generate/text-to-image",
    #     json={
    #         "prompt_mode": "custom",
    #         "custom_prompt": "a blue car",
    #         "num_candidates": 3,
    #     },
    # )
    # assert r.status_code == 200
    # data = r.json()
    # assert len(data["candidates"]) == 3
    # assert data["candidates"][0]["mime"] == "image/png"


def test_sketch_to_3d_requires_primary():
    pass
    # pid = _mk_project()
    # r = client.post(
    #     f"/api/projects/{pid}/generate/sketch-to-3d",
    #     json={
    #         "prompt_mode": "custom",
    #         "custom_prompt": "upscale",
    #     },
    # )
    # assert r.status_code == 422

    # r2 = client.post(
    #     f"/api/projects/{pid}/generate/sketch-to-3d",
    #     json={
    #         "prompt_mode": "custom",
    #         "custom_prompt": "upscale",
    #         "primary_image": {"base64": PNG_1x1, "mime": "image/png"},
    #         "num_candidates": 2,
    #     },
    # )
    # assert r2.status_code == 200
    # assert len(r2.json()["candidates"]) == 2

