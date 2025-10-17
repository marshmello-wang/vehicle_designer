from __future__ import annotations

from typing import List

from fastapi import APIRouter, HTTPException
import logging

from app.db import (
    project_get,
    version_get,
    version_insert,
    version_list,
)
from app.schemas import (
    ImagePayload,
    SubmitVersionIn,
    SubmitVersionOut,
    VersionDetailOut,
    VersionOutBrief,
)


router = APIRouter(prefix="/api/projects/{project_id}", tags=["versions"])
log = logging.getLogger("app.routes.versions")


@router.post("/versions/create", response_model=SubmitVersionOut)
def submit_version(project_id: str, body: SubmitVersionIn):
    log.info(
        "version_create project_id=%s base=%s interface=%s",
        project_id,
        body.base_version_id,
        body.interface_name,
    )
    if not project_get(project_id):
        raise HTTPException(status_code=404, detail="project not found")
    base_ver = None
    if body.base_version_id:
        base_ver = version_get(body.base_version_id)
        if not base_ver or base_ver.get("project_id") != project_id:
            raise HTTPException(status_code=404, detail="base_version not found for project")
    ver = version_insert(
        project_id=project_id,
        parent_version_id=base_ver.get("id") if base_ver else None,
        interface_name=body.interface_name,
        image_mime=body.image.mime,
        image_base64=body.image.base64,
    )
    return SubmitVersionOut(
        project_id=project_id,
        version={"id": ver["id"], "index": ver["index"]},
        image=ImagePayload(base64=ver["image_base64"], mime=ver["image_mime"]),
        interface_name=ver["interface_name"],
    )


@router.get("/versions", response_model=List[VersionOutBrief])
def list_versions(project_id: str):
    log.info("version_list project_id=%s", project_id)
    if not project_get(project_id):
        raise HTTPException(status_code=404, detail="project not found")
    rows = version_list(project_id)
    return [
        VersionOutBrief(
            id=v["id"],
            index=v["index"],
            parent_version_id=v.get("parent_version_id"),
            interface_name=v["interface_name"],
            created_at=v["created_at"],
        )
        for v in rows
    ]


@router.get("/versions/{version_id}", response_model=VersionDetailOut)
def get_version(project_id: str, version_id: str):
    log.info("version_get project_id=%s version_id=%s", project_id, version_id)
    v = version_get(version_id)
    if not v or v.get("project_id") != project_id:
        raise HTTPException(status_code=404, detail="version not found for project")
    return VersionDetailOut(
        id=v["id"],
        index=v["index"],
        parent_version_id=v.get("parent_version_id"),
        interface_name=v["interface_name"],
        image=ImagePayload(base64=v["image_base64"], mime=v["image_mime"]),
    )


@router.post("/versions/{version_id}/revert", response_model=SubmitVersionOut)
def revert_version(project_id: str, version_id: str):
    log.info("version_revert project_id=%s version_id=%s", project_id, version_id)
    if not project_get(project_id):
        raise HTTPException(status_code=404, detail="project not found")
    base = version_get(version_id)
    if not base or base.get("project_id") != project_id:
        raise HTTPException(status_code=404, detail="version not found for project")
    new_v = version_insert(
        project_id=project_id,
        parent_version_id=base["id"],
        interface_name=base["interface_name"],
        image_mime=base["image_mime"],
        image_base64=base["image_base64"],
    )
    return SubmitVersionOut(
        project_id=project_id,
        version={"id": new_v["id"], "index": new_v["index"]},
        image=ImagePayload(base64=new_v["image_base64"], mime=new_v["image_mime"]),
        interface_name=new_v["interface_name"],
    )
