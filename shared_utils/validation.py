"""
Shared helper functions for the project.
Has tools to check if data is in the right format and to build standard responses.
"""

import json
import logging
from typing import Any, Dict, Optional, Tuple
import jsonschema
from jsonschema import validate, ValidationError, Draft7Validator
from datetime import datetime


class StandardizedResponse:
    """Helps us build JSON responses that always have the same structure."""
    
    @staticmethod
    def success(data, message=None):
        """Wraps the data in a success response with status 'success'."""
        response = {
            "status": "success",
            "data": data
        }
        if message:
            response["message"] = message
        return response
    
    @staticmethod
    def error(code, message, details=None, status_code=500):
        """Wraps error info in a standard error response with an HTTP code."""
        response = {
            "status": "error",
            "code": code,
            "message": message
        }
        if details:
            response["details"] = details
        return response, status_code


class SchemaValidator:
    """Checks if incoming data matches a JSON schema we defined."""
    
    def __init__(self, logger=None):
        """Sets up the validator. You can pass a logger if you want to see errors."""
        self.logger = logger or logging.getLogger(__name__)
        self.schemas = {}
    
    def load_schema(self, schema_name, schema_path):
        """Loads a JSON schema file so we can use it to validate data later."""
        try:
            with open(schema_path, 'r') as f:
                self.schemas[schema_name] = json.load(f)
            self.logger.info(f"✓ Schema loaded: {schema_name}")
            return True
        except Exception as e:
            self.logger.error(f"✗ Failed to load schema {schema_name}: {e}")
            return False
    
    def validate(self, data, schema_name):
        """Checks if the data matches the rules in the schema. Returns True/False and an error message."""
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
    
    def validate_and_respond(self, data, schema_name):
        """Validates data and returns a ready-to-send error response if something is wrong."""
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
    """Checks if MQTT messages have the right fields and values."""
    
    def __init__(self, logger=None):
        """Sets up the validator."""
        self.logger = logger or logging.getLogger(__name__)
    
    @staticmethod
    def validate_senml_message(data):
        """Makes sure a SenML message is a valid list with the right fields (n, v, t)."""
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
    def validate_fault_alert(data):
        """Makes sure a fault alert has all required fields like error type and moisture values."""
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
    """Shortcuts to quickly format success or error responses."""
    
    @staticmethod
    def format_error_response(code, message, details=None):
        """Builds a standard error response dictionary."""
        return StandardizedResponse.error(code, message, details)[0]
    
    @staticmethod
    def format_success_response(data, message=None):
        """Builds a standard success response dictionary."""
        return StandardizedResponse.success(data, message)
    
    @staticmethod
    def format_list_response(items, message=None):
        """Builds a response for a list of items, adding a count message automatically."""
        if not message and items:
            count = len(items)
            item_word = "item" if count == 1 else "items"
            message = f"Retrieved {count} {item_word}"
        
        return StandardizedResponse.success(items, message)


def validate_http_status(status_code):
    """Checks if the given HTTP status code is a valid one (between 100 and 599)."""
    return 100 <= status_code <= 599


def get_error_status_code(error_code):
    """Returns the right HTTP code for a given error type (like 404 for NOT_FOUND)."""
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
