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
    m = await service.get_settings_map(session)
    return s.SettingsIO(receiver_mode=m.get("receiver_mode") == "1", quotes=m.get("quotes") or "")


@router.put("/settings", response_model=s.SettingsIO)
async def put_app_settings(data: s.SettingsIO, session: SessionDep):
    await service.set_setting(session, "receiver_mode", "1" if data.receiver_mode else "0")
    if data.quotes is not None:
        await service.set_setting(session, "quotes", data.quotes.strip())
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


_MAX_FILE = 10 * 1024 * 1024
_IMAGE_TYPES = {"image/jpeg", "image/png", "image/webp", "image/gif"}


def _kind(f: UploadFile) -> str:
    name = (f.filename or "").lower()
    mt = (f.content_type or "").lower()
    if mt in _IMAGE_TYPES or name.endswith((".jpg", ".jpeg", ".png", ".webp", ".gif")):
        return "image"
    if mt == "application/pdf" or name.endswith(".pdf"):
        return "pdf"
    if name.endswith((".xlsx", ".xlsm")) or "spreadsheetml" in mt:
        return "xlsx"
    if name.endswith(".csv") or mt == "text/csv":
        return "csv"
    if name.endswith((".txt", ".text")) or mt.startswith("text/"):
        return "txt"
    return "?"


def _decode(data: bytes) -> str:
    for enc in ("utf-8-sig", "cp1251"):
        try:
            return data.decode(enc)
        except UnicodeDecodeError:
            continue
    return data.decode("utf-8", errors="ignore")


@router.post("/recognize", response_model=s.RecognizeOut)
async def recognize(
    session: SessionDep,
    text: str | None = Form(default=None),
    files: list[UploadFile] | None = File(default=None),
):
    """Фото/скріни, файли (Excel, CSV, TXT, PDF) або текст → рядки «матеріал / вага» для однієї колонки."""
    materials = await service.list_materials(session)
    matcher = rec.Matcher(materials)
    names = {m.id: m.name for m in materials}
    found_date = None
    items: list[rec.Item] = []
    if files:
        if len(files) > 5:
            raise HTTPException(422, L("Не більше 5 файлів за раз", "Не больше 5 файлов за раз"))
        to_claude: list[tuple[bytes, str]] = []
        for f in files:
            data = await f.read()
            if len(data) > _MAX_FILE:
                raise HTTPException(413, L("Файл завеликий (макс. 10 МБ)", "Файл слишком большой (макс. 10 МБ)"))
            kind = _kind(f)
            if kind == "image":
                to_claude.append((data, f.content_type if f.content_type in _IMAGE_TYPES else "image/jpeg"))
            elif kind == "pdf":
                to_claude.append((data, "application/pdf"))
            elif kind == "xlsx":
                from io import BytesIO

                from openpyxl import load_workbook
                try:
                    wb = load_workbook(BytesIO(data), read_only=True, data_only=True)
                except Exception:
                    raise HTTPException(422, L("Не вдалося відкрити Excel-файл", "Не удалось открыть Excel-файл")) from None
                for ws in wb.worksheets:
                    items += rec.parse_table([list(r) for r in ws.iter_rows(values_only=True)], matcher)
            elif kind == "csv":
                import csv
                raw = _decode(data)
                dialect = csv.Sniffer().sniff(raw[:2000], delimiters=",;\t") if raw.strip() else csv.excel
                items += rec.parse_table(list(csv.reader(raw.splitlines(), dialect)), matcher)
            elif kind == "txt":
                d, its = rec.parse_text(_decode(data), matcher)
                found_date = found_date or d
                items += its
            else:
                raise HTTPException(415, L("Підтримуються фото, PDF, Excel (.xlsx), CSV і TXT",
                                           "Поддерживаются фото, PDF, Excel (.xlsx), CSV и TXT"))
        if to_claude:
            d, its = await rec.parse_images(to_claude, materials, matcher)
            found_date = found_date or d
            items += its
        source = "photo" if to_claude else "file"
    elif text and text.strip():
        found_date, items = rec.parse_text(text, matcher)
        source = "text"
    else:
        raise HTTPException(422, L("Додайте фото, файл або текст", "Добавьте фото, файл или текст"))
    return s.RecognizeOut(
        source=source,
        date=found_date,
        items=[s.RecognizedItem(raw=i.raw, material_id=i.material_id,
                                material_name=names.get(i.material_id) if i.material_id else None,
                                kg=i.kg, kg2=i.kg2) for i in items],
    )
