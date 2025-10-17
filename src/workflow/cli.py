import argparse
import json
from typing import Any, Dict, List

from src.workflow.interfaces import (
    TEXT_TO_IMAGE,
    SKETCH_TO_3D,
    FUSION_RANDOMIZE,
    REFINE_EDIT,
)
from src.workflow.runner import run_interface


def main(argv: List[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Workflow CLI wrapper for Ark image generation")
    parser.add_argument("--interface", required=True, choices=[TEXT_TO_IMAGE, SKETCH_TO_3D, FUSION_RANDOMIZE, REFINE_EDIT])
    parser.add_argument("--prompt-mode", required=True, choices=["template", "custom"])
    parser.add_argument("--template-key")
    parser.add_argument("--template-params", default="", help="JSON object of template params")
    parser.add_argument("--custom-prompt")

    parser.add_argument("--primary-image")
    parser.add_argument("--ref-images", nargs="*", default=[])

    parser.add_argument("--num-candidates", type=int, default=4)
    parser.add_argument("--concurrency", action="store_true")
    parser.add_argument("--max-workers", type=int, default=4)

    # Ark passthrough (same names as ark_image_cli)
    parser.add_argument("--model", default="doubao-seedream-4-0-250828")
    parser.add_argument("--size")
    parser.add_argument("--seed", type=int)
    parser.add_argument("--guidance-scale", type=float, dest="guidance_scale")
    parser.add_argument("--sequential-image-generation", dest="sequential_image_generation")
    parser.add_argument("--response-format", default=None, dest="response_format")
    parser.add_argument("--watermark", type=lambda x: str(x).lower() == "true")
    parser.add_argument("--output-dir", dest="output_dir")
    parser.add_argument("--timeout", type=int)
    parser.add_argument("--param", action="append", default=[])
    parser.add_argument("--json-params", dest="json_params")

    args = parser.parse_args(argv)

    tpl_params: Dict[str, Any] = {}
    if args.template_params:
        try:
            tpl_params = json.loads(args.template_params)
            if not isinstance(tpl_params, dict):
                raise ValueError("template-params must be a JSON object")
        except Exception as e:
            raise SystemExit(f"Invalid --template-params: {e}")

    ark_kwargs: Dict[str, Any] = {
        "size": args.size,
        "seed": args.seed,
        "guidance_scale": args.guidance_scale,
        "sequential_image_generation": args.sequential_image_generation,
        "response_format": args.response_format,
        "watermark": args.watermark,
        "output_dir": args.output_dir,
        "timeout": args.timeout,
        "param": args.param,
        "json_params": args.json_params,
    }

    return run_interface(
        interface_name=args.interface,
        prompt_mode=args.prompt_mode,
        template_key=args.template_key,
        template_params=tpl_params,
        custom_prompt=args.custom_prompt,
        model=args.model,
        primary_image=args.primary_image,
        ref_images=args.ref_images,
        num_candidates=args.num_candidates,
        concurrency=args.concurrency,
        max_workers=args.max_workers,
        ark_kwargs=ark_kwargs,
    )


if __name__ == "__main__":
    raise SystemExit(main())

