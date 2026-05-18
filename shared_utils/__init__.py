"""
Shared utilities for Smart Open Air Garden services.
Provides common functionality for data validation, standardized responses, and message handling.
"""

from .validation import (
    StandardizedResponse,
    SchemaValidator,
    MessageValidator,
    ResponseFormatter,
    validate_http_status,
    get_error_status_code,
)

__all__ = [
    'StandardizedResponse',
    'SchemaValidator',
    'MessageValidator',
    'ResponseFormatter',
    'validate_http_status',
    'get_error_status_code',
]

__version__ = '1.0.0'
