from __future__ import annotations

import uvicorn

from app.core.app import create_app

app = create_app()

if __name__ == "__main__":
    uvicorn.run("api:app", host="0.0.0.0", port=8000, reload=True)
