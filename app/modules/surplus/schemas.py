from __future__ import annotations

from datetime import date
from decimal import Decimal

from pydantic import BaseModel, ConfigDict, Field, field_validator


class _Orm(BaseModel):
    model_config = ConfigDict(from_attributes=True)


# ── Довідники ───────────────────────────────────────────────────────────────
class PointIn(BaseModel):
    name: str = Field(min_length=1, max_length=120)
    receiver_name: str = Field(min_length=1, max_length=120)
    is_active: bool = True


class PointOut(_Orm):
    id: int
    name: str
    receiver_name: str
    is_active: bool


class MaterialIn(BaseModel):
    name: str = Field(min_length=1, max_length=120)
    group: str = Field(default="color", pattern="^(color|ferrous)$")
    price_per_kg: Decimal = Field(ge=0)
    aliases: str | None = None
    sort: int = 100
    is_active: bool = True


class MaterialOut(_Orm):
    id: int
    name: str
    group: str
    price_per_kg: float
    aliases: str | None
    sort: int
    is_active: bool


# ── Відвантаження ───────────────────────────────────────────────────────────
class LineIn(BaseModel):
    material_id: int
    point_kg: Decimal = Field(ge=0)
    warehouse_kg: Decimal = Field(ge=0)
    # Порожньо → береться поточна ціна з довідника.
    price_per_kg: Decimal | None = Field(default=None, ge=0)


class ShipmentIn(BaseModel):
    ship_date: date
    point_id: int
    receiver_name: str | None = None  # порожньо → поточний приймальник пункту
    destination: str = "ДМС"
    note: str | None = None
    lines: list[LineIn] = Field(min_length=1)

    @field_validator("lines")
    @classmethod
    def _unique_materials(cls, v: list[LineIn]) -> list[LineIn]:
        ids = [ln.material_id for ln in v]
        if len(ids) != len(set(ids)):
            raise ValueError("Один матеріал не може бути у відвантаженні двічі")
        return v


class LineOut(BaseModel):
    id: int
    material_id: int
    material_name: str
    point_kg: float
    warehouse_kg: float
    price_per_kg: float
    deviation_kg: float
    deviation_pct: float | None
    deviation_amount: float


class Totals(BaseModel):
    point_kg: float = 0
    warehouse_kg: float = 0
    deviation_kg: float = 0
    surplus_kg: float = 0      # сума додатних відхилень
    shortage_kg: float = 0     # сума від'ємних відхилень (від'ємне число)
    deviation_amount: float = 0
    surplus_amount: float = 0
    shortage_amount: float = 0


class ShipmentOut(BaseModel):
    id: int
    ship_date: date
    point_id: int
    point_name: str
    receiver_name: str
    destination: str
    note: str | None
    lines: list[LineOut]
    totals: Totals


class ShipmentListItem(BaseModel):
    id: int
    ship_date: date
    point_id: int
    point_name: str
    receiver_name: str
    destination: str
    lines_count: int
    totals: Totals


# ── Погашення ───────────────────────────────────────────────────────────────
class SettlementIn(BaseModel):
    settle_date: date
    receiver_name: str = Field(min_length=1, max_length=120)
    material_id: int
    kg: Decimal  # +: заготовив недостачу; −: списали надлишок
    price_per_kg: Decimal | None = Field(default=None, ge=0)
    note: str | None = None

    @field_validator("kg")
    @classmethod
    def _nonzero(cls, v: Decimal) -> Decimal:
        if v == 0:
            raise ValueError("Вага погашення не може бути нульовою")
        return v


class SettlementOut(BaseModel):
    id: int
    settle_date: date
    receiver_name: str
    material_id: int
    material_name: str
    kg: float
    price_per_kg: float
    amount: float
    note: str | None


# ── Звіти ───────────────────────────────────────────────────────────────────
class MaterialBalance(BaseModel):
    material_id: int
    material_name: str
    deviation_kg: float     # сума відхилень за відвантаженнями
    settled_kg: float       # сума погашень
    balance_kg: float       # deviation + settled; < 0 — винен заготовити
    balance_amount: float


class ReceiverBalance(BaseModel):
    receiver_name: str
    shipments: int
    surplus_kg: float
    shortage_kg: float
    balance_kg: float
    balance_amount: float
    materials: list[MaterialBalance]


class MaterialStat(BaseModel):
    material_id: int
    material_name: str
    point_kg: float
    warehouse_kg: float
    deviation_kg: float
    deviation_pct: float | None
    deviation_amount: float


class TimelinePoint(BaseModel):
    shipment_id: int
    ship_date: date
    point_name: str
    receiver_name: str
    deviation_kg: float
    deviation_amount: float


class Summary(BaseModel):
    shipments: int
    totals: Totals
    receivers: list[ReceiverBalance]
    materials: list[MaterialStat]
    timeline: list[TimelinePoint]


class LedgerRow(BaseModel):
    kind: str  # shipment | settlement
    ref_id: int
    on_date: date
    title: str
    material_id: int
    material_name: str
    kg: float
    amount: float
    balance_kg: float       # наростаючий баланс по цьому матеріалу
    balance_amount: float   # наростаючий баланс у грошах (по всіх матеріалах)


class RecognizedItem(BaseModel):
    raw: str
    material_id: int | None
    material_name: str | None
    kg: float | None
    kg2: float | None


class RecognizeOut(BaseModel):
    source: str  # text | photo
    date: date | None
    items: list[RecognizedItem]
