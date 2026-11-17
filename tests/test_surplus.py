from __future__ import annotations

from decimal import Decimal as D

from app.modules.surplus.service import line_deviation


def test_line_deviation_sign():
    # Склад прийняв менше, ніж за пунктом → недостача (мінус), приймальник винен.
    dev, pct, amt = line_deviation(D("71.9"), D("65.7"), D("60"))
    assert dev == D("-6.2")
    assert round(pct, 2) == D("-8.62")
    assert amt == D("-372.0")
    # Склад прийняв більше → надлишок.
    dev, _, _ = line_deviation(D("12"), D("18"), D("45"))
    assert dev == D("6")
    # Нульова вага пункту не ламає відсоток.
    assert line_deviation(D("0"), D("1"), D("1"))[1] is None


async def _setup(client):
    p = (await client.post("/api/v1/surplus/points", json={"name": "Пункт №1", "receiver_name": "Іван"})).json()
    al = (await client.post("/api/v1/surplus/materials", json={"name": "AL", "price_per_kg": "60"})).json()
    bank = (await client.post("/api/v1/surplus/materials", json={"name": "AL банка", "price_per_kg": "45"})).json()
    cu = (await client.post("/api/v1/surplus/materials", json={"name": "Cu", "price_per_kg": "330"})).json()
    return p, al, bank, cu


async def test_notebook_page_totals(client):
    p, al, bank, cu = await _setup(client)
    r = await client.post("/api/v1/surplus/shipments", json={
        "ship_date": "2026-07-03", "point_id": p["id"],
        "lines": [
            {"material_id": al["id"], "point_kg": "71.9", "warehouse_kg": "65.7"},
            {"material_id": bank["id"], "point_kg": "12", "warehouse_kg": "18"},
            {"material_id": cu["id"], "point_kg": "37.85", "warehouse_kg": "37.5"},
        ],
    })
    assert r.status_code == 201, r.text
    sh = r.json()
    assert sh["receiver_name"] == "Іван"  # знімок із пункту
    t = sh["totals"]
    assert t["deviation_kg"] == -0.55          # -6.2 + 6 - 0.35
    assert t["surplus_kg"] == 6.0
    assert t["shortage_kg"] == -6.55
    # Вага майже зійшлась, а в грошах — мінус: AL перейшов у дешевшу банку.
    assert t["deviation_amount"] == round(-6.2 * 60 + 6 * 45 - 0.35 * 330, 2)


async def test_balance_and_settlement(client):
    p, al, bank, cu = await _setup(client)
    await client.post("/api/v1/surplus/shipments", json={
        "ship_date": "2026-07-03", "point_id": p["id"],
        "lines": [{"material_id": al["id"], "point_kg": "71.9", "warehouse_kg": "65.7"}],
    })
    summ = (await client.get("/api/v1/surplus/summary")).json()
    ivan = summ["receivers"][0]
    assert ivan["receiver_name"] == "Іван" and ivan["balance_kg"] == -6.2

    # Приймальник заготовив 6.2 кг AL — борг закрито.
    r = await client.post("/api/v1/surplus/settlements", json={
        "settle_date": "2026-07-05", "receiver_name": "Іван", "material_id": al["id"], "kg": "6.2"})
    assert r.status_code == 201, r.text
    ivan = (await client.get("/api/v1/surplus/summary")).json()["receivers"][0]
    assert ivan["balance_kg"] == 0 and ivan["balance_amount"] == 0

    ledger = (await client.get("/api/v1/surplus/receivers/Іван/ledger")).json()
    assert [row["balance_kg"] for row in ledger] == [0, -6.2]

    # Баланс на дату до погашення — ще борг.
    ivan = (await client.get("/api/v1/surplus/summary", params={"date_to": "2026-07-04"})).json()["receivers"][0]
    assert ivan["balance_kg"] == -6.2


