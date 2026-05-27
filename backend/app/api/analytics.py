"""Analytics endpoint."""
from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import session_dep
from app.schemas.analytics import AnalyticsResponse
from app.services.analytics import compute_analytics

router = APIRouter(tags=["analytics"])


@router.get("/analytics", response_model=AnalyticsResponse)
async def analytics(
    session: AsyncSession = Depends(session_dep),
) -> AnalyticsResponse:
    data = await compute_analytics(session)
    return AnalyticsResponse(**data)
