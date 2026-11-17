"""Вивантаження в Excel — щоб звіт можна було переслати тим, хто ще живе в таблицях."""
from __future__ import annotations

from io import BytesIO

from openpyxl import Workbook
from openpyxl.styles import Alignment, Font, PatternFill
from openpyxl.utils import get_column_letter

from app.modules.surplus import schemas as s
from app.shared.i18n import L

_HEAD = Font(bold=True)
_RED = PatternFill("solid", fgColor="FDE2E2")
_GREEN = PatternFill("solid", fgColor="DCFCE7")


def _sheet(ws, header: list[str], rows: list[list], widths: list[int], dev_col: int | None = None) -> None:
    ws.append(header)
    for c in ws[1]:
        c.font = _HEAD
        c.alignment = Alignment(wrap_text=True, vertical="center")
    for r in rows:
        ws.append(r)
        if dev_col is not None:
            v = r[dev_col]
            if isinstance(v, (int, float)) and v:
                ws.cell(ws.max_row, dev_col + 1).fill = _GREEN if v > 0 else _RED
    for i, w in enumerate(widths, start=1):
        ws.column_dimensions[get_column_letter(i)].width = w
    ws.freeze_panes = "A2"


def build_xlsx(shipments: list[s.ShipmentOut], summary: s.Summary) -> bytes:
    wb = Workbook()
    ws = wb.active
    ws.title = L("Відвантаження", "Отгрузки")
    rows = []
    for sh in shipments:
        for ln in sh.lines:
            rows.append([
                sh.ship_date.strftime("%d.%m.%Y"), sh.point_name, sh.receiver_name, sh.destination,
                ln.material_name, ln.point_kg, ln.warehouse_kg, ln.deviation_kg, ln.deviation_pct,
                ln.price_per_kg, ln.deviation_amount,
            ])
    _sheet(ws, [L("Дата", "Дата"), L("Пункт", "Пункт"), L("Приймальник", "Приёмщик"), L("Склад", "Склад"),
                L("Матеріал", "Материал"), L("Приймальник, кг", "Приёмщик, кг"), L("Склад, кг", "Склад, кг"),
                L("Відхилення, кг", "Отклонение, кг"), L("Відхилення, %", "Отклонение, %"),
                L("Ціна, грн/кг", "Цена, грн/кг"), L("Відхилення, грн", "Отклонение, грн")],
           rows, [11, 18, 20, 10, 22, 11, 11, 13, 12, 11, 14], dev_col=7)

    ws2 = wb.create_sheet(L("Баланс приймальників", "Баланс приёмщиков"))
    rows2 = []
    for r in summary.receivers:
        for m in r.materials:
            rows2.append([r.receiver_name, m.material_name, m.deviation_kg, m.settled_kg, m.balance_kg, m.balance_amount])
        rows2.append([f"{r.receiver_name} — " + L("разом", "итого"), "", None, None, r.balance_kg, r.balance_amount])
    _sheet(ws2, [L("Приймальник", "Приёмщик"), L("Матеріал", "Материал"), L("Відхилення, кг", "Отклонение, кг"),
                 L("Погашено, кг", "Погашено, кг"), L("Баланс, кг", "Баланс, кг"), L("Баланс, грн", "Баланс, грн")],
           rows2, [26, 22, 14, 13, 12, 13], dev_col=4)

    ws3 = wb.create_sheet(L("По матеріалах", "По материалам"))
    _sheet(ws3, [L("Матеріал", "Материал"), L("Приймальник, кг", "Приёмщик, кг"), L("Склад, кг", "Склад, кг"),
                 L("Відхилення, кг", "Отклонение, кг"), L("Відхилення, %", "Отклонение, %"), L("Відхилення, грн", "Отклонение, грн")],
           [[m.material_name, m.point_kg, m.warehouse_kg, m.deviation_kg, m.deviation_pct, m.deviation_amount]
            for m in summary.materials],
           [22, 12, 12, 14, 13, 14], dev_col=3)

    buf = BytesIO()
    wb.save(buf)
    return buf.getvalue()
