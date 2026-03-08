# Domain ORM + DDL Usage

`app/domain` now includes SQLAlchemy ORM classes that map all tables in
`DB_structure/LOCAL_ON_DDL_v3_final.sql`.

## ORM files

- `base.py`: `DeclarativeBase`
- `models_master.py`: master/ingestion/mapping tables
- `models_citydata_live.py`: citydata 1:1 tables
- `models_citydata_detail_a.py`: citydata 1:n tables (part A)
- `models_citydata_detail_b.py`: citydata 1:n tables (part B)
- `models_analytics.py`: sdot/read-model/optional tables

## Create schema from ORM

```python
from sqlalchemy import create_engine
from app.domain import Base

engine = create_engine("mysql+pymysql://user:password@localhost:3306/local_on")
Base.metadata.create_all(bind=engine)
```

## FastAPI async session dependency

```python
from fastapi import Depends, FastAPI
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.domain import create_schema, get_db

app = FastAPI()

@app.on_event("startup")
async def startup() -> None:
    await create_schema()

@app.get("/health/db")
async def health_db(db: AsyncSession = Depends(get_db)) -> dict[str, bool]:
    await db.execute(text("SELECT 1"))
    return {"ok": True}
```

## Create schema from DDL source

```python
from sqlalchemy.ext.asyncio import create_async_engine
from app.domain import apply_ddl_async

engine = create_async_engine("mysql+aiomysql://user:password@localhost:3306/local_on")
await apply_ddl_async(engine)
```
