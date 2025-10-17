import os
from dataclasses import dataclass
from typing import Optional

try:
    import tomllib  # Python 3.11+
except Exception:  # pragma: no cover
    import tomli as tomllib  # type: ignore


@dataclass
class ArkConfig:
    base_url: str
    api_key: Optional[str]
    timeout: int = 60
    output_dir: str = "outputs"
    default_model: Optional[str] = None


def load_config(path: str = "config.toml") -> ArkConfig:
    data = {}
    if os.path.exists(path):
        with open(path, "rb") as f:
            data = tomllib.load(f)

    ark = data.get("ark", {})
    defaults = data.get("defaults", {})

    base_url = ark.get("base_url", "https://ark.cn-beijing.volces.com/api/v3")
    # Prefer config value; fallback to env ARK_API_KEY
    api_key = ark.get("api_key") or os.environ.get("ARK_API_KEY")
    # api_key = ark.get("api_key") or ""
    timeout = int(ark.get("timeout", 60))
    output_dir = defaults.get("output_dir", "outputs")
    default_model = defaults.get("model")

    return ArkConfig(
        base_url=base_url,
        api_key=api_key,
        timeout=timeout,
        output_dir=output_dir,
        default_model=default_model,
    )

