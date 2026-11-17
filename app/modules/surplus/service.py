from __future__ import annotations

import hashlib
import secrets
from collections import defaultdict
from datetime import date
from decimal import ROUND_HALF_UP, Decimal

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.modules.surplus import schemas as s
from app.modules.surplus.models import (
    SurplusSetting,
    SurplusMaterial,
    SurplusPoint,
    SurplusSettlement,
    SurplusShipment,
    SurplusShipmentLine,
)
from app.shared.i18n import L

ZERO = Decimal("0")


def _f(v: Decimal, q: str = "0.001") -> float:
    return float(Decimal(v).quantize(Decimal(q), rounding=ROUND_HALF_UP))


def _money(v: Decimal) -> float:
    return _f(v, "0.01")


# ── Чисті розрахунки (покриті тестами без БД) ───────────────────────────────
def line_deviation(point_kg: Decimal, warehouse_kg: Decimal, price: Decimal) -> tuple[Decimal, Decimal | None, Decimal]:
    """(відхилення кг, відхилення % від ваги пункту, відхилення грн).

    Додатне — надлишок (склад прийняв більше), від'ємне — недостача.
    """
    dev = Decimal(warehouse_kg) - Decimal(point_kg)
    pct = (dev / Decimal(point_kg) * 100) if point_kg else None
    return dev, pct, dev * Decimal(price)


class _Acc:
    """Накопичувач підсумків по набору рядків."""

    def __init__(self) -> None:
        self.point = ZERO
        self.wh = ZERO
        self.dev = ZERO
        self.surplus = ZERO
        self.shortage = ZERO
        self.amount = ZERO
        self.surplus_amount = ZERO
        self.shortage_amount = ZERO

    def add(self, point_kg: Decimal, wh_kg: Decimal, price: Decimal) -> None:
        dev, _, amount = line_deviation(point_kg, wh_kg, price)
        self.point += point_kg
        self.wh += wh_kg
        self.dev += dev
        self.amount += amount
        if dev > 0:
            self.surplus += dev
            self.surplus_amount += amount
        elif dev < 0:
            self.shortage += dev
            self.shortage_amount += amount

    def out(self) -> s.Totals:
        return s.Totals(
            point_kg=_f(self.point),
            warehouse_kg=_f(self.wh),
            deviation_kg=_f(self.dev),
            surplus_kg=_f(self.surplus),
            shortage_kg=_f(self.shortage),
            deviation_amount=_money(self.amount),
            surplus_amount=_money(self.surplus_amount),
            shortage_amount=_money(self.shortage_amount),
        )


# ── Довідники ───────────────────────────────────────────────────────────────
async def list_points(db: AsyncSession) -> list[SurplusPoint]:
    return list((await db.scalars(select(SurplusPoint).order_by(SurplusPoint.name))).all())


async def save_point(db: AsyncSession, data: s.PointIn, point_id: int | None = None) -> SurplusPoint:
    if point_id is None:
        obj = SurplusPoint()
        db.add(obj)
    else:
        obj = await _get(db, SurplusPoint, point_id, ("Пункт", "Пункт"))
    for k, v in data.model_dump().items():
        setattr(obj, k, v)
    await db.commit()
    await db.refresh(obj)
    return obj


async def list_materials(db: AsyncSession) -> list[SurplusMaterial]:
    q = select(SurplusMaterial).order_by(SurplusMaterial.sort, SurplusMaterial.name)
    return list((await db.scalars(q)).all())


async def save_material(db: AsyncSession, data: s.MaterialIn, material_id: int | None = None) -> SurplusMaterial:
    if material_id is None:
        obj = SurplusMaterial()
        db.add(obj)
    else:
        obj = await _get(db, SurplusMaterial, material_id, ("Матеріал", "Материал"))
    for k, v in data.model_dump().items():
        setattr(obj, k, v)
    await db.commit()
    await db.refresh(obj)
    return obj


async def _get(db: AsyncSession, model, obj_id: int, label: tuple[str, str]):
    obj = await db.get(model, obj_id)
    if obj is None:
        raise HTTPException(404, L(f"{label[0]} #{obj_id} не знайдено", f"{label[1]} #{obj_id} не найден"))
    return obj


# ── Відвантаження ───────────────────────────────────────────────────────────
def _shipment_query():
    return select(SurplusShipment).options(
        selectinload(SurplusShipment.lines).selectinload(SurplusShipmentLine.material),
        selectinload(SurplusShipment.point),
    )


