from __future__ import annotations

from typing import Dict, Any, List, Optional
import logging
from fastapi import APIRouter, HTTPException

from app.ark import generate_images
from app.schemas import CandidatesOut, GenerateCommon, ImagePayload

# Align validation and prompt/image handling with src workflow
from src.workflow.interfaces import SPECS, normalize_images
from src.workflow import templates as tpl


router = APIRouter(prefix="/api/projects/{project_id}/generate", tags=["generate"])
log = logging.getLogger("app.routes.generate")


def _expand_prompt(prompt_mode: str, template_key: Optional[str], template_params: Optional[Dict[str, Any]], custom_prompt: Optional[str]) -> str:
    if prompt_mode == "custom":
        if not custom_prompt:
            raise HTTPException(status_code=422, detail="custom_prompt required when prompt_mode=custom")
        return custom_prompt
    if prompt_mode == "template":
        if not template_key:
            raise HTTPException(status_code=422, detail="template_key required when prompt_mode=template")
        if template_key not in tpl.REGISTRY:
            raise HTTPException(status_code=422, detail=f"unknown template_key: {template_key}")
        spec = tpl.REGISTRY[template_key]
        params = template_params or {}
        missing = [k for k in spec.required_placeholders if k not in params]
        if missing:
            raise HTTPException(status_code=422, detail=f"missing template_params: {', '.join(missing)}")
        try:
            return spec.template.format(**params)
        except KeyError as ke:
            raise HTTPException(status_code=422, detail=f"template_params missing key: {ke}")
    raise HTTPException(status_code=422, detail="invalid prompt_mode")


def _to_data_url(image_base64: Optional[str], mime: Optional[str]) -> Optional[str]:
    if not image_base64:
        return None
    m = mime or "image/png"
    return f"data:{m};base64,{image_base64}"


def _prepare_images(interface_name: str, primary_base64: Optional[str], primary_mime: Optional[str], ref_items: Optional[List[ImagePayload]]) -> List[str]:
    primary_url = _to_data_url(primary_base64, primary_mime)
    ref_urls = [
        _to_data_url(r.base64, getattr(r, "mime", None))  # type: ignore[attr-defined]
        for r in (ref_items or [])
    ]
    # normalize_images enforces required primary and max ref limits
    try:
        return normalize_images(interface_name, primary_url, ref_urls)
    except ValueError as e:
        raise HTTPException(status_code=422, detail=str(e))


@router.post("/text-to-image", response_model=CandidatesOut)
def text_to_image(project_id: str, body: GenerateCommon):
    log.info(
        "text_to_image_enter project_id=%s prompt_mode=%s template_key=%s num_candidates=%s",
        project_id,
        body.prompt_mode,
        body.template_key,
        body.num_candidates,
    )
    # Build/validate prompt via workflow templates when in template mode
    prompt = _expand_prompt(body.prompt_mode, body.template_key, body.template_params, body.custom_prompt)
    imgs = generate_images(
        interface_name="TextToImage",
        prompt_mode=body.prompt_mode,
        custom_prompt=prompt if body.prompt_mode == "template" else body.custom_prompt,
        template_key=body.template_key,
        template_params=body.template_params,
        primary_image_base64=None,
        ref_images_base64=None,
        num_candidates=body.num_candidates or 4,
        ark=body.ark,
    )
    payloads = [ImagePayload(base64=i.base64, mime=i.mime) for i in imgs]
    meta: Dict = {
        "interface_name": "TextToImage",
        "prompt_mode": body.prompt_mode,
        "template_key": body.template_key,
        "template_params": body.template_params,
        "ark": body.ark or {},
    }
    log.info(
        "text_to_image_exit project_id=%s candidates=%s",
        project_id,
        len(payloads),
    )
    return CandidatesOut(candidates=payloads, metadata=meta)


