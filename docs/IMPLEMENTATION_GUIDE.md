# Implementation Guide: Data Format Standards

This guide helps developers implement standardized data formats and validation in their services.

## Quick Start for Service Developers

### Step 1: Use Standardized Response Format

Instead of:
```python
# Old way - inconsistent
return json.dumps({"result": "success", "data": {...}})
return json.dumps({"error": "message"})
```

Use:
```python
from shared_utils import StandardizedResponse, ResponseFormatter

# Success response
response = ResponseFormatter.format_success_response(
    data={"slotID": "slot_1", "plantID": "tomato"},
    message="Slot retrieved successfully"
)
return json.dumps(response)

# Error response
response = ResponseFormatter.format_error_response(
    code="NOT_FOUND",
    message="Slot with ID 'slot_1' not found"
)
return json.dumps(response)
```

### Step 2: Validate Input with Schemas

Instead of:
```python
# Old way - manual validation
if "slotID" not in body_json:
    return json.dumps({"error": "slotID required"})
```

Use:
```python
from shared_utils import SchemaValidator
import logging

# Initialize validator
validator = SchemaValidator(logger=logging.getLogger(__name__))
validator.load_schema("garden_slot", "docs/schemas/garden-slot.schema.json")

# Validate incoming data
is_valid, response = validator.validate_and_respond(request_body, "garden_slot")
if not is_valid:
    return json.dumps(response[0]), response[1]

# Process valid data
process_slot(request_body)
```

### Step 3: Handle MQTT Messages

For SenML messages:
```python
from shared_utils import MessageValidator

validator = MessageValidator(logger=logging.getLogger(__name__))

# Validate SenML telemetry
is_valid, error_msg = validator.validate_senml_message(mqtt_payload)
if not is_valid:
    logger.error(f"Invalid telemetry: {error_msg}")
    return

# Parse and process
for entry in mqtt_payload:
    sensor_name = entry.get("n")
    value = entry.get("v")
    timestamp = entry.get("t")
    process_reading(sensor_name, value, timestamp)
```

For fault alerts:
```python
# Validate fault alert format
is_valid, error_msg = validator.validate_fault_alert(mqtt_payload)
if not is_valid:
    logger.error(f"Invalid fault alert: {error_msg}")
    return

# Process alert
alert_device = mqtt_payload["target"]
alert_type = mqtt_payload["error"]
handle_alert(alert_device, alert_type)
```

## Service-Specific Implementation Examples

### REST API Service (CherryPy)

