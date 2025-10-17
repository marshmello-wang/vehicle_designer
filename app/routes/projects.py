from __future__ import annotations

from typing import List
from fastapi import APIRouter, HTTPException
import logging

from app.db import project_create, project_get, project_list, version_count_for_project
from app.schemas import ProjectCreate, ProjectOut


router = APIRouter(prefix="/api/projects", tags=["projects"])
log = logging.getLogger("app.routes.projects")


@router.post("/create", response_model=ProjectOut)
def create_project(payload: ProjectCreate):
    log.info("project_create name=%s", getattr(payload, "name", None))
    p = project_create(payload.name)
    return ProjectOut(project_id=p["id"], name=p.get("name"), created_at=p["created_at"], version_count=0)


@router.get("", response_model=List[ProjectOut])
def list_projects():
    log.info("project_list")
    rows = project_list()
    result: List[ProjectOut] = []
    for p in rows:
        cnt = version_count_for_project(p["id"])  # exact count
        result.append(
            ProjectOut(project_id=p["id"], name=p.get("name"), created_at=p["created_at"], version_count=cnt)
        )
    return result


@router.get("/{project_id}", response_model=ProjectOut)
def get_project(project_id: str):
    log.info("project_get project_id=%s", project_id)
    p = project_get(project_id)
    if not p:
        raise HTTPException(status_code=404, detail="project not found")
    cnt = version_count_for_project(project_id)
    return ProjectOut(project_id=p["id"], name=p.get("name"), created_at=p["created_at"], version_count=cnt)
