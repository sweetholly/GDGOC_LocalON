from __future__ import annotations

from fastapi import FastAPI, HTTPException, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse

from app.router import areas_router, mainpage_router, search_router


def create_app() -> FastAPI:
    app = FastAPI(
        title='LOCAL ON API',
        version='1.0.0',
        description='Real-time Seoul citydata based congestion information API',
    )

    app.include_router(mainpage_router, tags=['main'])
    app.include_router(areas_router, tags=['areas'])
    app.include_router(search_router, tags=['search'])

    @app.exception_handler(HTTPException)
    async def http_exception_handler(request: Request, exc: HTTPException) -> JSONResponse:
        if isinstance(exc.detail, dict):
            return JSONResponse(status_code=exc.status_code, content=exc.detail)
        return JSONResponse(
            status_code=exc.status_code,
            content={'error': 'HTTP_ERROR', 'message': str(exc.detail)},
        )

    @app.exception_handler(RequestValidationError)
    async def validation_exception_handler(request: Request, exc: RequestValidationError) -> JSONResponse:
        return JSONResponse(
            status_code=422,
            content={'error': 'BAD_REQUEST', 'message': str(exc.errors())},
        )

    @app.exception_handler(Exception)
    async def generic_exception_handler(request: Request, exc: Exception) -> JSONResponse:
        return JSONResponse(
            status_code=500,
            content={'error': 'INTERNAL_ERROR', 'message': '서버 내부 오류가 발생했습니다'},
        )

    return app
