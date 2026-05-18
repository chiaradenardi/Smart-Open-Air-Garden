"""
Shared utilities for the Smart Open Air Garden project.
Contains helpers for validating data and formatting API responses.
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
