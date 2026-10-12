from typing import Literal

from pydantic import BaseModel

from app.models.platform import PlatformName

AssetType = Literal[
    "publication_preview",
    "source_visual",
    "generated_explainer",
    "programme_card",
    "generated_education_visual",
    "user_upload",
]


class AssetRequest(BaseModel):
    platforms: list[PlatformName]


class MainAssetRequest(BaseModel):
    asset_id: str


class VisualAsset(BaseModel):
    id: str
    type: AssetType
    label: str
    source: Literal["document", "local", "generated", "user", "web"]
    path: str
    recommended: bool = False


class AssetPack(BaseModel):
    document_family: Literal["research", "curriculum"]
    assets: list[VisualAsset]
    recommended_asset_id: str | None
    main_asset_id: str | None
    main_is_manual: bool = False
    image_attempted: bool = False
    image_error: str | None = None
