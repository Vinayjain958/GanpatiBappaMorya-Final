"""Structured error handling foundation.

Every error response follows the same JSON shape so the frontend's
ApiError normalization (apps/web/lib/api/client.ts) can rely on it.
No domain-specific error types exist yet — those are added alongside
their owning module in later phases.
"""

from __future__ import annotations

from fastapi import FastAPI, Request, status
from fastapi.encoders import jsonable_encoder
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse


class ApiError(Exception):
    def __init__(self, message: str, status_code: int = status.HTTP_400_BAD_REQUEST) -> None:
        super().__init__(message)
        self.message = message
        self.status_code = status_code


def register_error_handlers(app: FastAPI) -> None:
    @app.exception_handler(ApiError)
    async def handle_api_error(_: Request, exc: ApiError) -> JSONResponse:
        return JSONResponse(status_code=exc.status_code, content={"message": exc.message})

    @app.exception_handler(RequestValidationError)
    async def handle_validation_error(_: Request, exc: RequestValidationError) -> JSONResponse:
        # Pydantic v2 puts the raised exception object itself in
        # ctx["error"] for model_validator ValueErrors, which is not
        # JSON-serializable — drop it (the "msg" field already carries
        # the human-readable text) rather than let json.dumps crash.
        safe_errors = []
        for error in exc.errors():
            error = dict(error)
            error.pop("ctx", None)
            safe_errors.append(jsonable_encoder(error))
        return JSONResponse(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            content={"message": "Validation failed", "detail": safe_errors},
        )

    @app.exception_handler(Exception)
    async def handle_unexpected_error(_: Request, exc: Exception) -> JSONResponse:
        return JSONResponse(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            content={"message": "Internal server error"},
        )
