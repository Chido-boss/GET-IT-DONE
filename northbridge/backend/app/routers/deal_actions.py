"""Deal actions — Express Interest, JV Interest, Request Deal Pack, Save/Unsave.
Behaviour tracking — views, paywall hits, unlock events.
"""
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select, func, update
from sqlalchemy.ext.asyncio import AsyncSession
from pydantic import BaseModel
from typing import Optional
from datetime import datetime, timedelta

from app.database import get_db
from app.auth.utils import get_current_user
from app.models.user import User
from app.models.deal_action import DealAction, DealView
from app.models.deal import Deal

router = APIRouter(prefix="/deal-actions", tags=["deal-actions"])


# ── Schemas ──────────────────────────────────────────────────────────────────

class ActionRequest(BaseModel):
    action_type: str  # express_interest | jv_interest | request_deal_pack | save | unsave
    notes: Optional[str] = None
    budget_confirmed: bool = False
    finance_type: Optional[str] = None  # cash | bridging | mortgage


class ViewEvent(BaseModel):
    deal_id: str
    session_id: Optional[str] = None
    duration_seconds: Optional[int] = None
    reached_paywall: bool = False
    unlocked: bool = False


class ActionOut(BaseModel):
    id: str
    deal_id: str
    action_type: str
    created_at: datetime

    class Config:
        from_attributes = True


class DealActivityOut(BaseModel):
    deal_id: str
    view_count: int
    unique_viewers: int
    interest_count: int
    jv_count: int
    pack_requests: int
    saves_count: int
    paywall_hits: int
    last_activity: Optional[datetime]
    activity_label: str   # "3 investors viewing" etc


# ── Endpoints ────────────────────────────────────────────────────────────────

@router.post("/{deal_id}/action", response_model=ActionOut)
async def submit_action(
    deal_id: str,
    body: ActionRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    # Verify deal exists
    deal = await db.get(Deal, deal_id)
    if not deal:
        raise HTTPException(status_code=404, detail="Deal not found")

    # Prevent duplicate saves
    if body.action_type in ("save", "unsave"):
        existing = await db.execute(
            select(DealAction).where(
                DealAction.deal_id == deal_id,
                DealAction.user_id == str(current_user.id),
                DealAction.action_type == "save",
            )
        )
        if body.action_type == "save" and existing.scalar_one_or_none():
            raise HTTPException(status_code=409, detail="Already saved")
        if body.action_type == "unsave":
            await db.execute(
                select(DealAction).where(
                    DealAction.deal_id == deal_id,
                    DealAction.user_id == str(current_user.id),
                    DealAction.action_type == "save",
                )
            )
            # Delete save record
            from sqlalchemy import delete
            await db.execute(
                delete(DealAction).where(
                    DealAction.deal_id == deal_id,
                    DealAction.user_id == str(current_user.id),
                    DealAction.action_type == "save",
                )
            )
            await db.commit()
            return ActionOut(id="deleted", deal_id=deal_id, action_type="unsave", created_at=datetime.utcnow())

    action = DealAction(
        deal_id=deal_id,
        user_id=str(current_user.id),
        action_type=body.action_type,
        notes=body.notes,
        budget_confirmed=body.budget_confirmed,
        finance_type=body.finance_type,
    )
    db.add(action)
    await db.commit()
    await db.refresh(action)
    return action


@router.post("/track-view")
async def track_view(
    body: ViewEvent,
    db: AsyncSession = Depends(get_db),
    current_user: Optional[User] = Depends(get_current_user),
):
    view = DealView(
        deal_id=body.deal_id,
        user_id=str(current_user.id) if current_user else None,
        session_id=body.session_id,
        duration_seconds=body.duration_seconds,
        reached_paywall=body.reached_paywall,
        unlocked=body.unlocked,
    )
    db.add(view)
    await db.commit()
    return {"ok": True}


@router.get("/{deal_id}/activity", response_model=DealActivityOut)
async def get_deal_activity(
    deal_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    # Views in last 7 days
    since = datetime.utcnow() - timedelta(days=7)

    view_count_result = await db.execute(
        select(func.count(DealView.id)).where(
            DealView.deal_id == deal_id,
            DealView.viewed_at >= since,
        )
    )
    view_count = view_count_result.scalar() or 0

    unique_viewers_result = await db.execute(
        select(func.count(func.distinct(DealView.user_id))).where(
            DealView.deal_id == deal_id,
            DealView.user_id.isnot(None),
            DealView.viewed_at >= since,
        )
    )
    unique_viewers = unique_viewers_result.scalar() or 0

    paywall_result = await db.execute(
        select(func.count(DealView.id)).where(
            DealView.deal_id == deal_id,
            DealView.reached_paywall == True,
            DealView.viewed_at >= since,
        )
    )
    paywall_hits = paywall_result.scalar() or 0

    async def count_actions(action_type: str) -> int:
        r = await db.execute(
            select(func.count(DealAction.id)).where(
                DealAction.deal_id == deal_id,
                DealAction.action_type == action_type,
            )
        )
        return r.scalar() or 0

    interest_count = await count_actions("express_interest")
    jv_count = await count_actions("jv_interest")
    pack_requests = await count_actions("request_deal_pack")
    saves_count = await count_actions("save")

    # Last activity
    last_view = await db.execute(
        select(DealView.viewed_at).where(DealView.deal_id == deal_id)
        .order_by(DealView.viewed_at.desc()).limit(1)
    )
    last_activity = last_view.scalar_one_or_none()

    # Activity label
    label = _activity_label(view_count, interest_count, jv_count, unique_viewers)

    return DealActivityOut(
        deal_id=deal_id,
        view_count=view_count,
        unique_viewers=unique_viewers,
        interest_count=interest_count,
        jv_count=jv_count,
        pack_requests=pack_requests,
        saves_count=saves_count,
        paywall_hits=paywall_hits,
        last_activity=last_activity,
        activity_label=label,
    )


@router.get("/{deal_id}/my-actions")
async def my_actions(
    deal_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    result = await db.execute(
        select(DealAction).where(
            DealAction.deal_id == deal_id,
            DealAction.user_id == str(current_user.id),
        )
    )
    actions = result.scalars().all()
    return {
        "saved": any(a.action_type == "save" for a in actions),
        "expressed_interest": any(a.action_type == "express_interest" for a in actions),
        "jv_interest": any(a.action_type == "jv_interest" for a in actions),
        "requested_pack": any(a.action_type == "request_deal_pack" for a in actions),
    }


def _activity_label(views: int, interest: int, jv: int, unique: int) -> str:
    if interest + jv >= 5:
        return f"🔥 High activity — {interest + jv} investors engaged"
    if interest >= 2:
        return f"⚡ {interest} investors expressed interest"
    if jv >= 1:
        return f"🤝 {jv} JV inquiry received"
    if unique >= 3:
        return f"👁 {unique} investors viewing this week"
    if views >= 5:
        return f"📊 {views} views this week"
    return "New listing"
