# Smart Open Air Garden - Data Formats Specification

Complete specification for all data formats used in the Smart Open Air Garden system.

## Document Version History

| Version | Date | Changes |
|---|---|---|
| 1.0 | 2024-05-18 | Initial comprehensive data format specification |

## 1. Introduction

This document provides a comprehensive reference for all data formats used across the Smart Open Air Garden system. It covers:

- MQTT message formats (sensor telemetry, pump commands, fault alerts)
- REST API request/response formats
- Data catalog storage format
- Error handling and validation rules
- Implementation guidelines

**Key Principles**:
- Consistency across all services
- Standards-based formats (SenML for MQTT, JSON for REST)
- Clear validation rules
- Comprehensive error handling

## 2. Data Format Categories

### 2.1 MQTT Messages (Message-to-Message Communication)

**Format**: SenML JSON (RFC 8428) or JSON objects  
**Protocol**: MQTT 3.1.1  
**QoS**: 1 (At Least Once)  
**Encoding**: UTF-8  

Detailed specifications: See [MQTT_MESSAGE_FORMATS.md](./MQTT_MESSAGE_FORMATS.md)

### 2.2 REST API Messages (Service-to-Service, Client-Server)

**Format**: JSON with standardized response envelope  
**Protocol**: HTTP/1.1  
**Content-Type**: `application/json`  

Detailed specifications: See [REST_API_STANDARDS.md](./REST_API_STANDARDS.md)

### 2.3 Catalog Storage Format

**Format**: JSON  
**Storage**: File-based JSON (catalogManager.json)  
**Schema**: Well-defined object types

Example structure:
```json
{
  "broker": {
    "broker_name": "message-broker",
    "port": 1883
  },
  "waterPricePerM3": 1.5,
  "garden_slots": [
    {
      "slotID": "slot_1",
      "slotName": "Zone A - Tomatoes",
      "plantID": "tomato",
      "deviceID": "RPi_001",
      "lastUpdate": "2024-05-18T12:00:00Z"
    }
  ],
  "devices": [
    {
      "deviceID": "RPi_001",
      "config": {
        "clientID": "Client_RPi_001"
      }
    }
  ],
  "location": {
    "location": "Turin,IT"
  }
}
```

## 3. Standard Message Types

### 3.1 Telemetry Data

**Source**: IoT devices (via Device Connector)  
**Destinations**: Multiple (Influx, Statistics, Smart Irrigation, Fault Detection)  
**Format**: SenML JSON Array  

```json
[
  {
    "bn": "RPi_001/",
    "n": "temperature",
    "v": 22.5,
    "u": "Cel",
    "t": 1715930532
  },
  {
    "n": "air_humidity",
    "v": 48.0,
    "u": "%RH",
    "t": 1715930532
  },
  {
    "n": "soil_moisture",
    "v": 65.0,
    "u": "%",
    "t": 1715930532
  }
]
```

**Validation Rules**:
- Must be valid JSON array
- Each entry must have `n`, `v`, `t` (required)
- `n` must be in allowed set: temperature, air_humidity, soil_moisture, pump_status
- `v` must be numeric or boolean
- `t` must be Unix timestamp (integer)
- `u` recommended but optional

### 3.2 Pump Commands

**Source**: Smart Irrigation Service  
**Destinations**: Device Connector, Fault Detection  
**Format**: SenML JSON Array (single entry)  

```json
[
  {
    "bn": "RPi_001/",
    "n": "pump_status",
    "v": 1,
    "u": "on/off",
    "t": 1715930540
  }
]
```

**Validation Rules**:
- Must be valid JSON array with exactly 1 entry
- `n` must be exactly "pump_status"
- `v` must be 0, 1, true, or false
- `u` should be "on/off"
- All fields required

### 3.3 Fault Alerts

**Source**: Fault Detection Service  
**Destinations**: Telegram Bot, Statistics Service  
**Format**: JSON Object  

```json
{
  "target": "RPi_001",
  "error": "PUMP_FAILURE_OR_LEAK",
  "val_now": 65.2,
  "val_init": 60.0,
  "time_iso": "2024-05-18T12:42:12.221000+00:00"
}
```

**Validation Rules**:
- Must be valid JSON object
- All fields required: target, error, val_now, val_init, time_iso
- `target` format: Device ID (e.g., RPi_XXX)
- `error` must be "PUMP_FAILURE_OR_LEAK"
- `val_now`, `val_init` must be numbers
- `time_iso` must be ISO 8601 format

### 3.4 Weather Data

**Source**: Weather Service Adaptor  
**Destinations**: Smart Irrigation Service  
**Format**: JSON Object  

Success:
```json
{
  "status": "success",
  "location": "Turin,IT",
  "max_precipitation_probability_6h": 30,
  "total_rain_accumulation_6h": 2.5
}
```

Error:
```json
{
  "status": "error",
  "message": "Error connecting to Tomorrow.io API"
}
```

**Validation Rules**:
- Must be valid JSON object
- `status` required, must be "success" or "error"
- If success: location, max_precipitation_probability_6h, total_rain_accumulation_6h required
- If error: message required
- Numeric fields must be >= 0

### 3.5 Statistics Data

**Source**: Statistics Service  
**Destinations**: Client applications  
**Format**: JSON Object  

```json
{
  "status": "success",
  "period": "7d",
  "water_saved_liters": 280,
  "money_saved_euros": 1.12,
  "average_daily_savings": 40,
  "pump_runtime_minutes": 140
}
```

**Validation Rules**:
- Must be valid JSON object
- `status` must be "success"
- `period` must be one of: "7d", "30d", "1y"
- All numeric fields must be >= 0
- All fields required

