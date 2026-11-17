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
from app.shared.i18n import L

log = logging.getLogger(__name__)

MODEL = os.getenv("IZLISHEK_VISION_MODEL", "claude-opus-5-5")

# Латиниця, схожа на кирилицю: у зошитах «AL»/«АЛ», «Cu»/«Са» пишуть як завгодно.
_LOOKALIKE = str.maketrans({"а": "a", "с": "c", "е": "e", "о": "o", "р": "p", "х": "x", "к": "k",
                            "і": "i", "у": "y", "т": "t", "м": "m", "н": "h", "в": "b", "ї": "i", "ё": "e"})
_NUM = re.compile(r"\d+(?:[.,]\d+)?")
_KG = re.compile(r"\b(?:кг|kg)\b\.?", re.IGNORECASE)
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

    def best(self, raw: str) -> tuple[int, int, int] | None:
        """(material_id, довжина аліаса, позиція в назві) найкращого збігу або None."""
        n = _norm(raw)
        if not n:
            return None
        toks = _tokens(n)
        for alias, mid in self.entries:  # відсортовано від найдовших
            # Короткі аліаси («al», «cu») — лише цілим словом, інакше ловлять що завгодно.
            if len(alias) <= 3 and alias.isalnum():
                if alias in toks:
                    return mid, len(alias), n.find(alias)
            elif alias in n:
                return mid, len(alias), n.find(alias)
        return None

    def match(self, raw: str) -> int | None:
        b = self.best(raw)
        return b[0] if b else None


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


_NUM_TOKEN = re.compile(r"^\d+(?:[.,]\d+)?$")


def _tokenize(chunk: str) -> list[str]:
    chunk = _KG.sub(" ", chunk)
    chunk = re.sub(r"(\d)\s*[/|]\s*(\d)", r"\1 \2", chunk)        # «71,9/65,7» → дві ваги
    chunk = re.sub(r"\s[:=–\-|/]\s|[:=]", " ", chunk)                # роздільники між назвою і вагою
    toks = [x.strip(",.;:") if _NUM_TOKEN.match(x.strip(",.;:")) else x.rstrip(",;:") for x in chunk.split()]
    return [x for x in toks if x]


def _split_groups(toks: list[str], matcher: Matcher) -> list[tuple[str, list[float]]]:
    """Ділить послідовність токенів на групи «назва вага [вага2]».

    Дозволяє писати все в один рядок («AL 71,9 Cu 37,85 Латунь 34,45»), не ламаючи
    назви з числами («Медь 1 сорт 37,85»): з кількох можливих меж обираємо ту, де назва
    найкраще впізнається; назва з числом усередині має починатися з упізнаного аліаса.
    """
    is_num = [bool(_NUM_TOKEN.match(x)) for x in toks]
    groups: list[tuple[str, list[float]]] = []
    i = 0
    while i < len(toks):
        while i < len(toks) and is_num[i]:   # числа без назви на початку — пропускаємо
            i += 1
        if i >= len(toks):
            break
        best: tuple[tuple[int, int], int, str, list[float]] | None = None
        for j in range(i + 1, len(toks) + 1):
            # межа: після числа, і далі слово або кінець
            if not is_num[j - 1] or (j < len(toks) and is_num[j]):
                continue
            k = j
            while k > i and is_num[k - 1] and j - k < 2:
                k -= 1
            name_toks, nums = toks[i:k], [_num(x) for x in toks[k:j]]
            if not name_toks:
                continue
            name = " ".join(name_toks)
            if not re.search(r"[^\W\d_]", name):
                continue
            m = matcher.best(name)
            inner_num = any(is_num[x] for x in range(i, k))
            if m and inner_num and m[2] != 0:
                m = None  # «АЛ 5 АЛ профиль» — це дві групи, а не одна назва
            score = (m[1] if m else 0, -j)
            if best is None or score > best[0]:
                best = (score, j, name, nums)
        if best is None:
            break
        _, j, name, nums = best
        groups.append((name, nums))
        i = j
    return groups


