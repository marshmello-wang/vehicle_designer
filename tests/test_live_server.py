import os
import time
import logging
import pytest
import httpx


BASE_URL = os.getenv("LIVE_SERVER_BASE_URL", "http://127.0.0.1:8000")
PNG_1x1 = (
    "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8/x8AAwMB/axuE9sAAAAASUVORK5CYII="
)

# Basic test logging
if not logging.getLogger().handlers:
    logging.basicConfig(
        level=os.getenv("TEST_LOG_LEVEL", "INFO").upper(),
        format="%(asctime)s %(levelname)s tests.live - %(message)s",
    )
log = logging.getLogger("tests.live")


def _request(client: httpx.Client, method: str, url: str, **kwargs) -> httpx.Response:
    start = time.time()
    resp = client.request(method, url, **kwargs)
    dur_ms = int((time.time() - start) * 1000)
    log.info("HTTP %s %s -> %s (%d ms)", method, url, resp.status_code, dur_ms)
    return resp


def _server_available() -> bool:
    url = f"{BASE_URL.rstrip('/')}/api/projects"
    try:
        with httpx.Client(timeout=2.0) as c:
            r = c.get(url)
            ok = r.status_code < 500
            log.info("Probing live server %s -> %s", url, r.status_code)
            return ok
    except Exception:
        log.warning("Live server not reachable at %s", url)
        return False


def test_live_text_to_image_candidates():
    base = BASE_URL.rstrip('/')
    with httpx.Client(timeout=10.0) as client:
        # create a project
        r = _request(client, "POST", f"{base}/api/projects/create", json={"name": "live"})
        assert r.status_code == 200, r.text
        pid = r.json()["project_id"]
        log.info("Created project id=%s", pid)

        # call text-to-image generation
        r2 = _request(
            client,
            "POST",
            f"{base}/api/projects/{pid}/generate/text-to-image",
            json={
                "prompt_mode": "custom",
                "custom_prompt": "a blue car",
                "num_candidates": 2,
            },
        )
        assert r2.status_code == 200, r2.text
        data = r2.json()
        assert isinstance(data.get("candidates"), list)
        assert len(data["candidates"]) == 2
        assert data["candidates"][0]["mime"] in ("image/png", "image/jpeg")
        log.info("Generated candidates=%d interface=text-to-image", len(data["candidates"]))


def test_live_projects_endpoints():
    base = BASE_URL.rstrip('/')
    with httpx.Client(timeout=10.0) as client:
        # create
        r = _request(client, "POST", f"{base}/api/projects/create", json={"name": "proj-live"})
        assert r.status_code == 200, r.text
        pid = r.json()["project_id"]
        log.info("Created project id=%s", pid)

        # get
        r2 = _request(client, "GET", f"{base}/api/projects/{pid}")
        assert r2.status_code == 200, r2.text
        assert r2.json()["project_id"] == pid

        # list
        r3 = _request(client, "GET", f"{base}/api/projects")
        assert r3.status_code == 200, r3.text
        arr = r3.json()
        assert any(p["project_id"] == pid for p in arr)
        log.info("Projects list count=%d", len(arr))


