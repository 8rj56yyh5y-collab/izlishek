"""Модуль «Надлишки / недостачі приймальника».

Суть обліку
-----------
Приймальник на пункті приймає брухт і сам ставить засор. Потім пункт
відвантажує метал на склад (напр. склад кольорового «ДМС»), і там його
переважують/пересортовують зі своїм засором.

* ``point_kg``     — скільки за обліком пункту (колонка «Я» в зошиті);
* ``warehouse_kg`` — скільки зарахував склад (колонка «ДМС»);
* відхилення = ``warehouse_kg − point_kg``:
    > 0 — НАДЛИШОК: склад прийняв більше, ніж за пунктом
          (приймальник поставив засор більший, ніж треба);
    < 0 — НЕДОСТАЧА: за пунктом вага є, а фізично її нема
          (засор поставлено замалий) — цю вагу приймальник має «заготовити».

Плюс і мінус — це особистий баланс приймальника, окремо по кожному
матеріалу (кг) і в грошах (кг × ціна на дату відвантаження).
Погашення (``SurplusSettlement``) — запис, яким недостачу закривають
(приймальник «заготовив» вагу) або списують надлишок.
"""
from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal

from sqlalchemy import Boolean, Date, DateTime, ForeignKey, Integer, Numeric, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.shared.database import Base

KG = Numeric(12, 3)
PRICE = Numeric(12, 2)


class SurplusPoint(Base):
    """Приймальний пункт і його поточний приймальник."""

    __tablename__ = "surplus_points"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(120), nullable=False)
    receiver_name: Mapped[str] = mapped_column(String(120), nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=func.now())


class SurplusMaterial(Base):
    """Вид металу. Ціна — поточна; у рядку відвантаження вона фіксується знімком."""

    __tablename__ = "surplus_materials"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(120), nullable=False)
    group: Mapped[str] = mapped_column(String(20), nullable=False, default="color")  # color | ferrous
    price_per_kg: Mapped[Decimal] = mapped_column(PRICE, nullable=False, default=0)
    # Як матеріал пишуть у зошитах/скрінах, через кому: «al, ал, алюміній».
    aliases: Mapped[str | None] = mapped_column(Text, nullable=True)
    sort: Mapped[int] = mapped_column(Integer, nullable=False, default=100)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)


class SurplusShipment(Base):
    """Одне відвантаження пункту на склад (одна сторінка зошита)."""

    __tablename__ = "surplus_shipments"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    ship_date: Mapped[date] = mapped_column(Date, nullable=False)
    point_id: Mapped[int] = mapped_column(ForeignKey("surplus_points.id", ondelete="RESTRICT"), nullable=False)
    # Знімок: приймальник на пункті може змінитися, а відповідальність лишається за тим, хто був.
    receiver_name: Mapped[str] = mapped_column(String(120), nullable=False)
    destination: Mapped[str] = mapped_column(String(120), nullable=False, default="ДМС")
    note: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=func.now())

    lines: Mapped[list[SurplusShipmentLine]] = relationship(
        back_populates="shipment", cascade="all, delete-orphan", order_by="SurplusShipmentLine.line_no"
    )
    point: Mapped[SurplusPoint] = relationship()


class SurplusShipmentLine(Base):
    __tablename__ = "surplus_shipment_lines"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    shipment_id: Mapped[int] = mapped_column(ForeignKey("surplus_shipments.id", ondelete="CASCADE"), nullable=False)
    line_no: Mapped[int] = mapped_column(Integer, nullable=False)
    material_id: Mapped[int] = mapped_column(ForeignKey("surplus_materials.id", ondelete="RESTRICT"), nullable=False)
    point_kg: Mapped[Decimal] = mapped_column(KG, nullable=False)
    warehouse_kg: Mapped[Decimal] = mapped_column(KG, nullable=False)
    price_per_kg: Mapped[Decimal] = mapped_column(PRICE, nullable=False)

    shipment: Mapped[SurplusShipment] = relationship(back_populates="lines")
    material: Mapped[SurplusMaterial] = relationship()


class SurplusSettlement(Base):
    """Погашення: недостачу «заготовили» (kg > 0) або надлишок списали (kg < 0)."""

    __tablename__ = "surplus_settlements"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    settle_date: Mapped[date] = mapped_column(Date, nullable=False)
    receiver_name: Mapped[str] = mapped_column(String(120), nullable=False)
    material_id: Mapped[int] = mapped_column(ForeignKey("surplus_materials.id", ondelete="RESTRICT"), nullable=False)
    kg: Mapped[Decimal] = mapped_column(KG, nullable=False)
    price_per_kg: Mapped[Decimal] = mapped_column(PRICE, nullable=False)
    note: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=func.now())

    material: Mapped[SurplusMaterial] = relationship()
