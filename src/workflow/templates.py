from dataclasses import dataclass
from typing import Dict, List


@dataclass(frozen=True)
class TemplateSpec:
    key: str
    interface_name: str
    template: str  # Python format string with placeholders only
    required_placeholders: List[str]


# Minimal placeholder-only templates. Content will be finalized later by product.
REGISTRY: Dict[str, TemplateSpec] = {
    # 0) TextToImage
    "text_to_image_v1": TemplateSpec(
        key="text_to_image_v1",
        interface_name="TextToImage",
        template="{brand} {style_adjectives} {colorway} {lighting} {era} {notes} {negative}",
        required_placeholders=[
            "brand",
            "style_adjectives",
            "colorway",
            "lighting",
            "era",
        ],
    ),
    # 1) SketchTo3D
    "sketch_to_3d_v1": TemplateSpec(
        key="sketch_to_3d_v1",
        interface_name="SketchTo3D",
        template="{brand} {style_adjectives} {colorway} {lighting} {era} {notes} {negative}",
        required_placeholders=[
            "brand",
            "style_adjectives",
            "colorway",
        ],
    ),
    # 2) FusionRandomize
    "fusion_randomize_v1": TemplateSpec(
        key="fusion_randomize_v1",
        interface_name="FusionRandomize",
        template="{brand} {style_adjectives} {colorway} {lighting} {era} {blend_notes} {negative}",
        required_placeholders=[
            "brand",
            "style_adjectives",
        ],
    ),
    # 3) RefineEdit
    "refine_edit_v1": TemplateSpec(
        key="refine_edit_v1",
        interface_name="RefineEdit",
        template="{brand} {style_adjectives} {colorway} {lighting} {era} {edit_instructions} {negative}",
        required_placeholders=[
            "edit_instructions",
        ],
    ),
}

