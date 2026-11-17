"""API «версії приймальника»: усе — лише в межах свого пункту."""
from __future__ import annotations

from fastapi import APIRouter, HTTPException

from app.modules.surplus import schemas as s
from app.modules.surplus import service
from app.modules.surplus.models import SurplusPoint
from app.shared.auth import CurrentPrincipal
from app.shared.database import SessionDep
from app.shared.i18n import L

router = APIRouter(prefix="/api/v1/receiver", tags=["receiver"])


async def _point(session, who) -> SurplusPoint:
    if who.role != "receiver":
        raise HTTPException(403, L("Це розділ приймальника", "Это раздел приёмщика"))
    p = await session.get(SurplusPoint, who.point_id)
    if p is None:
        raise HTTPException(404, L("Пункт не знайдено", "Пункт не найден"))
    return p


@router.get("/me", response_model=s.ReceiverMe)
async def me(session: SessionDep, who: CurrentPrincipal):
    p = await _point(session, who)
    bal = next((r for r in await service.receiver_balances(session) if r.receiver_name == p.receiver_name), None)
    return s.ReceiverMe(point_id=p.id, point_name=p.name, receiver_name=p.receiver_name, balance=bal)


@router.get("/submissions", response_model=list[s.SubmissionOut])
async def submissions(session: SessionDep, who: CurrentPrincipal):
    p = await _point(session, who)
    items = await service.list_shipments(session, point_id=p.id, status=None)
    return [service.submission_out(x) for x in items[:60]]


@router.post("/submissions", response_model=s.SubmissionOut, status_code=201)
async def create_submission(data: s.SubmissionIn, session: SessionDep, who: CurrentPrincipal):
    p = await _point(session, who)
    return service.submission_out(await service.save_submission(session, p, data))


@router.put("/submissions/{shipment_id}", response_model=s.SubmissionOut)
async def update_submission(shipment_id: int, data: s.SubmissionIn, session: SessionDep, who: CurrentPrincipal):
    p = await _point(session, who)
    return service.submission_out(await service.save_submission(session, p, data, shipment_id))


@router.delete("/submissions/{shipment_id}", status_code=204)
async def delete_submission(shipment_id: int, session: SessionDep, who: CurrentPrincipal):
    p = await _point(session, who)
    sh = await service.own_pending(session, p, shipment_id)
    await session.delete(sh)
    await session.commit()
