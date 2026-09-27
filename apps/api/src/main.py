"""ASGI entry point. Run with: uvicorn src.main:app --reload"""

from __future__ import annotations

from src.core.app import create_app

app = create_app()
