from __future__ import annotations

from datetime import date

from fastapi import APIRouter, Response

from app.modules.surplus import schemas as s
from app.modules.surplus import service
from app.modules.surplus.export import build_xlsx
from app.shared.database import SessionDep

router = APIRouter(prefix="/api/v1/surplus", tags=["surplus"])


@router.get("/points", response_model=list[s.PointOut])
async def points(session: SessionDep):
    return await service.list_points(session)


@router.post("/points", response_model=s.PointOut, status_code=201)
async def create_point(data: s.PointIn, session: SessionDep):
    return await service.save_point(session, data)


@router.put("/points/{point_id}", response_model=s.PointOut)
async def update_point(point_id: int, data: s.PointIn, session: SessionDep):
    return await service.save_point(session, data, point_id)


@router.get("/materials", response_model=list[s.MaterialOut])
async def materials(session: SessionDep):
    return await service.list_materials(session)


@router.post("/materials", response_model=s.MaterialOut, status_code=201)
async def create_material(data: s.MaterialIn, session: SessionDep):
    return await service.save_material(session, data)


@router.put("/materials/{material_id}", response_model=s.MaterialOut)
async def update_material(material_id: int, data: s.MaterialIn, session: SessionDep):
    return await service.save_material(session, data, material_id)


@router.get("/shipments", response_model=list[s.ShipmentListItem])
async def shipments(
    session: SessionDep,
    date_from: date | None = None,
    date_to: date | None = None,
    point_id: int | None = None,
    receiver: str | None = None,
):
    items = await service.list_shipments(session, date_from, date_to, point_id, receiver)
    out = []
    for sh in items:
        full = service.shipment_out(sh)
        out.append(s.ShipmentListItem(**full.model_dump(exclude={"lines", "note"}), lines_count=len(full.lines)))
    return out


@router.post("/shipments", response_model=s.ShipmentOut, status_code=201)
async def create_shipment(data: s.ShipmentIn, session: SessionDep):
    return service.shipment_out(await service.save_shipment(session, data))


@router.get("/shipments/{shipment_id}", response_model=s.ShipmentOut)
async def get_shipment(shipment_id: int, session: SessionDep):
    return service.shipment_out(await service.get_shipment(session, shipment_id))


@router.put("/shipments/{shipment_id}", response_model=s.ShipmentOut)
async def update_shipment(shipment_id: int, data: s.ShipmentIn, session: SessionDep):
    return service.shipment_out(await service.save_shipment(session, data, shipment_id))


@router.delete("/shipments/{shipment_id}", status_code=204)
async def delete_shipment(shipment_id: int, session: SessionDep):
    await service.delete_shipment(session, shipment_id)


@router.get("/settlements", response_model=list[s.SettlementOut])
async def settlements(session: SessionDep, receiver: str | None = None):
    return [service.settlement_out(x) for x in await service.list_settlements(session, receiver)]


@router.post("/settlements", response_model=s.SettlementOut, status_code=201)
async def create_settlement(data: s.SettlementIn, session: SessionDep):
    return service.settlement_out(await service.create_settlement(session, data))


@router.delete("/settlements/{settlement_id}", status_code=204)
async def delete_settlement(settlement_id: int, session: SessionDep):
    await service.delete_settlement(session, settlement_id)


@router.get("/summary", response_model=s.Summary)
async def summary(
    session: SessionDep,
    date_from: date | None = None,
    date_to: date | None = None,
    point_id: int | None = None,
):
    return await service.summary(session, date_from, date_to, point_id)


@router.get("/receivers/{receiver}/ledger", response_model=list[s.LedgerRow])
async def ledger(receiver: str, session: SessionDep):
    return await service.receiver_ledger(session, receiver)


@router.get("/export.xlsx")
async def export_xlsx(
    session: SessionDep,
    date_from: date | None = None,
    date_to: date | None = None,
    point_id: int | None = None,
):
    items = await service.list_shipments(session, date_from, date_to, point_id)
    data = build_xlsx([service.shipment_out(x) for x in items], await service.summary(session, date_from, date_to, point_id))
    return Response(
        data,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": 'attachment; filename="izlishek.xlsx"'},
    )
