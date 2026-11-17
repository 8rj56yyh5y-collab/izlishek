from __future__ import annotations

from collections import defaultdict
from datetime import date
from decimal import ROUND_HALF_UP, Decimal

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.modules.surplus import schemas as s
from app.modules.surplus.models import (
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
) -> list[SurplusShipment]:
    q = _shipment_query().order_by(SurplusShipment.ship_date.desc(), SurplusShipment.id.desc())
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