def shipment_out(sh: SurplusShipment) -> s.ShipmentOut:
    acc = _Acc()
    lines: list[s.LineOut] = []
    for ln in sh.lines:
        dev, pct, amount = line_deviation(ln.point_kg, ln.warehouse_kg, ln.price_per_kg)
        acc.add(ln.point_kg, ln.warehouse_kg, ln.price_per_kg)
        lines.append(
            s.LineOut(
                id=ln.id,
                material_id=ln.material_id,
                material_name=ln.material.name,
                point_kg=_f(ln.point_kg),
                warehouse_kg=_f(ln.warehouse_kg),
                price_per_kg=_money(ln.price_per_kg),
                deviation_kg=_f(dev),
                deviation_pct=_f(pct, "0.01") if pct is not None else None,
                deviation_amount=_money(amount),
            )
        )
    return s.ShipmentOut(
        id=sh.id,
        ship_date=sh.ship_date,
        point_id=sh.point_id,
        point_name=sh.point.name,
        receiver_name=sh.receiver_name,
        destination=sh.destination,
        note=sh.note,
        lines=lines,
        totals=acc.out(),
    )


async def get_shipment(db: AsyncSession, shipment_id: int) -> SurplusShipment:
    sh = await db.scalar(_shipment_query().where(SurplusShipment.id == shipment_id))
    if sh is None:
        raise HTTPException(404, L(f"Відвантаження #{shipment_id} не знайдено", f"Отгрузка #{shipment_id} не найдена"))
    return sh


async def list_shipments(
    db: AsyncSession,
    date_from: date | None = None,
    date_to: date | None = None,
    point_id: int | None = None,
    receiver: str | None = None,
    status: str | None = "done",
) -> list[SurplusShipment]:
    """Типово — лише звірені: незвірені здачі приймальника (pending) не мають ваги складу
    і в розрахунки відхилень не потрапляють."""
    q = _shipment_query().order_by(SurplusShipment.ship_date.desc(), SurplusShipment.id.desc())
    if status:
        q = q.where(SurplusShipment.status == status)
    if date_from:
        q = q.where(SurplusShipment.ship_date >= date_from)
    if date_to:
        q = q.where(SurplusShipment.ship_date <= date_to)
    if point_id:
        q = q.where(SurplusShipment.point_id == point_id)
    if receiver:
        q = q.where(SurplusShipment.receiver_name == receiver)
    return list((await db.scalars(q)).all())


async def save_shipment(db: AsyncSession, data: s.ShipmentIn, shipment_id: int | None = None) -> SurplusShipment:
    point = await _get(db, SurplusPoint, data.point_id, ("Пункт", "Пункт"))
    materials = {m.id: m for m in await list_materials(db)}
    for ln in data.lines:
        if ln.material_id not in materials:
            raise HTTPException(422, L(f"Матеріал #{ln.material_id} не знайдено", f"Материал #{ln.material_id} не найден"))

    if shipment_id is None:
        sh = SurplusShipment()
        db.add(sh)
    else:
        sh = await get_shipment(db, shipment_id)
        sh.lines.clear()
        await db.flush()

    sh.ship_date = data.ship_date
    sh.point_id = point.id
    sh.receiver_name = (data.receiver_name or "").strip() or point.receiver_name
    sh.destination = data.destination.strip() or "ДМС"
    sh.note = data.note
    sh.status = "done"  # збереження адміністратором = звірено (у т.ч. добивка здачі приймальника)
    for i, ln in enumerate(data.lines, start=1):
        price = ln.price_per_kg if ln.price_per_kg is not None else materials[ln.material_id].price_per_kg
        sh.lines.append(
            SurplusShipmentLine(
                line_no=i,
                material_id=ln.material_id,
                point_kg=ln.point_kg,
                warehouse_kg=ln.warehouse_kg,
                price_per_kg=price,
            )
        )
    await db.commit()
    db.expunge_all()
    return await get_shipment(db, sh.id)


async def delete_shipment(db: AsyncSession, shipment_id: int) -> None:
    sh = await get_shipment(db, shipment_id)
    await db.delete(sh)
    await db.commit()


# ── Погашення ───────────────────────────────────────────────────────────────
def settlement_out(st: SurplusSettlement) -> s.SettlementOut:
    return s.SettlementOut(
        id=st.id,
        settle_date=st.settle_date,
        receiver_name=st.receiver_name,
        material_id=st.material_id,
        material_name=st.material.name,
        kg=_f(st.kg),
        price_per_kg=_money(st.price_per_kg),
        amount=_money(st.kg * st.price_per_kg),
        note=st.note,
    )


