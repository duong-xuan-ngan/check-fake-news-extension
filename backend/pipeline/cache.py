"""Compatibility façade for the backend-local semantic cache."""
from app.cache import get, set

__all__ = ["get", "set"]
