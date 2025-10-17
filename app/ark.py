from __future__ import annotations

import base64
from dataclasses import dataclass
import logging
import json
import os
import random
from typing import Any, Dict, List, Optional

from app.config import settings

log = logging.getLogger("app.ark")


@dataclass
class GeneratedImage:
    base64: str
    mime: str = "image/png"


def generate_images(
    interface_name: str,
    prompt_mode: Optional[str],
    custom_prompt: Optional[str],
    template_key: Optional[str],
    template_params: Optional[dict],
    primary_image_base64: Optional[str],
    ref_images_base64: Optional[list[str]],
    num_candidates: int = 4,
    ark: Optional[dict] = None,
) -> List[GeneratedImage]:
    """
    Adapter for image generation. Always uses real Ark API via official SDK.
    """

    # Real Ark integration via official SDK.
    # Lazily import so tests/dev do not require the dependency.
    try:
        from volcenginesdkarkruntime import Ark  # type: ignore
    except Exception as e:  # pragma: no cover
        raise RuntimeError(
            "Ark SDK not available. Install with: pip install 'volcengine-python-sdk[ark]'"
        ) from e

    # Build Ark client
    base_url = settings.ark_base_url or os.getenv("ARK_BASE_URL") or "https://ark.cn-beijing.volces.com/api/v3"
    api_key = settings.ark_api_key or os.getenv("ARK_API_KEY")
    if not api_key:
        raise RuntimeError("Missing ARK_API_KEY (or config.ark_api_key)")
    client = Ark(base_url=base_url, api_key=api_key)

    # Final prompt is provided by routes (custom_prompt already expanded for template mode)
    if not custom_prompt:
        raise ValueError("custom_prompt is required after prompt expansion")

    # Prepare image(s) as data URLs. Default mime to image/png
    def _as_data_url(b64: str, mime: str = "image/png") -> str:
        return f"data:{mime};base64,{b64}"

    images: List[str] = []
    if primary_image_base64:
        images.append(_as_data_url(primary_image_base64))
    if ref_images_base64:
        images.extend([_as_data_url(b) for b in ref_images_base64[:2]])

    # Ark kwargs with defaults per docs/spec
    ark_kwargs: Dict[str, Any] = dict(ark or {})
    if "size" not in ark_kwargs or ark_kwargs.get("size") in (None, ""):
        ark_kwargs["size"] = "4K"
    if (
        "sequential_image_generation" not in ark_kwargs
        or ark_kwargs.get("sequential_image_generation") in (None, "")
    ):
        ark_kwargs["sequential_image_generation"] = "disabled"
    if "response_format" not in ark_kwargs or ark_kwargs.get("response_format") in (None, ""):
        ark_kwargs["response_format"] = "url"
    if "watermark" not in ark_kwargs or ark_kwargs.get("watermark") is None:
        ark_kwargs["watermark"] = False

    # Base payload with only documented fields
    model = ark_kwargs.pop("model", None) or "doubao-seedream-4-0-250828"
    base_payload: Dict[str, Any] = {
        "model": model,
        "prompt": custom_prompt,
        "response_format": ark_kwargs.get("response_format"),
        "watermark": ark_kwargs.get("watermark"),
    }
    # Attach size/seed/guidance_scale/sequential_image_generation when provided
    for k in ("size", "seed", "guidance_scale", "sequential_image_generation"):
        if k in ark_kwargs and ark_kwargs[k] is not None:
            base_payload[k] = ark_kwargs[k]

    # Attach images (Seedream accepts list). For seededit i2i models, backend will accept a single image.
    if images:
        base_payload["image"] = images

    # Extra params passthrough (only documented fields should be used)
    # Support `param: ["k=v", ...]` and `json_params: "{...}"`
    try:
        from src.ark_image_cli import _parse_param_overrides  # reuse logic
    except Exception:
        _parse_param_overrides = None  # type: ignore

    params_list = ark_kwargs.get("param", []) or []
    if params_list and _parse_param_overrides:
        base_payload.update(_parse_param_overrides(params_list))  # type: ignore
    json_params = ark_kwargs.get("json_params")
    if json_params:
        try:
            base_payload.update(json.loads(json_params) if isinstance(json_params, str) else dict(json_params))
        except Exception as e:
            raise ValueError(f"invalid ark.json_params: {e}")

    # Seed policy: FusionRandomize uses varying seeds if not provided
    spec_varying_seed = interface_name == "FusionRandomize"
    provided_seed = base_payload.get("seed")

    results: List[GeneratedImage] = []

    # Log sanitized payload (no image data, no api_key)
    try:
        log.info(
            "ark_generate_call interface=%s model=%s prompt_len=%s images=%s size=%s response_format=%s wmark=%s vary_seed=%s num_candidates=%s",
            interface_name,
            base_payload.get("model"),
            len(base_payload.get("prompt") or ""),
            len(images),
            base_payload.get("size"),
            base_payload.get("response_format"),
            base_payload.get("watermark"),
            spec_varying_seed,
            num_candidates,
        )
    except Exception:
        pass

    def _resp_to_images(resp_obj: Any) -> List[GeneratedImage]:
        out: List[GeneratedImage] = []
        # Attempt generic dict conversion
        try:
            resp_dict = json.loads(json.dumps(resp_obj, default=lambda o: o.__dict__))
        except Exception:
            resp_dict = {"repr": str(resp_obj)}
        data_list = resp_dict.get("data") or []
        # Prefer direct base64 when present; otherwise, fetch URL
        for item in data_list:
            if isinstance(item, dict):
                b64 = item.get("b64_json") or item.get("base64") or item.get("image_base64")
                if b64:
                    out.append(GeneratedImage(base64=b64, mime="image/png"))
                    continue
                url = item.get("url")
            else:
                # object with attributes
                b64 = getattr(item, "b64_json", None) or getattr(item, "base64", None) or getattr(item, "image_base64", None)
                if b64:
                    out.append(GeneratedImage(base64=b64, mime="image/png"))
                    continue
                url = getattr(item, "url", None)
            if url and str(url).lower().startswith("http"):
                try:
                    import httpx  # type: ignore

                    with httpx.Client(timeout=30.0) as client:
                        r = client.get(url)
                        r.raise_for_status()
                        b64 = base64.b64encode(r.content).decode("ascii")
                        out.append(GeneratedImage(base64=b64, mime="image/png"))
                except Exception as de:  # pragma: no cover
                    raise RuntimeError(f"failed to download image: {de}")
        return out

    # Perform parallel calls until enough candidates collected
    attempts = max(1, int(num_candidates))
    max_workers_env = os.getenv("ARK_MAX_WORKERS")
    try:
        max_workers = int(max_workers_env) if max_workers_env else None
    except ValueError:
        max_workers = None
    workers = max(1, min(attempts, max_workers or 4))

    from concurrent.futures import ThreadPoolExecutor, as_completed

    def _call_once(seed_override: Optional[int]) -> List[GeneratedImage]:
        payload = dict(base_payload)
        if seed_override is not None:
            payload["seed"] = seed_override
        try:
            resp = client.images.generate(**payload)
        except Exception as e:  # pragma: no cover
            log.warning("ark_generate_error interface=%s error=%s", interface_name, e)
            # surface as empty set so aggregation can continue
            return []
        return _resp_to_images(resp)

    futures = []
    with ThreadPoolExecutor(max_workers=workers) as ex:
        for i in range(attempts):
            seed_override = None
            if spec_varying_seed and provided_seed is None:
                seed_override = random.randint(1, 2**31 - 1)
            futures.append(ex.submit(_call_once, seed_override))
        for fu in as_completed(futures):
            try:
                imgs = fu.result()
            except Exception:
                imgs = []
            for img in imgs:
                results.append(img)
                if len(results) >= num_candidates:
                    break
            if len(results) >= num_candidates:
                break

    # Ensure at least one image when API returned empty list
    if not results:
        log.error("ark_generate_no_images interface=%s", interface_name)
        raise RuntimeError("Ark returned no images")
    return results[: max(1, num_candidates)]
