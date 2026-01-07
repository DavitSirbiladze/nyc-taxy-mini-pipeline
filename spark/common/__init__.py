"""
NYC Taxi Pipeline - Common Utilities Module

This module contains shared utilities and configurations:
- config: Configuration management
- spark_session: Spark session factory
"""

__version__ = "1.0.0"

from .config import PipelineConfig, StorageConfig, DatabaseConfig
from .spark_session import get_spark_session

__all__ = [
    "PipelineConfig",
    "StorageConfig",
    "DatabaseConfig",
    "get_spark_session",
]