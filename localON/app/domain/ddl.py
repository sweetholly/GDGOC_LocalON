from __future__ import annotations

import re
from pathlib import Path
from typing import TYPE_CHECKING, Sequence

if TYPE_CHECKING:
    from sqlalchemy.engine import Engine
    from sqlalchemy.ext.asyncio import AsyncEngine


_DDL_SOURCE = "LOCAL_ON_DDL_v3_final.sql"
_DDL_PATTERN = re.compile(
    r"CREATE\s+TABLE\s+IF\s+NOT\s+EXISTS\s+`[^`]+`\s*\(.*?\)\s*ENGINE\s*=\s*InnoDB\b.*?;",
    flags=re.IGNORECASE | re.DOTALL,
)
_ENCODINGS = ("utf-8", "utf-8-sig", "cp949", "euc-kr")


def get_source_path() -> Path:
    return Path(__file__).resolve().parents[2] / "DB_structure" / _DDL_SOURCE


def read_source_sql(path: Path | None = None) -> str:
    source = path or get_source_path()
    last_error: UnicodeDecodeError | None = None

    for encoding in _ENCODINGS:
        try:
            return source.read_text(encoding=encoding)
        except UnicodeDecodeError as exc:
            last_error = exc

    if last_error:
        raise last_error
    raise FileNotFoundError(source)


def extract_table_ddl(raw_sql: str) -> list[str]:
    statements = [match.strip() for match in _DDL_PATTERN.findall(raw_sql)]
    if not statements:
        raise ValueError("Could not find CREATE TABLE statements in the DDL source.")
    return statements


def load_table_ddl(path: Path | None = None) -> list[str]:
    return extract_table_ddl(read_source_sql(path))


def render_table_ddl(path: Path | None = None) -> str:
    return "\n\n".join(load_table_ddl(path)) + "\n"


def apply_ddl(engine: Engine, statements: Sequence[str] | None = None) -> int:
    from sqlalchemy import text

    ddl_statements = list(statements or load_table_ddl())
    with engine.begin() as conn:
        for stmt in ddl_statements:
            conn.execute(text(stmt))
    return len(ddl_statements)


async def apply_ddl_async(
    async_engine: AsyncEngine,
    statements: Sequence[str] | None = None,
) -> int:
    from sqlalchemy import text

    ddl_statements = list(statements or load_table_ddl())
    async with async_engine.begin() as conn:
        for stmt in ddl_statements:
            await conn.execute(text(stmt))
    return len(ddl_statements)
