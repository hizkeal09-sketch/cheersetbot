"""Middleware package."""

from app.middlewares.db import DatabaseSessionMiddleware
from app.middlewares.errors import error_handler
from app.middlewares.gate import RegistrationGateMiddleware
from app.middlewares.throttle import ThrottlingMiddleware
from app.middlewares.user import UserMiddleware

__all__ = [
    "DatabaseSessionMiddleware",
    "RegistrationGateMiddleware",
    "ThrottlingMiddleware",
    "UserMiddleware",
    "error_handler",
]