def test_live_versions_endpoints_flow():
    base = BASE_URL.rstrip('/')
    with httpx.Client(timeout=10.0) as client:
        # project
        r = _request(client, "POST", f"{base}/api/projects/create", json={"name": "ver-live"})
        assert r.status_code == 200, r.text
        pid = r.json()["project_id"]

        # create v1
        r1 = _request(
            client,
            "POST",
            f"{base}/api/projects/{pid}/versions/create",
            json={
                "image": {"base64": PNG_1x1, "mime": "image/png"},
                "interface_name": "TextToImage",
            },
        )
        assert r1.status_code == 200, r1.text
        v1 = r1.json()["version"]["id"]
        log.info("Created version v1=%s", v1)

        # create v2 based on v1
        r2 = _request(
            client,
            "POST",
            f"{base}/api/projects/{pid}/versions/create",
            json={
                "image": {"base64": PNG_1x1, "mime": "image/png"},
                "interface_name": "SketchTo3D",
                "base_version_id": v1,
            },
        )
        assert r2.status_code == 200, r2.text
        v2 = r2.json()["version"]["id"]
        log.info("Created version v2=%s (base=%s)", v2, v1)

        # list
        r3 = _request(client, "GET", f"{base}/api/projects/{pid}/versions")
        assert r3.status_code == 200, r3.text
        arr = r3.json()
        assert len(arr) == 2
        assert arr[0]["index"] == 1
        assert arr[1]["index"] == 2
        log.info("Versions list count=%d", len(arr))

        # detail v2
        r4 = _request(client, "GET", f"{base}/api/projects/{pid}/versions/{v2}")
        assert r4.status_code == 200, r4.text
        assert r4.json()["image"]["mime"] == "image/png"
        log.info("Version detail ok id=%s", v2)

        # revert v1 -> v3
        r5 = _request(client, "POST", f"{base}/api/projects/{pid}/versions/{v1}/revert")
        assert r5.status_code == 200, r5.text
        assert r5.json()["version"]["index"] == 3
        log.info("Reverted version %s -> new index=%d", v1, r5.json()["version"]["index"])


def test_live_generate_sketch_to_3d():
    base = BASE_URL.rstrip('/')
    with httpx.Client(timeout=100.0) as client:
        r = _request(client, "POST", f"{base}/api/projects/create", json={"name": "g-sketch"})
        assert r.status_code == 200, r.text
        pid = r.json()["project_id"]

        r2 = _request(
            client,
            "POST",
            f"{base}/api/projects/{pid}/generate/sketch-to-3d",
            json={
                "prompt_mode": "custom",
                "custom_prompt": "make 3d",
                "primary_image": {"base64": PNG_1x1, "mime": "image/png"},
                "num_candidates": 2,
            },
        )
        assert r2.status_code == 200, r2.text
        assert len(r2.json()["candidates"]) == 2
        log.info("Generated candidates=%d interface=sketch-to-3d", len(r2.json()["candidates"]))


def test_live_generate_fusion_randomize():
    base = BASE_URL.rstrip('/')
    with httpx.Client(timeout=100.0) as client:
        r = _request(client, "POST", f"{base}/api/projects/create", json={"name": "g-fusion"})
        assert r.status_code == 200, r.text
        pid = r.json()["project_id"]

        r2 = _request(
            client,
            "POST",
            f"{base}/api/projects/{pid}/generate/fusion-randomize",
            json={
                "prompt_mode": "custom",
                "custom_prompt": "combine",
                "primary_image": {"base64": PNG_1x1, "mime": "image/png"},
                "ref_images": [
                    {"base64": PNG_1x1, "mime": "image/png"},
                    {"base64": PNG_1x1, "mime": "image/png"},
                ],
                "num_candidates": 2,
            },
        )
        assert r2.status_code == 200, r2.text
        assert len(r2.json()["candidates"]) == 2
        log.info("Generated candidates=%d interface=fusion-randomize", len(r2.json()["candidates"]))


def test_live_generate_refine_edit():
    base = BASE_URL.rstrip('/')
    with httpx.Client(timeout=100.0) as client:
        r = _request(client, "POST", f"{base}/api/projects/create", json={"name": "g-refine"})
        assert r.status_code == 200, r.text
        pid = r.json()["project_id"]

        r2 = _request(
            client,
            "POST",
            f"{base}/api/projects/{pid}/generate/refine-edit",
            json={
                "prompt_mode": "custom",
                "custom_prompt": "refine",
                "primary_image": {"base64": PNG_1x1, "mime": "image/png"},
                "num_candidates": 2,
            },
        )
        assert r2.status_code == 200, r2.text
        assert len(r2.json()["candidates"]) == 2
        log.info("Generated candidates=%d interface=refine-edit", len(r2.json()["candidates"]))