async def test_duplicate_material_rejected(client):
    p, al, *_ = await _setup(client)
    line = {"material_id": al["id"], "point_kg": "1", "warehouse_kg": "1"}
    r = await client.post("/api/v1/surplus/shipments", json={"ship_date": "2026-07-03", "point_id": p["id"], "lines": [line, line]})
    assert r.status_code == 422


async def test_update_keeps_price_snapshot_and_export(client):
    p, al, *_ = await _setup(client)
    sh = (await client.post("/api/v1/surplus/shipments", json={
        "ship_date": "2026-07-03", "point_id": p["id"],
        "lines": [{"material_id": al["id"], "point_kg": "10", "warehouse_kg": "9"}]})).json()
    await client.put(f"/api/v1/surplus/materials/{al['id']}", json={"name": "AL", "price_per_kg": "100"})
    got = (await client.get(f"/api/v1/surplus/shipments/{sh['id']}")).json()
    assert got["lines"][0]["price_per_kg"] == 60.0
    r = await client.get("/api/v1/surplus/export.xlsx")
    assert r.status_code == 200 and r.content[:2] == b"PK"


def _matcher():
    from types import SimpleNamespace as NS

    from app.modules.surplus.recognize import Matcher
    from app.modules.surplus.seed import MATERIALS
    mats = [NS(id=i, name=n, aliases=a, is_active=True) for i, (n, _, _, a) in enumerate(MATERIALS, start=1)]
    return Matcher(mats), {m.id: m.name for m in mats}


def test_parse_notebook_text():
    from app.modules.surplus.recognize import parse_text
    m, names = _matcher()
    text = """03.07
AL 71,9 65,7
Cu 37,85
Латунь 34,45
AL банка 12
AL(посуда, проф) 8,2
Титан 3,9
Нерж 1,8
ЦАМ 1,4
"""
    d, items = parse_text(text, m)
    assert d is not None and (d.day, d.month) == (3, 7)
    got = [(names[i.material_id], i.kg, i.kg2) for i in items]
    assert got == [
        ("AL (електротех/лом)", 71.9, 65.7),
        ("Мідь (Cu)", 37.85, None),
        ("Латунь", 34.45, None),
        ("AL банка", 12.0, None),
        ("AL (посуд, профіль)", 8.2, None),
        ("Титан", 3.9, None),
        ("Нержавійка", 1.8, None),
        ("ЦАМ", 1.4, None),
    ]


def test_matcher_cyrillic_lookalikes_and_unknown():
    m, names = _matcher()
    assert names[m.match("АЛ")] == "AL (електротех/лом)"   # кирилицею
    assert names[m.match("Са")] == "Мідь (Cu)"             # «Cu» в зошиті схоже на «Са»
    assert m.match("свинець") is None


async def test_recognize_text_endpoint_and_photo_without_key(client, monkeypatch):
    # Довідники засіваються завжди, навіть без демо-даних.
    r = await client.post("/api/v1/surplus/recognize", data={"text": "ал 10,5\nщось 3"})
    assert r.status_code == 200, r.text
    items = r.json()["items"]
    assert items[0]["material_name"] == "AL (електротех/лом)" and items[0]["kg"] == 10.5
    assert items[1]["material_id"] is None and items[1]["raw"] == "щось"
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    r = await client.post("/api/v1/surplus/recognize", files={"files": ("a.jpg", b"x", "image/jpeg")})
    assert r.status_code == 503


async def test_password(monkeypatch):
    from httpx import ASGITransport, AsyncClient
    from fastapi import FastAPI
    from app.shared.auth import PasswordMiddleware
    app = FastAPI()
    app.add_middleware(PasswordMiddleware, password="secret")

    @app.get("/x")
    async def x():
        return {}

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://t") as c:
        assert (await c.get("/x")).status_code == 401
        assert (await c.get("/x", auth=("any", "secret"))).status_code == 200
        assert (await c.get("/x", auth=("any", "nope"))).status_code == 401
