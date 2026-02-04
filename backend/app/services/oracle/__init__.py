# app/services/oracle/__init__.py
"""
Oracle system for external match result verification.
"""
from .base import (
    OracleProvider,
    MatchResult,
    OracleException,
    MatchNotFoundException,
    OracleAPIException
)
from .factory import OracleFactory
from .service import OracleService

__all__ = [
    "OracleProvider",
    "MatchResult",
    "OracleException",
    "MatchNotFoundException",
    "OracleAPIException",
    "OracleFactory",
    "OracleService",
]