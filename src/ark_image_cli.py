import argparse
import base64
import json
import mimetypes
import os
import sys
import time
from datetime import datetime
from typing import Any, Dict, List, Tuple

from src.config import load_config


def _parse_param_overrides(param_list: List[str]) -> Dict[str, Any]:
    overrides: Dict[str, Any] = {}
    for item in param_list:
        if "=" not in item:
            raise ValueError(f"Invalid --param '{item}', expected key=value")
        k, v = item.split("=", 1)
        v = v.strip()
        # attempt simple typing: bool/int/float/str
        if v.lower() in ("true", "false"):
            overrides[k] = v.lower() == "true"
        else:
            try:
                if "." in v:
                    overrides[k] = float(v)
                else:
                    overrides[k] = int(v)
            except ValueError:
                overrides[k] = v
    return overrides


def _now_stamp() -> str:
    return datetime.utcnow().strftime("%Y%m%dT%H%M%SZ")


def _ensure_dir(path: str) -> None:
    os.makedirs(path, exist_ok=True)


def _split_image_and_weight(items: List[str]) -> Tuple[List[str], List[float]]:
    paths: List[str] = []
    weights: List[float] = []
    for item in items[:3]:  # max 3
        # Only treat trailing :weight when it looks like a local path, not a URL
        if ":" in item and not item.lower().startswith("http"):
            p, w = item.rsplit(":", 1)
            try:
                weights.append(float(w))
                paths.append(p)
            except ValueError:
                paths.append(item)
        else:
            paths.append(item)
    return paths, weights


def _file_to_data_url(path: str) -> str:
    mime, _ = mimetypes.guess_type(path)
    if not mime:
        # default to png to be safe if unknown
        mime = "image/png"
    with open(path, "rb") as f:
        b64 = base64.b64encode(f.read()).decode("ascii")
    return f"data:{mime};base64,{b64}"


