"""
Shared utilities for data validation and standardized responses.
Provides JSON Schema validation and standardized error/success response formatting.
"""

import json
import logging
from typing import Any, Dict, Optional, Tuple
import jsonschema
from jsonschema import validate, ValidationError, Draft7Validator
from datetime import datetime


class StandardizedResponse:
    """Helper class for creating standardized API responses."""
    
    @staticmethod
    def success(data: Any, message: Optional[str] = None) -> Dict[str, Any]:
        """
        Create a standardized success response.
        
        Args:
            data: Response payload (dict, list, string, number, bool)
            message: Optional human-readable message
            
        Returns:
            Standardized success response dictionary
        """
        response = {
            "status": "success",
            "data": data
        }
        if message:
            response["message"] = message
        return response
    
    @staticmethod
    def error(code: str, message: str, details: Optional[Dict] = None, 
              status_code: int = 500) -> Tuple[Dict[str, Any], int]:
        """
        Create a standardized error response.
        
        Args:
            code: Error code (e.g., 'VALIDATION_ERROR', 'NOT_FOUND')
            message: Human-readable error message
            details: Optional additional error context
            status_code: HTTP status code
            
        Returns:
            Tuple of (response dictionary, HTTP status code)
        """
        response = {
            "status": "error",
            "code": code,
            "message": message
        }
        if details:
            response["details"] = details
        return response, status_code


class SchemaValidator:
    """Helper class for validating data against JSON schemas."""
    
    def __init__(self, logger: Optional[logging.Logger] = None):
        """
        Initialize validator with optional logger.
        
        Args:
            logger: Optional logger instance for error logging
        """
        self.logger = logger or logging.getLogger(__name__)
        self.schemas = {}
    
    def load_schema(self, schema_name: str, schema_path: str) -> bool:
        """
        Load a JSON schema from file.
        
        Args:
            schema_name: Name to reference the schema by
            schema_path: Path to the schema JSON file
            
        Returns:
            True if successful, False if loading failed
        """
        try:
            with open(schema_path, 'r') as f:
                self.schemas[schema_name] = json.load(f)
            self.logger.info(f"✓ Schema loaded: {schema_name}")
            return True
        except Exception as e:
            self.logger.error(f"✗ Failed to load schema {schema_name}: {e}")
            return False
    
    def validate(self, data: Any, schema_name: str) -> Tuple[bool, Optional[str]]:
        """
        Validate data against a loaded schema.
        
        Args:
            data: Data to validate
            schema_name: Name of the schema to validate against
            
        Returns:
            Tuple of (is_valid, error_message)
        """
        if schema_name not in self.schemas:
            error_msg = f"Schema '{schema_name}' not loaded"
            self.logger.error(error_msg)
            return False, error_msg
        
        try:
            schema = self.schemas[schema_name]
            validate(instance=data, schema=schema)
            return True, None
        except ValidationError as e:
            error_msg = f"Validation error in {e.path}: {e.message}"
            self.logger.warning(f"Validation failed for {schema_name}: {error_msg}")
            return False, error_msg
        except Exception as e:
            error_msg = f"Unexpected validation error: {str(e)}"
            self.logger.error(error_msg)
            return False, error_msg
    
    def validate_and_respond(self, data: Any, schema_name: str) -> Tuple[bool, Any]:
        """
        Validate data and return standardized response.
        
        Args:
            data: Data to validate
            schema_name: Name of the schema to validate against
            
        Returns:
            Tuple of (is_valid, response_dict_or_error_tuple)
            If valid: (True, None)
            If invalid: (False, (error_response_dict, 400))
        """
        is_valid, error_msg = self.validate(data, schema_name)
        
        if not is_valid:
            response = StandardizedResponse.error(
                code="VALIDATION_ERROR",
                message=f"Invalid {schema_name} format",
                details={"error": error_msg},
                status_code=400
            )
            return False, response
        
        return True, None