```python
import cherrypy
import json
import logging
from shared_utils import ResponseFormatter, SchemaValidator, get_error_status_code

class SlotsEndpoint:
    exposed = True
    
    def __init__(self):
        self.logger = logging.getLogger(__name__)
        self.validator = SchemaValidator(self.logger)
        # Load schema if validation needed
    
    def GET(self, *uri, **params):
        """Get garden slots."""
        try:
            slots = self._fetch_slots()
            response = ResponseFormatter.format_list_response(
                items=slots,
                message=f"Retrieved {len(slots)} garden slots"
            )
            return json.dumps(response, indent=2)
        except Exception as e:
            self.logger.error(f"Error fetching slots: {e}")
            response = ResponseFormatter.format_error_response(
                code="SERVER_ERROR",
                message="Failed to retrieve slots",
                details={"error": str(e)}
            )
            cherrypy.response.status = 500
            return json.dumps(response, indent=2)
    
    def POST(self):
        """Create new garden slot."""
        try:
            body = cherrypy.request.body.read().decode('utf-8')
            request_data = json.loads(body)
            
            # Validate request
            required_fields = ["slotID", "plantID", "deviceID"]
            for field in required_fields:
                if field not in request_data:
                    response = ResponseFormatter.format_error_response(
                        code="VALIDATION_ERROR",
                        message="Missing required field",
                        details={"field": field, "required_fields": required_fields}
                    )
                    cherrypy.response.status = 400
                    return json.dumps(response, indent=2)
            
            # Check for conflicts
            if self._slot_exists(request_data["slotID"]):
                response = ResponseFormatter.format_error_response(
                    code="CONFLICT",
                    message="Slot ID already exists",
                    details={"slotID": request_data["slotID"]}
                )
                cherrypy.response.status = 409
                return json.dumps(response, indent=2)
            
            if self._device_in_use(request_data["deviceID"]):
                used_by = self._find_slot_for_device(request_data["deviceID"])
                response = ResponseFormatter.format_error_response(
                    code="DEVICE_IN_USE",
                    message=f"Device already in use by slot '{used_by}'",
                    details={"deviceID": request_data["deviceID"], "used_by_slot": used_by}
                )
                cherrypy.response.status = 409
                return json.dumps(response, indent=2)
            
            # Create slot
            new_slot = self._create_slot(request_data)
            response = ResponseFormatter.format_success_response(
                data=new_slot,
                message="Garden slot created successfully"
            )
            cherrypy.response.status = 201
            return json.dumps(response, indent=2)
            
        except json.JSONDecodeError as e:
            response = ResponseFormatter.format_error_response(
                code="VALIDATION_ERROR",
                message="Invalid JSON format",
                details={"error": str(e)}
            )
            cherrypy.response.status = 400
            return json.dumps(response, indent=2)
        except Exception as e:
            self.logger.error(f"Error creating slot: {e}")
            response = ResponseFormatter.format_error_response(
                code="SERVER_ERROR",
                message="Failed to create slot",
                details={"error": str(e)}
            )
            cherrypy.response.status = 500
            return json.dumps(response, indent=2)
```

### MQTT Service

```python
import json
import logging
from shared_utils import MessageValidator
from MyMQTT import MyMQTT

class SmartIrrigation:
    def __init__(self):
        self.logger = logging.getLogger(__name__)
        self.validator = MessageValidator(self.logger)
        self.client = MyMQTT("SmartIrrigation", "broker", 1883, self)
    
    def notify(self, topic, payload):
        """MQTT message callback."""
        try:
            # Decode and parse
            if isinstance(payload, bytes):
                payload = payload.decode('utf-8')
            
            msg = json.loads(payload)
            
            # Validate based on topic
            if "telemetry" in topic:
                is_valid, error = self.validator.validate_senml_message(msg)
                if not is_valid:
                    self.logger.error(f"Invalid telemetry on {topic}: {error}")
                    return
                self._process_telemetry(topic, msg)
            
            elif "pump" in topic:
                is_valid, error = self.validator.validate_senml_message(msg)
                if not is_valid:
                    self.logger.error(f"Invalid pump command on {topic}: {error}")
                    return
                self._process_pump_command(topic, msg)
            
        except json.JSONDecodeError as e:
            self.logger.error(f"Failed to parse JSON on {topic}: {e}")
        except Exception as e:
            self.logger.error(f"Error processing message on {topic}: {e}")
    
    def _process_telemetry(self, topic, msg):
        """Process valid telemetry message."""
        # Extract device ID
        device_id = topic.split('/')[1]
        
        # Extract sensor readings
        for entry in msg:
            sensor_name = entry.get("n")
            value = entry.get("v")
            timestamp = entry.get("t")
            
            self.logger.debug(f"[{device_id}] {sensor_name}={value}")
            self._handle_sensor_reading(device_id, sensor_name, value, timestamp)
    
    def _process_pump_command(self, topic, msg):
        """Process valid pump command."""
        device_id = topic.split('/')[1]
        
        for entry in msg:
            if entry.get("n") == "pump_status":
                status = entry.get("v")
                action = "ON" if status else "OFF"
                self.logger.info(f"[{device_id}] Pump: {action}")
                self._send_pump_command(device_id, status)
```

### Flask REST Service