async def list_settlements(db: AsyncSession, receiver: str | None = None, date_to: date | None = None) -> list[SurplusSettlement]:
    q = select(SurplusSettlement).options(selectinload(SurplusSettlement.material))
    if receiver:
        q = q.where(SurplusSettlement.receiver_name == receiver)
    if date_to:
        q = q.where(SurplusSettlement.settle_date <= date_to)
    q = q.order_by(SurplusSettlement.settle_date.desc(), SurplusSettlement.id.desc())
    return list((await db.scalars(q)).all())


async def create_settlement(db: AsyncSession, data: s.SettlementIn) -> SurplusSettlement:
    mat = await _get(db, SurplusMaterial, data.material_id, ("Матеріал", "Материал"))
    st = SurplusSettlement(
        settle_date=data.settle_date,
        receiver_name=data.receiver_name.strip(),
        material_id=mat.id,
        kg=data.kg,
        price_per_kg=data.price_per_kg if data.price_per_kg is not None else mat.price_per_kg,
        note=data.note,
    )
    db.add(st)
    await db.commit()
    st = await db.scalar(
        select(SurplusSettlement).options(selectinload(SurplusSettlement.material)).where(SurplusSettlement.id == st.id)
    )
    assert st is not None
    return st


async def delete_settlement(db: AsyncSession, settlement_id: int) -> None:
    st = await _get(db, SurplusSettlement, settlement_id, ("Погашення", "Погашение"))
    await db.delete(st)
    await db.commit()


# ── Звіти ───────────────────────────────────────────────────────────────────
async def receiver_balances(db: AsyncSession, date_to: date | None = None) -> list[s.ReceiverBalance]:
    """Баланс кожного приймальника на дату — за ВСЮ історію, а не лише за період:
    борг «заготовити» не зникає з початком нового місяця."""
    shipments = await list_shipments(db, date_to=date_to)
    settlements = await list_settlements(db, date_to=date_to)

    names: dict[int, str] = {}
    dev: dict[str, dict[int, Decimal]] = defaultdict(lambda: defaultdict(Decimal))
    dev_amt: dict[str, dict[int, Decimal]] = defaultdict(lambda: defaultdict(Decimal))
    settled: dict[str, dict[int, Decimal]] = defaultdict(lambda: defaultdict(Decimal))
    settled_amt: dict[str, dict[int, Decimal]] = defaultdict(lambda: defaultdict(Decimal))
    counts: dict[str, int] = defaultdict(int)
    surplus: dict[str, Decimal] = defaultdict(Decimal)
    shortage: dict[str, Decimal] = defaultdict(Decimal)

    for sh in shipments:
        r = sh.receiver_name
        counts[r] += 1
        for ln in sh.lines:
            names[ln.material_id] = ln.material.name
            d, _, a = line_deviation(ln.point_kg, ln.warehouse_kg, ln.price_per_kg)
            dev[r][ln.material_id] += d
            dev_amt[r][ln.material_id] += a
            if d > 0:
                surplus[r] += d
            else:
                shortage[r] += d
    for st in settlements:
        r = st.receiver_name
        names[st.material_id] = st.material.name
        settled[r][st.material_id] += st.kg
        settled_amt[r][st.material_id] += st.kg * st.price_per_kg

    out: list[s.ReceiverBalance] = []
    for r in sorted(set(dev) | set(settled)):
        mats: list[s.MaterialBalance] = []
        total_kg = total_amt = ZERO
        for mid in sorted(set(dev[r]) | set(settled[r]), key=lambda m: names[m]):
            bal = dev[r][mid] + settled[r][mid]
            amt = dev_amt[r][mid] + settled_amt[r][mid]
            total_kg += bal
            total_amt += amt
            mats.append(
                s.MaterialBalance(
                    material_id=mid,
                    material_name=names[mid],
                    deviation_kg=_f(dev[r][mid]),
                    settled_kg=_f(settled[r][mid]),
                    balance_kg=_f(bal),
                    balance_amount=_money(amt),
                )
            )
        out.append(
            s.ReceiverBalance(
                receiver_name=r,
                shipments=counts[r],
                surplus_kg=_f(surplus[r]),
                shortage_kg=_f(shortage[r]),
                balance_kg=_f(total_kg),
                balance_amount=_money(total_amt),
                materials=mats,
            )
        )
    out.sort(key=lambda x: x.balance_amount)  # найбільші боржники — зверху
    return out


