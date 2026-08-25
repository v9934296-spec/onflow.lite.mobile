"""Read-only canonical trick registry (BE-005).

The launch client must not keep a second catalog. This endpoint is the HTTP
surface for ``app.services.trick_registry`` so trick identity stays one source.
"""

from __future__ import annotations

from pydantic import BaseModel, Field
from fastapi import APIRouter, Depends

from app.core.auth import get_current_user
from app.services.trick_registry import TRICK_REGISTRY

router = APIRouter(prefix="/api/v1", tags=["tricks"])


class TrickOut(BaseModel):
    id: str = Field(description="Stable trick_id: lowercase canonical name.")
    name: str
    category: str
    aliases: list[str] = Field(default_factory=list)
    difficulty_tier: int
    rotation: str | None = None


class TrickListResponse(BaseModel):
    tricks: list[TrickOut]


@router.get("/tricks", response_model=TrickListResponse)
def list_tricks(_user_id: str = Depends(get_current_user)) -> TrickListResponse:
    items = [
        TrickOut(
            id=entry.name.strip().lower(),
            name=entry.name,
            category=entry.category,
            aliases=list(entry.aliases),
            difficulty_tier=entry.difficulty_tier,
            rotation=entry.rotation,
        )
        for entry in TRICK_REGISTRY
    ]
    items.sort(key=lambda t: (t.category, t.difficulty_tier, t.name.lower()))
    return TrickListResponse(tricks=items)
