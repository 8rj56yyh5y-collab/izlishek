"""Стартові довідники + приклад із зошита (03.07).

Ціни — ОРІЄНТОВНІ, лише щоб гроші не були нулями. Поставте свої
в «Довідники → Матеріали»: у вже збережених відвантаженнях ціна
зафіксована знімком, нові візьмуть нову.
"""
from __future__ import annotations

from datetime import date
from decimal import Decimal as D

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.surplus import schemas as s
from app.modules.surplus import service
from app.modules.surplus.models import SurplusMaterial, SurplusPoint

MATERIALS = [
    ("AL (електротех/лом)", "color", "60"),
    ("Мідь (Cu)", "color", "330"),
    ("Латунь", "color", "200"),
    ("AL банка", "color", "45"),
    ("AL (посуд, профіль)", "color", "70"),
    ("Титан", "color", "80"),
    ("Нержавійка", "color", "40"),
    ("ЦАМ", "color", "50"),
]

# Сторінка зошита: «Я» (пункт) | «ДМС» (склад)
NOTEBOOK_0307 = [
    ("AL (електротех/лом)", "71.9", "65.7"),
    ("Мідь (Cu)", "37.85", "37.5"),
    ("Латунь", "34.45", "34.5"),
    ("AL банка", "12", "18"),
    ("AL (посуд, профіль)", "8.2", "10"),
    ("Титан", "3.9", "3.9"),
    ("Нержавійка", "1.8", "1.8"),
    ("ЦАМ", "1.4", "1.4"),
]

DEMO = [
    (date(2026, 7, 10), 0, [("AL (електротех/лом)", "64.2", "61.0"), ("Мідь (Cu)", "22.4", "22.1"), ("Латунь", "18.0", "18.3"), ("AL банка", "9.5", "11.0")]),
    (date(2026, 7, 17), 1, [("AL (електротех/лом)", "88.0", "89.4"), ("Мідь (Cu)", "41.2", "41.0"), ("Нержавійка", "6.4", "6.2")]),
    (date(2026, 7, 24), 0, [("AL (електротех/лом)", "70.1", "67.9"), ("Латунь", "25.6", "25.0"), ("AL (посуд, профіль)", "14.0", "15.2"), ("ЦАМ", "3.3", "3.1")]),
    (date(2026, 7, 31), 1, [("AL (електротех/лом)", "55.0", "55.6"), ("Мідь (Cu)", "30.0", "29.4"), ("Титан", "2.1", "2.1")]),
]


async def seed(db: AsyncSession) -> None:
    if await db.scalar(select(func.count()).select_from(SurplusMaterial)):
        return
    for i, (name, group, price) in enumerate(MATERIALS, start=1):
        db.add(SurplusMaterial(name=name, group=group, price_per_kg=D(price), sort=i * 10))
    p1 = SurplusPoint(name="Пункт №1", receiver_name="Приймальник 1")
    p2 = SurplusPoint(name="Пункт №2", receiver_name="Приймальник 2")
    db.add_all([p1, p2])
    await db.commit()

    mats = {m.name: m.id for m in await service.list_materials(db)}

    def lines(rows):
        return [s.LineIn(material_id=mats[n], point_kg=D(a), warehouse_kg=D(b)) for n, a, b in rows]

    await service.save_shipment(db, s.ShipmentIn(
        ship_date=date(2026, 7, 3), point_id=p1.id, destination="ДМС",
        note="Перенесено з зошита (фото 03.07)", lines=lines(NOTEBOOK_0307)))
    for d, idx, rows in DEMO:
        await service.save_shipment(db, s.ShipmentIn(
            ship_date=d, point_id=(p1, p2)[idx].id, destination="ДМС", note="Демо-дані", lines=lines(rows)))
