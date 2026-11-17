"""Мінімальна «міграція» без Alembic: додає нові колонки в уже існуючі таблиці.

create_all створює лише відсутні ТАБЛИЦІ; якщо база вже жила (Render), нові
поля моделей треба долити ALTER TABLE ... ADD COLUMN. Лише додавання з
дефолтом — нічого не видаляємо і не змінюємо.
"""
from __future__ import annotations

from sqlalchemy import inspect
from sqlalchemy.engine import Connection
from sqlalchemy.schema import CreateColumn

from app.shared.database import Base


def add_missing_columns(conn: Connection) -> list[str]:
    insp = inspect(conn)
    added: list[str] = []
    for table in Base.metadata.sorted_tables:
        if not insp.has_table(table.name):
            continue
        have = {c["name"] for c in insp.get_columns(table.name)}
        for col in table.columns:
            if col.name in have:
                continue
            ddl = str(CreateColumn(col).compile(dialect=conn.dialect))
            if not col.nullable and col.server_default is None:
                ddl = ddl.replace(" NOT NULL", "")  # без дефолту NOT NULL на заповненій таблиці не додати
            conn.exec_driver_sql(f'ALTER TABLE "{table.name}" ADD COLUMN {ddl}')
            added.append(f"{table.name}.{col.name}")
    return added