def main(argv: List[str]) -> int:
    parser = argparse.ArgumentParser(description="Ark image CLI for Seedream/Seededit")
    parser.add_argument("--model", type=str, help="Model ID to use")
    parser.add_argument("--prompt", type=str, required=True, help="Text prompt")
    parser.add_argument(
        "--images",
        nargs="*",
        default=[],
        help="Up to 3 local image paths. Optional weight: path[:weight]",
    )
    parser.add_argument(
        "--source-index",
        type=int,
        default=0,
        help="For seededit i2i: which image is source (index in --images)",
    )
    # Only include parameters that appear in docs/examples
    parser.add_argument("--size", type=str, help="API 'size' field, e.g. '2K' or 'adaptive'")
    parser.add_argument("--seed", type=int, help="API 'seed' field")
    parser.add_argument("--guidance-scale", type=float, dest="guidance_scale", help="API 'guidance_scale' field")
    parser.add_argument(
        "--sequential-image-generation",
        type=str,
        dest="sequential_image_generation",
        help="API 'sequential_image_generation' field (Seedream)",
    )
    parser.add_argument(
        "--response-format",
        type=str,
        default="url",
        dest="response_format",
        help="API 'response_format' field (default: url)",
    )
    parser.add_argument(
        "--watermark",
        type=lambda x: str(x).lower() == "true",
        default=True,
        help="API 'watermark' field: true/false",
    )
    parser.add_argument("--count", type=int, default=1, help="Repeat calls client-side to get multiple results (default 1)")
    parser.add_argument("--output-dir", type=str, help="Output directory (default from config)")
    parser.add_argument("--timeout", type=int, help="HTTP timeout seconds (default from config)")
    parser.add_argument(
        "--param",
        action="append",
        default=[],
        help="Extra API params as key=value; repeatable (only pass documented fields)",
    )
    parser.add_argument("--json-params", type=str, default="", help="Extra API params as JSON string (documented fields only)")

    args = parser.parse_args(argv)

    # Load config
    cfg = load_config()
    if not cfg.api_key:
        print("Missing API key. Set in config.toml [ark].api_key or env ARK_API_KEY.", file=sys.stderr)
        return 2

    output_dir = args.output_dir or cfg.output_dir
    _ensure_dir(output_dir)

    # Ark SDK
    try:
        from volcenginesdkarkruntime import Ark
    except Exception as e:  # pragma: no cover
        print(
            "Failed to import Ark SDK: install with pip install 'volcengine-python-sdk[ark]'. Error: " + str(e),
            file=sys.stderr,
        )
        return 2

    client = Ark(base_url=cfg.base_url, api_key=cfg.api_key)

    model = args.model or cfg.default_model or "doubao-seedream-4-0-250828"

    # Prepare images & potential weights
    img_paths, weights = _split_image_and_weight(args.images)
    for p in img_paths:
        if not os.path.exists(p):
            print(f"Image not found: {p}", file=sys.stderr)
            return 2

    # Build payload using only documented fields
    payload: Dict[str, Any] = {
        "model": model,
        "prompt": args.prompt,
        "response_format": args.response_format,
        "watermark": args.watermark,
    }
    if args.size:
        payload["size"] = args.size
    if args.seed is not None:
        payload["seed"] = args.seed
    if args.guidance_scale is not None:
        payload["guidance_scale"] = args.guidance_scale
    if args.sequential_image_generation:
        payload["sequential_image_generation"] = args.sequential_image_generation

    # Dynamic extra params (user must ensure they are documented)
    try:
        payload.update(_parse_param_overrides(args.param))
    except ValueError as ve:
        print(str(ve), file=sys.stderr)
        return 2
    if args.json_params:
        try:
            payload.update(json.loads(args.json_params))
        except Exception as e:
            print(f"Invalid --json-params: {e}", file=sys.stderr)
            return 2

    # Attach image(s) as data URLs
    data_urls: List[str] = [_file_to_data_url(p) for p in img_paths]
    if model.startswith("doubao-seededit-3-0-i2i"):
        # Seededit: accept single image (source). If multiple provided, take source-index only.
        if data_urls:
            idx = max(0, min(args.source_index, len(data_urls) - 1))
            payload["image"] = data_urls[idx]
            if len(data_urls) > 1:
                print("Seededit i2i takes single source image; extra images ignored.", file=sys.stderr)
    else:
        # Seedream: multi-image supported as per doc example
        if data_urls:
            payload["image"] = data_urls

    # Metadata common fields
    run_id = f"{_now_stamp()}_{int(time.time()*1000)%1000000}"
    meta: Dict[str, Any] = {
        "run_id": run_id,
        "timestamp": _now_stamp(),
        "model": model,
        "input": {
            "prompt": args.prompt,
            "images": img_paths,  # record local file names only
            "weights": weights,
        },
        "request_payload_preview": {k: ("<data_url_list>" if k == "image" and isinstance(v, list) else ("<data_url>" if k == "image" else v)) for k, v in payload.items()},
        "responses": [],
        "outputs": [],
    }

    # Perform calls
    errors = 0
    for i in range(max(1, args.count)):
        try:
            resp = client.images.generate(**payload)
        except Exception as e:
            errors += 1
            print(f"Request failed ({i+1}/{args.count}): {e}", file=sys.stderr)
            continue

        # Try to serialize response to dict
        try:
            resp_dict = json.loads(json.dumps(resp, default=lambda o: o.__dict__))
        except Exception:
            resp_dict = {"repr": str(resp)}

        meta["responses"].append(resp_dict)

        # Save outputs (download URLs if present)
        try:
            data_list = getattr(resp, "data", None) or resp_dict.get("data", [])
            for j, item in enumerate(data_list):
                url = getattr(item, "url", None) if hasattr(item, "url") else item.get("url")
                size = getattr(item, "size", None) if hasattr(item, "size") else item.get("size")
                if url and str(url).lower().startswith("http"):
                    fname = f"{run_id}_{i+1}_{j+1}.png"
                    out_path = os.path.join(output_dir, fname)
                    try:
                        # Download if possible; if blocked, still record URL
                        try:
                            import requests  # type: ignore

                            with requests.get(url, timeout=cfg.timeout, stream=True) as r:
                                r.raise_for_status()
                                with open(out_path, "wb") as f:
                                    for chunk in r.iter_content(chunk_size=8192):
                                        if chunk:
                                            f.write(chunk)
                            meta["outputs"].append({"file": out_path, "size": size, "source_url": url})
                        except Exception as de:
                            meta["outputs"].append({"url": url, "size": size, "download_error": str(de)})
                    except Exception as e:
                        meta["outputs"].append({"url": url, "size": size, "download_error": str(e)})
                else:
                    # If API returns non-URL content, just record as-is
                    meta["outputs"].append(item)
        except Exception as e:
            meta["outputs"].append({"error": f"failed to parse outputs: {e}"})

    # Write metadata
    meta_path = os.path.join(output_dir, f"{run_id}_metadata.json")
    with open(meta_path, "w", encoding="utf-8") as f:
        json.dump(meta, f, ensure_ascii=False, indent=2)

    if errors and errors == args.count:
        print("All requests failed. See metadata for details.", file=sys.stderr)
        return 1

    print(f"Done. Metadata written: {meta_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))

