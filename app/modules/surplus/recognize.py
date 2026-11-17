"""Розпізнавання ваги з тексту або фото.

* Текст розбираємо локально — миттєво і без зовнішніх сервісів:
  кожен рядок «назва число [число]», напр. «AL 71,9» або «AL 71,9 65,7».
* Фото (зошит, скрін з 1С/Viber, накладна) — через Claude з vision і
  structured output; потрібен ANTHROPIC_API_KEY.

Назву матеріалу зіставляємо з довідником через аліаси (``SurplusMaterial.aliases``):
виграє найдовший збіг, тож «AL банка» → «AL банка», а не «AL».
"""
from __future__ import annotations

import base64
import json
import logging
import os
import re
from dataclasses import dataclass
from datetime import date

from fastapi import HTTPException

from app.modules.surplus.models import SurplusMaterial

log = logging.getLogger(__name__)

MODEL = os.getenv("IZLISHEK_VISION_MODEL", "claude-opus-5-5")

# Латиниця, схожа на кирилицю: у зошитах «AL»/«АЛ», «Cu»/«Са» пишуть як завгодно.
_LOOKALIKE = str.maketrans({"а": "a", "с": "c", "е": "e", "о": "o", "р": "p", "х": "x", "к": "k",
                            "і": "i", "у": "y", "т": "t", "м": "m", "н": "h", "в": "b", "ї": "i", "ё": "e"})
_NUM = re.compile(r"\d+(?:[.,]\d+)?")
_DATE_LINE = re.compile(r"^\s*(\d{1,2})[.,/](\d{1,2})(?:[.,/](\d{2,4}))?\s*$")


def _norm(s: str) -> str:
    return re.sub(r"\s+", " ", s.lower().translate(_LOOKALIKE)).strip()


def _tokens(s: str) -> list[str]:
    return [t for t in re.split(r"[^\w]+", s) if t]


@dataclass
class Item:
    raw: str
    material_id: int | None
    kg: float | None
    kg2: float | None


class Matcher:
    def __init__(self, materials: list[SurplusMaterial]):
        self.entries: list[tuple[str, int]] = []
        for m in materials:
            names = [m.name, *(m.aliases or "").split(",")]
            for a in names:
                a = _norm(a)
                if a:
                    self.entries.append((a, m.id))
        self.entries.sort(key=lambda e: -len(e[0]))
        self.by_name = {m.name: m.id for m in materials}

    def match(self, raw: str) -> int | None:
        n = _norm(raw)
        if not n:
            return None
        toks = set(_tokens(n))
        for alias, mid in self.entries:
            # Короткі аліаси («al», «cu») — лише цілим словом, інакше ловлять що завгодно.
            if len(alias) <= 3:
                if alias in toks:
                    return mid
            elif alias in n:
                return mid
        return None


def _num(s: str) -> float:
    return float(s.replace(",", "."))


def _parse_date(d: str, m: str, y: str | None) -> date | None:
    try:
        year = int(y) if y else date.today().year
        if year < 100:
            year += 2000
        return date(year, int(m), int(d))
    except ValueError:
        return None


def parse_text(text: str, matcher: Matcher) -> tuple[date | None, list[Item]]:
    found_date: date | None = None
    items: list[Item] = []
    for line in text.splitlines():
        line = line.strip().strip("|•-*")
        if not line:
            continue
        dm = _DATE_LINE.match(line)
        if dm:
            found_date = found_date or _parse_date(*dm.groups())
            continue
        first = _NUM.search(line)
        if not first:
            continue
        name = line[: first.start()].strip(" :=-–|\t")
        nums = [_num(x) for x in _NUM.findall(line[first.start():])]
        if not name or not re.search(r"[^\W\d_]", name):
            continue
        items.append(Item(raw=name, material_id=matcher.match(name), kg=nums[0],
                          kg2=nums[1] if len(nums) > 1 else None))
    return found_date, items


