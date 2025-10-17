from __future__ import annotations

from typing import Any, List, Literal, Optional
from pydantic import BaseModel, Field, constr


UuidStr = constr(strip_whitespace=True, min_length=1)  # keep as string validation; DB stores string UUIDs


class ProjectCreate(BaseModel):
    name: Optional[str] = None


class ProjectOut(BaseModel):
    project_id: UuidStr
    name: Optional[str] = None
    created_at: str
    version_count: int


class VersionOutBrief(BaseModel):
    id: UuidStr
    index: int
    parent_version_id: Optional[UuidStr] = None
    interface_name: str
    created_at: str


class ImagePayload(BaseModel):
    base64: str
    mime: Literal["image/png", "image/jpeg"]


class SubmitVersionIn(BaseModel):
    image: ImagePayload
    interface_name: Literal["TextToImage", "SketchTo3D", "FusionRandomize", "RefineEdit"]
    base_version_id: Optional[UuidStr] = None
    # generation info stays out of DB per minimal schema; accepted but not stored
    prompt_mode: Optional[Literal["template", "custom"]] = None
    template_key: Optional[str] = None
    template_params: Optional[dict] = None
    custom_prompt: Optional[str] = None
    ark: Optional[dict] = None
    seed: Optional[int] = None


class SubmitVersionOut(BaseModel):
    project_id: UuidStr
    version: dict
    image: ImagePayload
    interface_name: str


class VersionDetailOut(BaseModel):
    id: UuidStr
    index: int
    parent_version_id: Optional[UuidStr] = None
    interface_name: str
    image: ImagePayload


class PromptTemplateParams(BaseModel):
    template_key: str
    template_params: dict


class PrimaryImage(BaseModel):
    base64: str
    mime: Optional[Literal["image/png", "image/jpeg"]] = "image/png"


class RefImage(BaseModel):
    base64: str
    mime: Optional[Literal["image/png", "image/jpeg"]] = "image/png"


class GenerateCommon(BaseModel):
    prompt_mode: Literal["template", "custom"]
    template_key: Optional[str] = None
    template_params: Optional[dict] = None
    custom_prompt: Optional[str] = None
    primary_image: Optional[PrimaryImage] = None
    ref_images: Optional[List[RefImage]] = None
    num_candidates: Optional[int] = 4
    ark: Optional[dict] = None


class CandidatesOut(BaseModel):
    candidates: List[ImagePayload]
    metadata: dict