async def summary(
    db: AsyncSession,
    date_from: date | None = None,
    date_to: date | None = None,
    point_id: int | None = None,
) -> s.Summary:
    shipments = await list_shipments(db, date_from=date_from, date_to=date_to, point_id=point_id)
    total = _Acc()
    per_mat: dict[int, _Acc] = defaultdict(_Acc)
    names: dict[int, str] = {}
    timeline: list[s.TimelinePoint] = []
    for sh in sorted(shipments, key=lambda x: (x.ship_date, x.id)):
        acc = _Acc()
        for ln in sh.lines:
            names[ln.material_id] = ln.material.name
            for a in (total, per_mat[ln.material_id], acc):
                a.add(ln.point_kg, ln.warehouse_kg, ln.price_per_kg)
        timeline.append(
            s.TimelinePoint(
                shipment_id=sh.id,
                ship_date=sh.ship_date,
                point_name=sh.point.name,
                receiver_name=sh.receiver_name,
                deviation_kg=_f(acc.dev),
                deviation_amount=_money(acc.amount),
            )
        )
    materials = [
        s.MaterialStat(
            material_id=mid,
            material_name=names[mid],
            point_kg=_f(a.point),
            warehouse_kg=_f(a.wh),
            deviation_kg=_f(a.dev),
            deviation_pct=_f(a.dev / a.point * 100, "0.01") if a.point else None,
            deviation_amount=_money(a.amount),
        )
        for mid, a in per_mat.items()
    ]
    materials.sort(key=lambda m: m.deviation_amount)

    receivers = await receiver_balances(db, date_to=date_to)
    if point_id:
        involved = {sh.receiver_name for sh in shipments}
        receivers = [r for r in receivers if r.receiver_name in involved]

    return s.Summary(
        shipments=len(shipments),
        totals=total.out(),
        receivers=receivers,
        materials=materials,
        timeline=timeline,
    )


async def receiver_ledger(db: AsyncSession, receiver: str) -> list[s.LedgerRow]:
    """Хронологія приймальника: кожен рядок відвантаження і кожне погашення
    з наростаючим балансом по матеріалу та загальним у грошах."""
    events: list[tuple[date, int, int, s.LedgerRow]] = []
    for sh in await list_shipments(db, receiver=receiver):
        for ln in sh.lines:
            d, _, a = line_deviation(ln.point_kg, ln.warehouse_kg, ln.price_per_kg)
            if d == 0:
                continue
            events.append(
                (
                    sh.ship_date,
                    0,
                    sh.id,
                    s.LedgerRow(
                        kind="shipment",
                        ref_id=sh.id,
                        on_date=sh.ship_date,
                        title=L("Відвантаження", "Отгрузка") + f" {sh.point.name} → {sh.destination}",
                        material_id=ln.material_id,
                        material_name=ln.material.name,
                        kg=float(d),
                        amount=float(a),
                        balance_kg=0,
                        balance_amount=0,
                    ),
                )
            )
    for st in await list_settlements(db, receiver=receiver):
        events.append(
            (
                st.settle_date,
                1,
                st.id,
                s.LedgerRow(
                    kind="settlement",
                    ref_id=st.id,
                    on_date=st.settle_date,
                    title=st.note or (L("Заготовив недостачу", "Заготовил недостачу") if st.kg > 0 else L("Списано надлишок", "Списан излишек")),
                    material_id=st.material_id,
                    material_name=st.material.name,
                    kg=float(st.kg),
                    amount=float(st.kg * st.price_per_kg),
                    balance_kg=0,
                    balance_amount=0,
                ),
            )
        )
    events.sort(key=lambda e: (e[0], e[1], e[2]))
    run_kg: dict[int, Decimal] = defaultdict(Decimal)
    run_amt = ZERO
    rows: list[s.LedgerRow] = []
    for _, _, _, row in events:
        run_kg[row.material_id] += Decimal(str(row.kg))
        run_amt += Decimal(str(row.amount))
        row.kg = _f(Decimal(str(row.kg)))
        row.amount = _money(Decimal(str(row.amount)))
        row.balance_kg = _f(run_kg[row.material_id])
        row.balance_amount = _money(run_amt)
        rows.append(row)
    rows.reverse()  # свіже — зверху
    return rows



# ── Налаштування ────────────────────────────────────────────────────────────
SETTING_DEFAULTS = {"receiver_mode": "0"}


async def get_settings_map(db: AsyncSession) -> dict[str, str]:
    rows = (await db.scalars(select(SurplusSetting))).all()
    return {**SETTING_DEFAULTS, **{r.key: r.value for r in rows}}


async def set_setting(db: AsyncSession, key: str, value: str) -> None:
    row = await db.get(SurplusSetting, key)
    if row is None:
        db.add(SurplusSetting(key=key, value=value))
    else:
        row.value = value
    await db.commit()


