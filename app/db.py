from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from app.config import settings


def _require_env() -> None:
    if not settings.supabase_url or not settings.supabase_service_role_key:
        raise RuntimeError("Supabase configuration missing: SUPABASE_URL and SUPABASE_SERVICE_ROLE_KEY are required")


from supabase import Client  # noqa: F401

_client: Optional["Client"] = None


def get_client():
    global _client
    _require_env()
    if _client is None:
        # Local import to avoid hard dependency at module import time during tests
        from supabase import create_client  # type: ignore

        _client = create_client(settings.supabase_url, settings.supabase_service_role_key)
    return _client


# Helpers for project table
def project_create(name: Optional[str]) -> Dict[str, Any]:
    c = get_client()
    pid = str(uuid.uuid4())
    created_at = datetime.now(timezone.utc).isoformat()
    data = {"id": pid, "name": name, "created_at": created_at}
    c.table("project").insert(data).execute()
    return data


def project_get(project_id: str) -> Optional[Dict[str, Any]]:
    c = get_client()
    res = c.table("project").select("id,name,created_at").eq("id", project_id).limit(1).execute()
    if res.data:
        return res.data[0]
    return None


def project_list() -> List[Dict[str, Any]]:
    c = get_client()
    res = c.table("project").select("id,name,created_at").order("created_at", desc=False).execute()
    return list(res.data or [])


def version_count_for_project(project_id: str) -> int:
    c = get_client()
    res = c.table("version").select("id", count="exact").eq("project_id", project_id).execute()
    # supabase-py exposes count via .count on response
    return int(res.count or 0)


# Helpers for version table
def version_get(version_id: str) -> Optional[Dict[str, Any]]:
    c = get_client()
    res = c.table("version").select("* ").eq("id", version_id).limit(1).execute()
    return res.data[0] if res.data else None


def version_list(project_id: str) -> List[Dict[str, Any]]:
    c = get_client()
    res = (
        c.table("version")
        .select("id,project_id,parent_version_id,index,interface_name,image_mime,image_base64,created_at")
        .eq("project_id", project_id)
        .order("index", desc=False)
        .execute()
    )
    return list(res.data or [])


def version_latest_index(project_id: str) -> int:
    c = get_client()
    res = (
        c.table("version")
        .select("index")
        .eq("project_id", project_id)
        .order("index", desc=True)
        .limit(1)
        .execute()
    )
    if res.data:
        return int(res.data[0]["index"])  # current max
    return 0


def version_insert(
    project_id: str,
    interface_name: str,
    image_mime: str,
    image_base64: str,
    parent_version_id: Optional[str] = None,
) -> Dict[str, Any]:
    c = get_client()
    vid = str(uuid.uuid4())
    idx = version_latest_index(project_id) + 1
    row = {
        "id": vid,
        "project_id": project_id,
        "parent_version_id": parent_version_id,
        "index": idx,
        "interface_name": interface_name,
        "image_mime": image_mime,
        "image_base64": image_base64,
        "created_at": datetime.now(timezone.utc).isoformat(),
    }
    c.table("version").insert(row).execute()
    return row