# ── Фото через Claude ───────────────────────────────────────────────────────
def _schema(material_names: list[str]) -> dict:
    return {
        "type": "object",
        "properties": {
            "date": {"type": ["string", "null"], "description": "Дата з документа як DD.MM або DD.MM.YYYY, якщо є"},
            "rows": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {
                        "raw": {"type": "string", "description": "Назва матеріалу так, як написано"},
                        "material": {"type": "string", "enum": [*material_names, ""]},
                        "kg": {"type": ["number", "null"]},
                        "kg2": {"type": ["number", "null"]},
                    },
                    "required": ["raw", "material", "kg", "kg2"],
                    "additionalProperties": False,
                },
            },
        },
        "required": ["date", "rows"],
        "additionalProperties": False,
    }


_PROMPT = """На фото — облік брухту кольорових металів: рукописний зошит, скрін програми, \
повідомлення або накладна. Випиши кожен рядок «матеріал — вага в кг».

Правила:
- raw: назва так, як написано (AL, Cu/Са, латунь, AL банка, AL (посуда, профіль), титан, нерж, ЦАМ тощо).
- material: найближчий матеріал із довідника нижче; якщо не впевнений — порожній рядок.
  «AL банка», «AL посуда/профіль» — окремі матеріали, не плутай зі звичайним AL.
- kg: перша вага в рядку. Кома — десятковий роздільник (71,9 = 71.9).
- kg2: якщо в рядку є ДРУГА колонка ваги (напр. дві колонки «Я | ДМС»), то друга вага; інакше null.
- Підсумкові рядки («разом», «всього») не виписуй. Нічого не вигадуй: нерозбірливе — пропусти.
- date: дата на документі, якщо видно.

Довідник матеріалів: {names}"""


async def parse_images(images: list[tuple[bytes, str]], materials: list[SurplusMaterial], matcher: Matcher) -> tuple[date | None, list[Item]]:
    if not os.getenv("ANTHROPIC_API_KEY"):
        raise HTTPException(503, "Розпізнавання фото не налаштоване (немає ANTHROPIC_API_KEY). Вставте текстом.")
    import anthropic  # лінивий імпорт: без ключа модуль не потрібен

    names = [m.name for m in materials if m.is_active]
    content: list[dict] = []
    for data, media_type in images:
        content.append({"type": "image", "source": {"type": "base64", "media_type": media_type,
                                                    "data": base64.standard_b64encode(data).decode()}})
    content.append({"type": "text", "text": _PROMPT.format(names=", ".join(names))})

    client = anthropic.AsyncAnthropic()
    try:
        resp = await client.beta.messages.create(
            model=MODEL,
            max_tokens=8000,
            betas=["server-side-fallback-2026-07-01"],
            fallbacks="default",
            output_config={"effort": "low", "format": {"type": "json_schema", "schema": _schema(names)}},
            messages=[{"role": "user", "content": content}],
        )
    except anthropic.RateLimitError:
        raise HTTPException(429, "Забагато запитів на розпізнавання — спробуйте за хвилину") from None
    except anthropic.APIStatusError as e:
        log.warning("claude error %s: %s", e.status_code, e.message)
        raise HTTPException(502, "Сервіс розпізнавання повернув помилку. Спробуйте ще раз або вставте текстом.") from None
    except anthropic.APIConnectionError:
        raise HTTPException(502, "Немає зʼєднання із сервісом розпізнавання") from None

    if resp.stop_reason == "refusal":
        raise HTTPException(422, "Не вдалося розпізнати це фото")
    text = next((b.text for b in resp.content if b.type == "text"), "")
    try:
        data = json.loads(text)
    except json.JSONDecodeError:
        raise HTTPException(422, "Не вдалося розпізнати фото — спробуйте чіткіше або вставте текстом") from None

    by_name = {m.name: m.id for m in materials}
    items = [
        Item(raw=r["raw"], material_id=by_name.get(r["material"]) or matcher.match(r["raw"]), kg=r["kg"], kg2=r["kg2"])
        for r in data.get("rows", [])
        if r.get("kg") is not None
    ]
    found_date = None
    if data.get("date"):
        dm = re.match(r"\s*(\d{1,2})[.,/](\d{1,2})(?:[.,/](\d{2,4}))?", data["date"])
        if dm:
            found_date = _parse_date(*dm.groups())
    return found_date, items
