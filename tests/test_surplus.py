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
    mats = [NS(id=i, name=n, aliases=a, is_active=True) for i, (n, a) in enumerate(MATERIALS, start=1)]
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
        ("Алюминий", 71.9, 65.7),
        ("Медь микс", 37.85, None),
        ("Латунь/Бронза", 34.45, None),
        ("Банка", 12.0, None),
        ("АЛ профиль", 8.2, None),
        ("Титан", 3.9, None),
        ("Н/Ж (10%)", 1.8, None),
        ("ЦАМ", 1.4, None),
    ]


def test_parse_numbers_inside_names():
    from app.modules.surplus.recognize import parse_text
    m, names = _matcher()
    _, items = parse_text("Медь 1 сорт 37,85 37,5\nН/Ж (10%) 5 кг\nАЛ электротех - 71,9 / 65,7", m)
    assert [(names[i.material_id], i.kg, i.kg2) for i in items] == [
        ("Медь 1 сорт", 37.85, 37.5), ("Н/Ж (10%)", 5.0, None), ("АЛ электротех", 71.9, 65.7)]


def test_matcher_webmax_names():
    m, names = _matcher()
    for raw, want in [("АЛ электротех", "АЛ электротех"), ("ал стружка", "АЛ стружка"), ("Медь 1 сорт", "Медь 1 сорт"),
                      ("Медная стружка", "Медная стружка"), ("Н/Ж стружка", "Н/Ж стружка"), ("АКБ гелевый", "АКБ гелевый"),
                      ("Срібло не магніт", "Срібло не магніт"), ("Латунь/Бронза стружка", "Латунь/Бронза стружка")]:
        assert names[m.match(raw)] == want, raw


def test_matcher_cyrillic_lookalikes_and_unknown():
    m, names = _matcher()
    assert names[m.match("AL")] == "Алюминий"
    assert names[m.match("Са")] == "Медь микс"             # «Cu» в зошиті схоже на «Са»
    assert m.match("вольфрам") is None


async def test_recognize_text_endpoint_and_photo_without_key(client, monkeypatch):
    # Довідники засіваються завжди, навіть без демо-даних.
    r = await client.post("/api/v1/surplus/recognize", data={"text": "ал 10,5\nщось 3"})
    assert r.status_code == 200, r.text
    items = r.json()["items"]
    assert items[0]["material_name"] == "Алюминий" and items[0]["kg"] == 10.5
    assert items[1]["material_id"] is None and items[1]["raw"] == "щось"
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    r = await client.post("/api/v1/surplus/recognize", files={"files": ("a.jpg", b"x", "image/jpeg")})
    assert r.status_code == 503


async def test_login_cookie_and_lang(client, monkeypatch):
    from app.shared.config import get_settings
    monkeypatch.setenv("APP_PASSWORD", "secret")
    get_settings.cache_clear()
    st = (await client.get("/api/v1/auth/status")).json()
    assert st["required"] is True and st["ok"] is False
    r = await client.get("/api/v1/surplus/points", headers={"X-Lang": "ru"})
    assert r.status_code == 401 and r.json()["detail"] == "Нужно войти"
    r = await client.post("/api/v1/auth/login", json={"password": "nope"})
    assert r.status_code == 401 and r.json()["detail"] == "Невірний пароль"
    r = await client.post("/api/v1/auth/login", json={"password": "secret"})
    assert r.status_code == 200 and "bt_session" in r.cookies
    assert (await client.get("/api/v1/surplus/points")).status_code == 200
    r = await client.get("/api/v1/surplus/shipments/999", headers={"X-Lang": "ru"})
    assert r.json()["detail"] == "Отгрузка #999 не найдена"
    assert (await client.get("/api/v1/health")).status_code == 200