## 4. Response Envelopes

### 4.1 Success Response

All successful REST API responses:

```json
{
  "status": "success",
  "data": { /* response payload */ },
  "message": "Optional message"
}
```

### 4.2 Error Response

All error REST API responses:

```json
{
  "status": "error",
  "code": "ERROR_CODE",
  "message": "Human-readable message",
  "details": {
    /* optional context */
  }
}
```

## 5. Timestamp Formats

### 5.1 Unix Time (MQTT)

- **Format**: Integer seconds since epoch (UTC)
- **Example**: 1715930532
- **Range**: 0 to 253402300799 (until year 9999)
- **Precision**: 1 second

Used in:
- SenML messages (t field)
- Pump commands (t field)

### 5.2 ISO 8601 (REST API, Fault Alerts)

- **Format**: YYYY-MM-DDTHH:MM:SS.ssssss±HH:MM
- **Example**: 2024-05-18T12:42:12.221000+00:00
- **Timezone**: Always include offset
- **Precision**: Microseconds

Used in:
- Fault alert messages (time_iso field)
- REST API responses (lastUpdate field)
- Catalog data

## 6. Unit Conventions

### 6.1 Temperature

- **Unit Code**: Cel
- **Unit Name**: Celsius
- **Valid Range**: -40 to +60
- **Resolution**: 0.1°C
- **Example**: {"n": "temperature", "v": 22.5, "u": "Cel"}

### 6.2 Humidity

- **Unit Code**: %RH
- **Unit Name**: Relative Humidity
- **Valid Range**: 0 to 100
- **Resolution**: 0.1%
- **Example**: {"n": "air_humidity", "v": 48.5, "u": "%RH"}

### 6.3 Soil Moisture

- **Unit Code**: %
- **Unit Name**: Percentage
- **Valid Range**: 0 to 100
- **Resolution**: 0.1%
- **Example**: {"n": "soil_moisture", "v": 65.2, "u": "%"}

### 6.4 Pump Status

- **Unit Code**: on/off
- **Unit Name**: On/Off
- **Valid Values**: 0, 1, true, false
- **Example**: {"n": "pump_status", "v": 1, "u": "on/off"}

## 7. Error Codes & HTTP Status Mapping

| HTTP Status | Error Code | Description | Example |
|---|---|---|---|
| 400 | VALIDATION_ERROR | Input validation failed | Missing required field |
| 400 | INVALID_OPERATION | Cannot perform operation | Invalid period parameter |
| 404 | NOT_FOUND | Resource not found | Slot ID doesn't exist |
| 409 | CONFLICT | Resource already exists | Duplicate slot ID |
| 409 | DEVICE_IN_USE | Device associated elsewhere | Device used by another slot |
| 500 | SERVER_ERROR | Internal error | Database connection failed |

## 8. JSON Schema Files

Schema files for all message types are provided:

| Message Type | Schema File |
|---|---|
| SenML Telemetry | senml-telemetry.schema.json |
| Fault Alert | fault-alert.schema.json |
| Weather Response | weather-response.schema.json |
| Broker Config | broker-config.schema.json |
| Device Info | device-info.schema.json |
| Error Response | error-response.schema.json |
| Success Response | success-response.schema.json |

Location: `/docs/schemas/`

## 9. Implementation Guidelines

### 9.1 For Message Producers

1. **Validate before sending**: Check against schema
2. **Use correct format**: SenML for MQTT, JSON for REST
3. **Include all required fields**
4. **Use correct units**: Follow unit conventions
5. **Timestamp accuracy**: Sync system clock
6. **Error handling**: Retry with exponential backoff

### 9.2 For Message Consumers

1. **Parse safely**: Handle malformed JSON
2. **Validate on receipt**: Check against schema
3. **Log errors**: Include full message context
4. **Drop invalid messages**: Don't process partial data
5. **Graceful degradation**: Continue on missing optional fields
6. **Error recovery**: Implement retry logic

### 9.3 Services Checklist

- [ ] Validate all inputs against schema
- [ ] Use standardized response envelopes
- [ ] Return appropriate HTTP status codes
- [ ] Handle and log all errors
- [ ] Timestamp with correct format
- [ ] Document data format usage
- [ ] Test with valid and invalid data
- [ ] Monitor schema compliance

## 10. Deprecation & Migration

### 10.1 Legacy Format Support

Services currently support both SenML and simple dictionary format:

```json
{
  "soil_moisture": 65.2,
  "temperature": 22.5,
  "air_humidity": 48.0
}
```

**Status**: Deprecated  
**Support Window**: Until Q3 2024  
**Action**: Migrate all producers to SenML exclusively

### 10.2 Migration Path

1. Update device connectors to use SenML format
2. Update producers to use standardized responses
3. Implement schema validation in all services
4. Update OpenAPI documentation
5. Remove legacy format support in Q3 2024

## 11. References & Standards

- [RFC 8428 - Sensor Markup Language (SenML)](https://tools.ietf.org/html/rfc8428)
- [RFC 3339 - Date and Time on the Internet](https://tools.ietf.org/html/rfc3339)
- [MQTT Version 3.1.1](https://docs.oasis-open.org/mqtt/mqtt/v3.1.1/mqtt-v3.1.1.html)
- [JSON Schema Specification](https://json-schema.org/)
- [OpenAPI 3.0.0 Specification](https://spec.openapis.org/oas/v3.0.0)

## 12. Feedback & Updates

To suggest improvements or report issues with data formats:
1. Open an issue on GitHub
2. Include example messages or data
3. Describe the problem or improvement
4. Reference this specification

---

**Last Updated**: May 18, 2024  
**Maintainer**: Smart Open Air Garden Project Team