```python
from flask import Flask, jsonify, request
import logging
from shared_utils import ResponseFormatter, StandardizedResponse

app = Flask(__name__)
logger = logging.getLogger(__name__)

@app.route('/slots', methods=['GET'])
def get_slots():
    """Get all garden slots."""
    try:
        slots = fetch_slots_from_database()
        return jsonify(ResponseFormatter.format_list_response(slots))
    except Exception as e:
        logger.error(f"Error fetching slots: {e}")
        response, status_code = StandardizedResponse.error(
            code="SERVER_ERROR",
            message="Failed to retrieve slots"
        )
        return jsonify(response), status_code

@app.route('/slots', methods=['POST'])
def create_slot():
    """Create new garden slot."""
    try:
        data = request.get_json()
        
        # Validate required fields
        required = ["slotID", "plantID", "deviceID"]
        if not all(field in data for field in required):
            missing = [f for f in required if f not in data]
            response, status_code = StandardizedResponse.error(
                code="VALIDATION_ERROR",
                message="Missing required fields",
                details={"missing_fields": missing}
            )
            return jsonify(response), status_code
        
        # Create slot
        new_slot = create_slot_in_database(data)
        return jsonify(ResponseFormatter.format_success_response(
            data=new_slot,
            message="Slot created successfully"
        )), 201
        
    except ValueError as e:
        response, status_code = StandardizedResponse.error(
            code="VALIDATION_ERROR",
            message=str(e)
        )
        return jsonify(response), status_code
    except Exception as e:
        logger.error(f"Error creating slot: {e}")
        response, status_code = StandardizedResponse.error(
            code="SERVER_ERROR",
            message="Failed to create slot"
        )
        return jsonify(response), status_code

@app.errorhandler(400)
def bad_request(e):
    """Handle 400 errors."""
    response = ResponseFormatter.format_error_response(
        code="VALIDATION_ERROR",
        message="Bad request"
    )
    return jsonify(response), 400

@app.errorhandler(404)
def not_found(e):
    """Handle 404 errors."""
    response = ResponseFormatter.format_error_response(
        code="NOT_FOUND",
        message="Resource not found"
    )
    return jsonify(response), 404

@app.errorhandler(500)
def server_error(e):
    """Handle 500 errors."""
    response = ResponseFormatter.format_error_response(
        code="SERVER_ERROR",
        message="Internal server error"
    )
    return jsonify(response), 500
```

## Validation Checklist

When implementing standardized formats:

- [ ] Use `ResponseFormatter` for all API responses
- [ ] Return appropriate HTTP status codes
- [ ] Validate input with JSON schemas or `MessageValidator`
- [ ] Use standardized error codes
- [ ] Log all errors with full context
- [ ] Include `details` field in error responses for debugging
- [ ] Test with both valid and invalid data
- [ ] Document error scenarios in README or API docs
- [ ] Use correct timestamp formats (Unix time for MQTT, ISO 8601 for REST)
- [ ] Validate MQTT messages as SenML format

## Testing

Test standardized responses:

```python
import json
from shared_utils import ResponseFormatter

def test_success_response():
    response = ResponseFormatter.format_success_response(
        data={"id": 1, "name": "test"},
        message="Test successful"
    )
    assert response["status"] == "success"
    assert response["data"]["id"] == 1
    assert response["message"] == "Test successful"

def test_error_response():
    response = ResponseFormatter.format_error_response(
        code="NOT_FOUND",
        message="Item not found",
        details={"id": "invalid"}
    )
    assert response["status"] == "error"
    assert response["code"] == "NOT_FOUND"
    assert response["details"]["id"] == "invalid"
```

## Migration Guide

For existing services:

1. **Add import**: `from shared_utils import ResponseFormatter, StandardizedResponse`
2. **Replace responses**: Update all `json.dumps()` calls to use formatters
3. **Add validation**: Validate incoming data using schemas
4. **Test thoroughly**: Ensure backward compatibility if needed
5. **Update documentation**: Document API changes in OpenAPI specs

## Need Help?

- Check `/docs/README.md` for documentation overview
- See `/docs/schemas/` for schema examples
- Review `/docs/api/` for API specifications
- Check `shared_utils/validation.py` for available methods
