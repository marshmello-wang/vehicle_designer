import json
import random
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Any, Dict, List, Optional, Tuple

from src.workflow.interfaces import SPECS, normalize_images
from src.workflow import templates as tpl
from src import ark_image_cli


def _expand_prompt(prompt_mode: str, template_key: Optional[str], template_params: Dict[str, Any], custom_prompt: Optional[str]) -> str:
    if prompt_mode == "custom":
        if not custom_prompt:
            raise ValueError("custom prompt_mode requires --custom-prompt")
        return custom_prompt
    if not template_key:
        raise ValueError("template prompt_mode requires --template-key")
    if template_key not in tpl.REGISTRY:
        raise ValueError(f"unknown template_key: {template_key}")
    spec = tpl.REGISTRY[template_key]
    # Validate required placeholders
    missing = [k for k in spec.required_placeholders if k not in template_params]
    if missing:
        raise ValueError(f"missing template_params: {', '.join(missing)}")
    try:
        return spec.template.format(**template_params)
    except KeyError as ke:
        raise ValueError(f"template_params missing key: {ke}")


def _build_ark_argv(
    model: str,
    prompt: str,
    images: List[str],
    ark_kwargs: Dict[str, Any],
    count: int,
) -> List[str]:
    argv: List[str] = [
        "--model",
        model,
        "--prompt",
        prompt,
    ]
    if images:
        argv.append("--images")
        argv.extend(images)

    # Defaults per S10-P0-2 (apply when missing or None/empty)
    if "size" not in ark_kwargs or ark_kwargs.get("size") in (None, ""):
        ark_kwargs["size"] = "4K"
    if (
        "sequential_image_generation" not in ark_kwargs
        or ark_kwargs.get("sequential_image_generation") in (None, "")
    ):
        ark_kwargs["sequential_image_generation"] = "disabled"  # conceptual false
    if "response_format" not in ark_kwargs or ark_kwargs.get("response_format") in (None, ""):
        ark_kwargs["response_format"] = "url"
    if "watermark" not in ark_kwargs or ark_kwargs.get("watermark") is None:
        ark_kwargs["watermark"] = False

    # Known mapped args
    for k in ["size", "seed", "guidance_scale", "sequential_image_generation", "response_format", "watermark", "output_dir", "timeout"]:
        if k in ark_kwargs and ark_kwargs[k] is not None:
            flag = f"--{k.replace('_', '-')}"
            argv.extend([flag, str(ark_kwargs[k])])

    # Extra passthrough
    extra_params: List[str] = ark_kwargs.get("param", []) or []
    for p in extra_params:
        argv.extend(["--param", p])
    if ark_kwargs.get("json_params"):
        argv.extend(["--json-params", str(ark_kwargs["json_params"])])

    argv.extend(["--count", str(max(1, int(count)))])
    return argv


def run_interface(
    interface_name: str,
    prompt_mode: str,
    template_key: Optional[str],
    template_params: Dict[str, Any],
    custom_prompt: Optional[str],
    model: str,
    primary_image: Optional[str],
    ref_images: Optional[List[str]],
    num_candidates: int = 4,
    concurrency: bool = False,
    max_workers: int = 4,
    ark_kwargs: Optional[Dict[str, Any]] = None,
) -> int:
    if interface_name not in SPECS:
        raise ValueError(f"unknown interface: {interface_name}")

    images = normalize_images(interface_name, primary_image, ref_images)
    prompt = _expand_prompt(prompt_mode, template_key, template_params or {}, custom_prompt)

    # Seed policy handling
    spec = SPECS[interface_name]
    base_ark = dict(ark_kwargs or {})
    provided_seed = base_ark.get("seed")

    if not concurrency:
        # Simpler path: one call with --count
        argv = _build_ark_argv(model, prompt, images, base_ark, num_candidates)
        return ark_image_cli.main(argv)

    # Concurrency path: multiple calls with --count 1
    workers = max(1, min(max_workers, num_candidates))
    results: List[int] = []
    with ThreadPoolExecutor(max_workers=workers) as ex:
        futs = []
        for i in range(num_candidates):
            call_kwargs = dict(base_ark)
            if spec.seed_policy == "varying":
                # assign different seed per call if not provided
                if provided_seed is None:
                    call_kwargs["seed"] = random.randint(1, 2**31 - 1)
            argv = _build_ark_argv(model, prompt, images, call_kwargs, 1)
            futs.append(ex.submit(ark_image_cli.main, argv))
        for fu in as_completed(futs):
            try:
                results.append(int(fu.result()))
            except Exception:
                results.append(1)
    # Return 0 if any succeeded
    return 0 if any(r == 0 for r in results) else 1