@router.post("/sketch-to-3d", response_model=CandidatesOut)
def sketch_to_3d(project_id: str, body: GenerateCommon):
    log.info(
        "sketch_to_3d_enter project_id=%s prompt_mode=%s template_key=%s num_candidates=%s has_primary=%s ref_count=%s",
        project_id,
        body.prompt_mode,
        body.template_key,
        body.num_candidates,
        bool(body.primary_image),
        len(body.ref_images or []),
    )
    prompt = _expand_prompt(body.prompt_mode, body.template_key, body.template_params, body.custom_prompt)
    # Enforce primary presence and ref limits via workflow normalize_images
    images = _prepare_images(
        interface_name="SketchTo3D",
        primary_base64=body.primary_image.base64 if body.primary_image else None,
        primary_mime=body.primary_image.mime if body.primary_image else None,
        ref_items=body.ref_images,
    )
    imgs = generate_images(
        interface_name="SketchTo3D",
        prompt_mode=body.prompt_mode,
        custom_prompt=prompt if body.prompt_mode == "template" else body.custom_prompt,
        template_key=body.template_key,
        template_params=body.template_params,
        primary_image_base64=images[0] if images else None,
        ref_images_base64=images[1:] if images and len(images) > 1 else None,
        num_candidates=body.num_candidates or 4,
        ark=body.ark,
    )
    payloads = [ImagePayload(base64=i.base64, mime=i.mime) for i in imgs]
    meta: Dict = {
        "interface_name": "SketchTo3D",
        "prompt_mode": body.prompt_mode,
        "template_key": body.template_key,
        "template_params": body.template_params,
        "ark": body.ark or {},
    }
    log.info(
        "sketch_to_3d_exit project_id=%s candidates=%s",
        project_id,
        len(payloads),
    )
    return CandidatesOut(candidates=payloads, metadata=meta)


@router.post("/fusion-randomize", response_model=CandidatesOut)
def fusion_randomize(project_id: str, body: GenerateCommon):
    log.info(
        "fusion_randomize_enter project_id=%s prompt_mode=%s template_key=%s num_candidates=%s has_primary=%s ref_count=%s",
        project_id,
        body.prompt_mode,
        body.template_key,
        body.num_candidates,
        bool(body.primary_image),
        len(body.ref_images or []),
    )
    prompt = _expand_prompt(body.prompt_mode, body.template_key, body.template_params, body.custom_prompt) if body.prompt_mode else None
    images = _prepare_images(
        interface_name="FusionRandomize",
        primary_base64=body.primary_image.base64 if body.primary_image else None,
        primary_mime=body.primary_image.mime if body.primary_image else None,
        ref_items=body.ref_images,
    )
    imgs = generate_images(
        interface_name="FusionRandomize",
        prompt_mode=body.prompt_mode,
        custom_prompt=prompt if body.prompt_mode == "template" else body.custom_prompt,
        template_key=body.template_key,
        template_params=body.template_params,
        primary_image_base64=images[0] if images else None,
        ref_images_base64=images[1:] if images and len(images) > 1 else None,
        num_candidates=body.num_candidates or 4,
        ark=body.ark,
    )
    payloads = [ImagePayload(base64=i.base64, mime=i.mime) for i in imgs]
    meta: Dict = {
        "interface_name": "FusionRandomize",
        "prompt_mode": body.prompt_mode,
        "template_key": body.template_key,
        "template_params": body.template_params,
        "ark": body.ark or {},
    }
    log.info(
        "fusion_randomize_exit project_id=%s candidates=%s",
        project_id,
        len(payloads),
    )
    return CandidatesOut(candidates=payloads, metadata=meta)


@router.post("/refine-edit", response_model=CandidatesOut)
def refine_edit(project_id: str, body: GenerateCommon):
    log.info(
        "refine_edit_enter project_id=%s prompt_mode=%s template_key=%s num_candidates=%s has_primary=%s ref_count=%s",
        project_id,
        body.prompt_mode,
        body.template_key,
        body.num_candidates,
        bool(body.primary_image),
        len(body.ref_images or []),
    )
    prompt = _expand_prompt(body.prompt_mode, body.template_key, body.template_params, body.custom_prompt)
    images = _prepare_images(
        interface_name="RefineEdit",
        primary_base64=body.primary_image.base64 if body.primary_image else None,
        primary_mime=body.primary_image.mime if body.primary_image else None,
        ref_items=body.ref_images,
    )
    imgs = generate_images(
        interface_name="RefineEdit",
        prompt_mode=body.prompt_mode,
        custom_prompt=prompt if body.prompt_mode == "template" else body.custom_prompt,
        template_key=body.template_key,
        template_params=body.template_params,
        primary_image_base64=images[0] if images else None,
        ref_images_base64=images[1:] if images and len(images) > 1 else None,
        num_candidates=body.num_candidates or 4,
        ark=body.ark,
    )
    payloads = [ImagePayload(base64=i.base64, mime=i.mime) for i in imgs]
    meta: Dict = {
        "interface_name": "RefineEdit",
        "prompt_mode": body.prompt_mode,
        "template_key": body.template_key,
        "template_params": body.template_params,
        "ark": body.ark or {},
    }
    log.info(
        "refine_edit_exit project_id=%s candidates=%s",
        project_id,
        len(payloads),
    )
    return CandidatesOut(candidates=payloads, metadata=meta)