class MessageValidator:
    """Specific validator for MQTT and other system messages."""
    
    def __init__(self, logger: Optional[logging.Logger] = None):
        """Initialize message validator."""
        self.logger = logger or logging.getLogger(__name__)
    
    @staticmethod
    def validate_senml_message(data: Any) -> Tuple[bool, Optional[str]]:
        """
        Validate SenML format message.
        
        Args:
            data: Message data to validate
            
        Returns:
            Tuple of (is_valid, error_message)
        """
        try:
            # Must be a list (array)
            if not isinstance(data, list):
                return False, "SenML message must be a JSON array"
            
            if len(data) == 0:
                return False, "SenML message must contain at least one entry"
            
            # Validate each entry
            for idx, entry in enumerate(data):
                if not isinstance(entry, dict):
                    return False, f"Entry {idx} is not a JSON object"
                
                # Check required fields
                if "n" not in entry:
                    return False, f"Entry {idx} missing required field 'n' (name)"
                
                if "v" not in entry:
                    return False, f"Entry {idx} missing required field 'v' (value)"
                
                if "t" not in entry:
                    return False, f"Entry {idx} missing required field 't' (timestamp)"
                
                # Validate name
                valid_names = ["temperature", "air_humidity", "soil_moisture", "pump_status"]
                if entry["n"] not in valid_names:
                    return False, f"Entry {idx}: invalid measurement name '{entry['n']}'"
                
                # Validate timestamp
                try:
                    t_value = entry["t"]
                    if not isinstance(t_value, int):
                        return False, f"Entry {idx}: timestamp must be integer"
                    if t_value < 0:
                        return False, f"Entry {idx}: timestamp must be non-negative"
                except (TypeError, ValueError):
                    return False, f"Entry {idx}: invalid timestamp format"
            
            return True, None
            
        except Exception as e:
            return False, f"Unexpected validation error: {str(e)}"
    
    @staticmethod
    def validate_fault_alert(data: Any) -> Tuple[bool, Optional[str]]:
        """
        Validate fault alert message format.
        
        Args:
            data: Message data to validate
            
        Returns:
            Tuple of (is_valid, error_message)
        """
        try:
            if not isinstance(data, dict):
                return False, "Fault alert must be a JSON object"
            
            required_fields = ["target", "error", "val_now", "val_init", "time_iso"]
            for field in required_fields:
                if field not in data:
                    return False, f"Missing required field '{field}'"
            
            if data["error"] != "PUMP_FAILURE_OR_LEAK":
                return False, f"Invalid error type: '{data['error']}'"
            
            # Validate numeric fields
            for field in ["val_now", "val_init"]:
                try:
                    val = float(data[field])
                    if val < 0 or val > 100:
                        return False, f"Field '{field}' must be between 0 and 100"
                except (TypeError, ValueError):
                    return False, f"Field '{field}' must be numeric"
            
            # Validate ISO timestamp format
            try:
                datetime.fromisoformat(data["time_iso"].replace("Z", "+00:00"))
            except (ValueError, AttributeError):
                return False, f"Invalid ISO 8601 timestamp format"
            
            return True, None
            
        except Exception as e:
            return False, f"Unexpected validation error: {str(e)}"


class ResponseFormatter:
    """Helper for formatting various response types."""
    
    @staticmethod
    def format_error_response(code: str, message: str, details: Optional[Dict] = None) -> Dict[str, Any]:
        """
        Format a standardized error response.
        
        Args:
            code: Error code
            message: Error message
            details: Optional details dict
            
        Returns:
            Formatted error response
        """
        return StandardizedResponse.error(code, message, details)[0]
    
    @staticmethod
    def format_success_response(data: Any, message: Optional[str] = None) -> Dict[str, Any]:
        """
        Format a standardized success response.
        
        Args:
            data: Response data
            message: Optional message
            
        Returns:
            Formatted success response
        """
        return StandardizedResponse.success(data, message)
    
    @staticmethod
    def format_list_response(items: list, message: Optional[str] = None) -> Dict[str, Any]:
        """
        Format a list response with optional count message.
        
        Args:
            items: List of items
            message: Optional message (auto-generated if not provided)
            
        Returns:
            Formatted response
        """
        if not message and items:
            count = len(items)
            item_word = "item" if count == 1 else "items"
            message = f"Retrieved {count} {item_word}"
        
        return StandardizedResponse.success(items, message)


def validate_http_status(status_code: int) -> bool:
    """
    Validate that HTTP status code is appropriate.
    
    Args:
        status_code: HTTP status code
        
    Returns:
        True if status code is valid
    """
    return 100 <= status_code <= 599


def get_error_status_code(error_code: str) -> int:
    """
    Get appropriate HTTP status code for error code.
    
    Args:
        error_code: Error code string
        
    Returns:
        HTTP status code
    """
    error_status_map = {
        "VALIDATION_ERROR": 400,
        "INVALID_OPERATION": 400,
        "NOT_FOUND": 404,
        "CONFLICT": 409,
        "DUPLICATE_ID": 409,
        "DEVICE_IN_USE": 409,
        "SERVER_ERROR": 500,
    }
    return error_status_map.get(error_code, 500)
