from dataclasses import dataclass
from typing import Dict, List, Optional


# Interface name constants
TEXT_TO_IMAGE = "TextToImage"
SKETCH_TO_3D = "SketchTo3D"
FUSION_RANDOMIZE = "FusionRandomize"
REFINE_EDIT = "RefineEdit"


@dataclass(frozen=True)
class InterfaceSpec:
    name: str
    requires_primary: bool
    allow_ref_max: int
    prompt_required: bool
    seed_policy: str  # "fixed" | "varying"


SPECS: Dict[str, InterfaceSpec] = {
    TEXT_TO_IMAGE: InterfaceSpec(
        name=TEXT_TO_IMAGE,
        requires_primary=False,
        allow_ref_max=0,
        prompt_required=True,
        seed_policy="fixed",
    ),
    SKETCH_TO_3D: InterfaceSpec(
        name=SKETCH_TO_3D,
        requires_primary=True,
        allow_ref_max=0,
        prompt_required=True,
        seed_policy="fixed",
    ),
    FUSION_RANDOMIZE: InterfaceSpec(
        name=FUSION_RANDOMIZE,
        requires_primary=True,
        allow_ref_max=2,
        prompt_required=False,
        seed_policy="varying",
    ),
    REFINE_EDIT: InterfaceSpec(
        name=REFINE_EDIT,
        requires_primary=True,
        allow_ref_max=2,
        prompt_required=True,
        seed_policy="fixed",
    ),
}


def normalize_images(
    interface_name: str, primary_image: Optional[str], ref_images: Optional[List[str]]
) -> List[str]:
    spec = SPECS[interface_name]
    refs = (ref_images or [])[: max(0, spec.allow_ref_max)]
    if spec.requires_primary:
        if not primary_image:
            raise ValueError(f"{interface_name} requires primary_image")
        return [primary_image, *refs]
    # no images for text-to-image
    return []