async def test_receiver_mode_flow(client, monkeypatch):
    from httpx import ASGITransport, AsyncClient

    from app.shared.config import get_settings
    from main import app
    monkeypatch.setenv("APP_PASSWORD", "admin-pw")
    get_settings.cache_clear()
    assert (await client.post("/api/v1/auth/login", json={"password": "admin-pw"})).status_code == 200
    point = (await client.get("/api/v1/surplus/points")).json()[0]
    al = next(m for m in (await client.get("/api/v1/surplus/materials")).json() if m["name"] == "Алюминий")
    assert (await client.put(f"/api/v1/surplus/points/{point['id']}/pin", json={"pin": "12"})).status_code == 422
    r = await client.put(f"/api/v1/surplus/points/{point['id']}/pin", json={"pin": "4321"})
    assert r.json()["has_pin"] is True

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://t") as rc:
        # режим вимкнено — PIN не пускає
        assert (await rc.post("/api/v1/auth/login", json={"password": "4321"})).status_code == 401
        await client.put("/api/v1/surplus/settings", json={"receiver_mode": True})
        r = await rc.post("/api/v1/auth/login", json={"password": "4321"})
        assert r.json()["role"] == "receiver"
        st = (await rc.get("/api/v1/auth/status")).json()
        assert st["role"] == "receiver" and st["point_id"] == point["id"]
        # чуже — заборонено
        assert (await rc.get("/api/v1/surplus/summary")).status_code == 403
        assert (await rc.get("/api/v1/surplus/materials")).status_code == 200
        sub = (await rc.post("/api/v1/receiver/submissions", json={
            "ship_date": "2026-11-17", "lines": [{"material_id": al["id"], "kg": "30"}]})).json()
        assert sub["status"] == "pending" and sub["lines"][0]["warehouse_kg"] is None

        # у звітах адміна незвірене не рахується, але є в «чекають звірки»
        assert (await client.get("/api/v1/surplus/summary")).json()["shipments"] == 0
        pend = (await client.get("/api/v1/surplus/pending")).json()
        assert [p["id"] for p in pend] == [sub["id"]]
        r = await client.put(f"/api/v1/surplus/shipments/{sub['id']}", json={
            "ship_date": "2026-11-17", "point_id": point["id"],
            "lines": [{"material_id": al["id"], "point_kg": "30", "warehouse_kg": "33"}]})
        assert r.status_code == 200
        assert (await client.get("/api/v1/surplus/pending")).json() == []

        # приймальник бачить результат: +3 кг — його плюс
        mine = (await rc.get("/api/v1/receiver/submissions")).json()
        assert mine[0]["status"] == "done" and mine[0]["lines"][0]["deviation_kg"] == 3.0
        me = (await rc.get("/api/v1/receiver/me")).json()
        assert me["balance"]["balance_kg"] == 3.0
        # звірене змінити не може
        r = await rc.put(f"/api/v1/receiver/submissions/{sub['id']}", json={
            "ship_date": "2026-11-17", "lines": [{"material_id": al["id"], "kg": "1"}]})
        assert r.status_code == 409

        # вимкнули режим — сесія приймальника більше не діє
        await client.put("/api/v1/surplus/settings", json={"receiver_mode": False})
        assert (await rc.get("/api/v1/receiver/me")).status_code == 401


async def test_custom_quotes(client):
    assert (await client.get("/api/v1/auth/quotes")).json() == []
    await client.put("/api/v1/surplus/settings", json={"receiver_mode": False,
        "quotes": "Хто всюди — той ніде. — Сенека\n\n«Без автора»"})
    assert (await client.get("/api/v1/auth/quotes")).json() == [
        {"text": "Хто всюди — той ніде.", "author": "Сенека"}, {"text": "Без автора", "author": ""}]


def test_parse_one_line_and_mixed():
    from app.modules.surplus.recognize import parse_text
    m, names = _matcher()
    got = lambda txt: [(names.get(i.material_id), i.kg, i.kg2) for i in parse_text(txt, m)[1]]
    # усе в один рядок, без переносів
    assert got("AL 71,9 Cu 37,85 Латунь 34,45 Банка 12") == [
        ("Алюминий", 71.9, None), ("Медь микс", 37.85, None), ("Латунь/Бронза", 34.45, None), ("Банка", 12.0, None)]
    # дві колонки в одному рядку + назва з числом
    assert got("Медь 1 сорт 37,85 37,5 Банка 12 18") == [("Медь 1 сорт", 37.85, 37.5), ("Банка", 12.0, 18.0)]
    # «АЛ 5 АЛ профиль 3» — дві різні позиції
    assert got("АЛ 5 АЛ профиль 3") == [("Алюминий", 5.0, None), ("АЛ профиль", 3.0, None)]
    # через кому/крапку з комою, з «кг» і двокрапкою, дата спереду
    d, items = parse_text("03.07 ЦАМ: 1,4 кг; Титан 3,9, Н/Ж (10%) 1,8", m)
    assert (d.day, d.month) == (3, 7)
    assert [(names[i.material_id], i.kg) for i in items] == [("ЦАМ", 1.4), ("Титан", 3.9), ("Н/Ж (10%)", 1.8)]
    assert got("АЛ электротех 71,9/65,7") == [("АЛ электротех", 71.9, 65.7)]


async def test_recognize_files(client):
    from io import BytesIO

    from openpyxl import Workbook
    wb = Workbook()
    ws = wb.active
    ws.append(["Матеріал", "Я", "ДМС"])
    ws.append(["Алюминий", 71.9, 65.7])
    ws.append(["Банка", "12", "18"])
    buf = BytesIO()
    wb.save(buf)
    r = await client.post("/api/v1/surplus/recognize", files={"files": ("t.xlsx", buf.getvalue(),
        "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")})
    assert r.status_code == 200, r.text
    assert [(i["material_name"], i["kg"], i["kg2"]) for i in r.json()["items"]] == [
        ("Алюминий", 71.9, 65.7), ("Банка", 12.0, 18.0)]
    r = await client.post("/api/v1/surplus/recognize", files={"files": ("t.csv", "Банка;12\nЦАМ;1,4\n".encode("cp1251"), "text/csv")})
    assert [(i["material_name"], i["kg"]) for i in r.json()["items"]] == [("Банка", 12.0), ("ЦАМ", 1.4)]
    r = await client.post("/api/v1/surplus/recognize", files={"files": ("a.docx", b"x", "application/msword")})
    assert r.status_code == 415
