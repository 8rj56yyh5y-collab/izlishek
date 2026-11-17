from __future__ import annotations

from datetime import date

from fastapi import APIRouter, File, Form, HTTPException, Response, UploadFile

from app.modules.surplus import schemas as s
from app.modules.surplus import service
from app.modules.surplus import recognize as rec
from app.modules.surplus.export import build_xlsx
from app.shared.database import SessionDep
from app.shared.i18n import L

router = APIRouter(prefix="/api/v1/surplus", tags=["surplus"])


@router.get("/points", response_model=list[s.PointOut])
async def points(session: SessionDep):
    return [s.PointOut.of(p) for p in await service.list_points(session)]


@router.post("/points", response_model=s.PointOut, status_code=201)
async def create_point(data: s.PointIn, session: SessionDep):
    return s.PointOut.of(await service.save_point(session, data))


@router.put("/points/{point_id}", response_model=s.PointOut)
async def update_point(point_id: int, data: s.PointIn, session: SessionDep):
    return s.PointOut.of(await service.save_point(session, data, point_id))


@router.put("/points/{point_id}/pin", response_model=s.PointOut)
async def set_pin(point_id: int, data: s.PinIn, session: SessionDep):
    """PIN приймальника для входу у його версію; порожній — вимкнути вхід."""
    return s.PointOut.of(await service.set_point_pin(session, point_id, data.pin))


@router.get("/settings", response_model=s.SettingsIO)
async def get_app_settings(session: SessionDep):
    return s.SettingsIO(receiver_mode=await service.receiver_mode(session))


@router.put("/settings", response_model=s.SettingsIO)
async def put_app_settings(data: s.SettingsIO, session: SessionDep):
    await service.set_setting(session, "receiver_mode", "1" if data.receiver_mode else "0")
    return data


@router.get("/pending", response_model=list[s.SubmissionOut])
async def pending(session: SessionDep):
    """Здачі приймальників, які чекають ваги складу."""
    return [service.submission_out(x) for x in await service.list_shipments(session, status="pending")]


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
        headers={"Content-Disposition": 'attachment; filename="brukhtarnia.xlsx"'},
    )


_MAX_IMAGE = 8 * 1024 * 1024


@router.post("/recognize", response_model=s.RecognizeOut)
async def recognize(
    session: SessionDep,
    text: str | None = Form(default=None),
    files: list[UploadFile] | None = File(default=None),
):
    """Фото (до 5 штук) або текст → рядки «матеріал / вага» для однієї колонки."""
    materials = await service.list_materials(session)
    matcher = rec.Matcher(materials)
    names = {m.id: m.name for m in materials}
    if files:
        if len(files) > 5:
            raise HTTPException(422, L("Не більше 5 фото за раз", "Не больше 5 фото за раз"))
        images = []
        for f in files:
            data = await f.read()
            if len(data) > _MAX_IMAGE:
                raise HTTPException(413, L("Фото завелике (макс. 8 МБ)", "Фото слишком большое (макс. 8 МБ)"))
            mt = f.content_type or "image/jpeg"
            if mt not in ("image/jpeg", "image/png", "image/webp", "image/gif"):
                raise HTTPException(415, L("Підтримуються JPEG, PNG, WebP", "Поддерживаются JPEG, PNG, WebP"))
            images.append((data, mt))
        found_date, items = await rec.parse_images(images, materials, matcher)
        source = "photo"
    elif text and text.strip():
        found_date, items = rec.parse_text(text, matcher)
        source = "text"
    else:
        raise HTTPException(422, L("Додайте фото або текст", "Добавьте фото или текст"))
    return s.RecognizeOut(
        source=source,
        date=found_date,
        items=[s.RecognizedItem(raw=i.raw, material_id=i.material_id,
                                material_name=names.get(i.material_id) if i.material_id else None,
                                kg=i.kg, kg2=i.kg2) for i in items],
    )