def parse_quotes(raw: str | None) -> list[dict[str, str]]:
    """«Текст — Автор» по рядку; автор необовʼязковий (роздільник — тире з пробілами)."""
    out = []
    for line in (raw or "").splitlines():
        line = line.strip()
        if not line:
            continue
        text, author = line, ""
        for sep in (" — ", " – ", " - "):
            if sep in line:
                text, _, author = line.rpartition(sep)
                break
        out.append({"text": text.strip().strip("«»\"„“"), "author": author.strip()})
    return out


async def receiver_mode(db: AsyncSession) -> bool:
    return (await get_settings_map(db)).get("receiver_mode") == "1"


# ── PIN приймальника ────────────────────────────────────────────────────────
def hash_pin(pin: str, salt: str) -> str:
    return hashlib.pbkdf2_hmac("sha256", pin.encode(), bytes.fromhex(salt), 120_000).hex()


async def set_point_pin(db: AsyncSession, point_id: int, pin: str | None) -> SurplusPoint:
    point = await _get(db, SurplusPoint, point_id, ("Пункт", "Пункт"))
    if pin:
        for other in await list_points(db):
            if other.id != point.id and other.pin_hash and hash_pin(pin, other.pin_salt) == other.pin_hash:
                raise HTTPException(422, L("Такий PIN уже має інший пункт", "Такой PIN уже у другого пункта"))
        point.pin_salt = secrets.token_hex(16)
        point.pin_hash = hash_pin(pin, point.pin_salt)
    else:
        point.pin_salt = point.pin_hash = None
    await db.commit()
    await db.refresh(point)
    return point


async def point_by_pin(db: AsyncSession, pin: str) -> SurplusPoint | None:
    for p in await list_points(db):
        if p.is_active and p.pin_hash and secrets.compare_digest(hash_pin(pin, p.pin_salt), p.pin_hash):
            return p
    return None


# ── Здачі приймальника (pending) ────────────────────────────────────────────
def submission_out(sh: SurplusShipment) -> s.SubmissionOut:
    done = sh.status == "done"
    lines = []
    for ln in sh.lines:
        dev = (ln.warehouse_kg - ln.point_kg) if done else None
        lines.append(s.SubmissionLineOut(
            material_id=ln.material_id, material_name=ln.material.name, point_kg=_f(ln.point_kg),
            warehouse_kg=_f(ln.warehouse_kg) if done else None, deviation_kg=_f(dev) if dev is not None else None))
    return s.SubmissionOut(
        id=sh.id, ship_date=sh.ship_date, point_id=sh.point_id, point_name=sh.point.name,
        receiver_name=sh.receiver_name, status=sh.status, note=sh.note,
        submitted_by_receiver=sh.submitted_by_receiver, lines=lines,
        totals=shipment_out(sh).totals if done else None,
    )


async def save_submission(db: AsyncSession, point: SurplusPoint, data: s.SubmissionIn,
                          shipment_id: int | None = None) -> SurplusShipment:
    materials = {m.id: m for m in await list_materials(db)}
    for ln in data.lines:
        if ln.material_id not in materials:
            raise HTTPException(422, L(f"Матеріал #{ln.material_id} не знайдено", f"Материал #{ln.material_id} не найден"))
    if shipment_id is None:
        sh = SurplusShipment(point_id=point.id, receiver_name=point.receiver_name, destination="ДМС",
                             status="pending", submitted_by_receiver=True)
        db.add(sh)
    else:
        sh = await own_pending(db, point, shipment_id)
        sh.lines.clear()
        await db.flush()
    sh.ship_date = data.ship_date
    sh.note = data.note
    for i, ln in enumerate(data.lines, start=1):
        sh.lines.append(SurplusShipmentLine(line_no=i, material_id=ln.material_id, point_kg=ln.kg,
                                            warehouse_kg=Decimal("0"), price_per_kg=materials[ln.material_id].price_per_kg))
    await db.commit()
    db.expunge_all()
    return await get_shipment(db, sh.id)


async def own_pending(db: AsyncSession, point: SurplusPoint, shipment_id: int) -> SurplusShipment:
    sh = await get_shipment(db, shipment_id)
    if sh.point_id != point.id:
        raise HTTPException(404, L(f"Відвантаження #{shipment_id} не знайдено", f"Отгрузка #{shipment_id} не найдена"))
    if sh.status != "pending":
        raise HTTPException(409, L("Склад уже звірив цю здачу — змінити її може лише адміністратор",
                                   "Склад уже сверил эту сдачу — изменить её может только администратор"))
    return sh