def parse_text(text: str, matcher: Matcher) -> tuple[date | None, list[Item]]:
    """Текст будь-якого вигляду: по рядку на матеріал, через «;» або все в один рядок."""
    found_date: date | None = None
    items: list[Item] = []
    for chunk in re.split(r"[\n;]+", text):
        chunk = chunk.strip().strip("|•*")
        if not chunk:
            continue
        dm = _DATE_LINE.match(chunk)
        if dm:
            found_date = found_date or _parse_date(*dm.groups())
            continue
        # дата на початку рядка: «03.07 AL 71,9 …»
        dm = re.match(r"^\s*(\d{1,2})\.(\d{2})(?:\.(\d{2,4}))?\s+(?=[^\W\d_])", chunk)
        if dm:
            found_date = found_date or _parse_date(*dm.groups())
            chunk = chunk[dm.end():]
        for name, nums in _split_groups(_tokenize(chunk), matcher):
            name = name.strip(" :=-–|\t")
            items.append(Item(raw=name, material_id=matcher.match(name), kg=nums[0],
                              kg2=nums[1] if len(nums) > 1 else None))
    return found_date, items


def parse_table(rows: list[list], matcher: Matcher) -> list[Item]:
    """Рядки таблиці (Excel/CSV): перша текстова клітинка — назва, наступні числа — ваги."""
    items: list[Item] = []
    for row in rows:
        name, nums = None, []
        for cell in row:
            if cell is None or (isinstance(cell, str) and not cell.strip()):
                continue
            if isinstance(cell, (int, float)) and not isinstance(cell, bool):
                if name:
                    nums.append(float(cell))
                continue
            s = str(cell).strip()
            if _NUM_TOKEN.match(s):
                if name:
                    nums.append(_num(s))
            elif name is None and re.search(r"[^\W\d_]", s):
                name = s
        if name and nums:
            items.append(Item(raw=name, material_id=matcher.match(name), kg=nums[0],
                              kg2=nums[1] if len(nums) > 1 else None))
    return items


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
        raise HTTPException(503, L("Розпізнавання фото не налаштоване (немає ANTHROPIC_API_KEY). Вставте текстом.", "Распознавание фото не настроено (нет ANTHROPIC_API_KEY). Вставьте текстом."))
    import anthropic  # лінивий імпорт: без ключа модуль не потрібен

    names = [m.name for m in materials if m.is_active]
    content: list[dict] = []
    for data, media_type in images:
        kind = "document" if media_type == "application/pdf" else "image"
        content.append({"type": kind, "source": {"type": "base64", "media_type": media_type,
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
        raise HTTPException(429, L("Забагато запитів на розпізнавання — спробуйте за хвилину", "Слишком много запросов на распознавание — попробуйте через минуту")) from None
    except anthropic.APIStatusError as e:
        log.warning("claude error %s: %s", e.status_code, e.message)
        raise HTTPException(502, L("Сервіс розпізнавання повернув помилку. Спробуйте ще раз або вставте текстом.", "Сервис распознавания вернул ошибку. Попробуйте ещё раз или вставьте текстом.")) from None
    except anthropic.APIConnectionError:
        raise HTTPException(502, L("Немає зʼєднання із сервісом розпізнавання", "Нет соединения с сервисом распознавания")) from None

    if resp.stop_reason == "refusal":
        raise HTTPException(422, L("Не вдалося розпізнати це фото", "Не удалось распознать это фото"))
    text = next((b.text for b in resp.content if b.type == "text"), "")
    try:
        data = json.loads(text)
    except json.JSONDecodeError:
        raise HTTPException(422, L("Не вдалося розпізнати фото — спробуйте чіткіше або вставте текстом", "Не удалось распознать фото — попробуйте чётче или вставьте текстом")) from None

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
