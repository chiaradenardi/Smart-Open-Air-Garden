# Smart Open Air Garden - API & Data Format Documentation

Complete reference documentation for all APIs, data formats, and message specifications used in the Smart Open Air Garden system.

## 📚 Documentation Structure

### Core Documentation Files

1. **[DATA_FORMATS_SPECIFICATION.md](./DATA_FORMATS_SPECIFICATION.md)**
   - Overview of all data formats used in the system
   - Message types and structures
   - Response envelopes and error handling
   - Timestamp formats and unit conventions
   - Implementation guidelines

2. **[MQTT_MESSAGE_FORMATS.md](./MQTT_MESSAGE_FORMATS.md)**
   - Complete MQTT topic structure and naming conventions
   - SenML message format specification (RFC 8428)
   - Detailed field definitions and constraints
   - Example messages for all message types
   - QoS and retained message policies
   - Standard measurement types and units

3. **[REST_API_STANDARDS.md](./REST_API_STANDARDS.md)**
   - Standardized REST API response formats
   - HTTP status codes and error responses
   - Service-specific API documentation
   - Request/response examples
   - Header requirements and validation rules
   - Data validation and error logging guidelines

### OpenAPI/Swagger Specifications

Located in `./api/` directory:

1. **[service-catalog-openapi.yaml](./api/service-catalog-openapi.yaml)**
   - Service Catalog API specification
   - Broker configuration endpoints
   - Garden slot management endpoints
   - Device information endpoints
   - Water price endpoints

2. **[weather-service-openapi.yaml](./api/weather-service-openapi.yaml)**
   - Weather Service Adaptor API specification
   - Weather forecast endpoint
   - Error handling

3. **[statistics-service-openapi.yaml](./api/statistics-service-openapi.yaml)**
   - Statistics Service API specification
   - Water savings statistics endpoints
   - Pump history endpoints

### JSON Schema Definitions

Located in `./schemas/` directory:

| Schema | Purpose |
|--------|---------|
| senml-telemetry.schema.json | Sensor telemetry messages (SenML format) |
| fault-alert.schema.json | Fault detection alert messages |
| weather-response.schema.json | Weather service responses |
| broker-config.schema.json | MQTT broker configuration |
| device-info.schema.json | Device information objects |
| error-response.schema.json | Standardized error responses |
| success-response.schema.json | Standardized success responses |

## 🎯 Quick Start

### For API Developers

1. Start with [REST_API_STANDARDS.md](./REST_API_STANDARDS.md)
2. Check [service-catalog-openapi.yaml](./api/service-catalog-openapi.yaml) for your service
3. Review JSON schema for request/response validation
4. Implement standardized error responses

### For MQTT Integration

1. Read [MQTT_MESSAGE_FORMATS.md](./MQTT_MESSAGE_FORMATS.md)
2. Check topic naming conventions and subscribe patterns
3. Review SenML format specification
4. Use provided schema for message validation

### For Integration with External Services

1. Consult [DATA_FORMATS_SPECIFICATION.md](./DATA_FORMATS_SPECIFICATION.md) for overview
2. Find your service API in OpenAPI files
3. Use schema files for validation
4. Follow REST API standards for responses

## 📋 Message Format Summary

### MQTT Messages

- **Format**: SenML JSON (RFC 8428) for telemetry and pump commands
- **Format**: JSON object for fault alerts
- **Protocol**: MQTT 3.1.1
- **QoS**: 1 (At Least Once)

#### Topic Patterns

```
garden/{device_id}/telemetry       # Device sensor data (SenML format)
garden/{device_id}/pump            # Pump commands (SenML format)
garden/alerts/faults               # Fault detection alerts (JSON object)
```

### REST API Messages

- **Format**: JSON with standardized response envelope
- **Protocol**: HTTP/1.1
- **Content-Type**: application/json
- **Base URLs**:
  - Service Catalog: `http://service-catalog:8080`
  - Weather Adaptor: `http://weather-service-adaptor:8085`
  - Statistics Service: `http://statistics-service:8090`

#### Success Response

```json
{
  "status": "success",
  "data": { /* payload */ },
  "message": "Optional message"
}
```

#### Error Response

```json
{
  "status": "error",
  "code": "ERROR_CODE",
  "message": "Human-readable message",
  "details": { /* optional context */ }
}
```

## 🔍 Key Standards

### Timestamp Formats

- **MQTT (SenML)**: Unix timestamp (seconds since epoch)
  - Example: `1715930532`
  
- **REST API & Fault Alerts**: ISO 8601 format
  - Example: `2024-05-18T12:42:12.221000+00:00`

### Unit Conventions

| Measurement | Code | Unit | Range |
|---|---|---|---|
| Temperature | Cel | Celsius | -40 to +60°C |
| Air Humidity | %RH | Relative Humidity | 0-100% |
| Soil Moisture | % | Percentage | 0-100% |
| Pump Status | on/off | On/Off | 0, 1, true, false |

### Error Codes

| Code | HTTP Status | Usage |
|---|---|---|
| VALIDATION_ERROR | 400 | Input validation failed |
| NOT_FOUND | 404 | Resource not found |
| CONFLICT | 409 | Resource conflict/duplicate |
| DEVICE_IN_USE | 409 | Device already associated |
| SERVER_ERROR | 500 | Internal server error |

## 🛠️ Implementation Checklist

### For API Endpoints

- [ ] Use standardized success response envelope
- [ ] Use standardized error response envelope
- [ ] Return appropriate HTTP status codes
- [ ] Validate input against JSON schemas
- [ ] Log errors with full context
- [ ] Document in OpenAPI specification
- [ ] Test with valid and invalid data

### For MQTT Integration

- [ ] Subscribe to correct topics
- [ ] Parse SenML format correctly
- [ ] Handle both array and object formats (during transition)
- [ ] Validate messages against schemas
- [ ] Use correct timestamp formats
- [ ] Publish with correct QoS level
- [ ] Handle connection and reconnection

### For Data Validation

- [ ] Load appropriate JSON schema
- [ ] Validate before processing
- [ ] Log validation errors
- [ ] Return clear error messages
- [ ] Handle malformed JSON gracefully
- [ ] Skip invalid messages

## 📖 Service-Specific Documentation

### Service Catalog API

- **Endpoints**: `/broker`, `/price`, `/slots`, `/devices`, `/location`
- **Primary Uses**: Device configuration, broker info, slot management
- **OpenAPI Spec**: [service-catalog-openapi.yaml](./api/service-catalog-openapi.yaml)
- **Detailed Guide**: See [REST_API_STANDARDS.md](./REST_API_STANDARDS.md#service-catalog-api)

### Weather Service API

- **Endpoints**: GET `/` (weather forecast)
- **Primary Uses**: 6-hour precipitation forecast for irrigation decisions
- **OpenAPI Spec**: [weather-service-openapi.yaml](./api/weather-service-openapi.yaml)
- **Response Format**: Location, max precipitation probability, rain accumulation

### Statistics Service API

- **Endpoints**: `/statistics/{period}`, `/pump-history/{period}`
- **Primary Uses**: Water savings calculation, pump history tracking
- **OpenAPI Spec**: [statistics-service-openapi.yaml](./api/statistics-service-openapi.yaml)
- **Periods**: 7 days, 30 days, 1 year

### MQTT Topics

- **Telemetry**: `garden/+/telemetry` (SenML sensor readings)
- **Pump Control**: `garden/+/pump` (SenML pump commands)
- **Alerts**: `garden/alerts/faults` (JSON fault alerts)
- **Subscriptions**: See [MQTT_MESSAGE_FORMATS.md](./MQTT_MESSAGE_FORMATS.md#connection--subscription)

## 🔄 Data Format Examples

### Telemetry Message (MQTT)

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
    "v": 65.2,
    "u": "%",
    "t": 1715930532
  }
]
```

### Pump Command (MQTT)

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

### Fault Alert (MQTT)

```json
{
  "target": "RPi_001",
  "error": "PUMP_FAILURE_OR_LEAK",
  "val_now": 65.2,
  "val_init": 60.0,
  "time_iso": "2024-05-18T12:42:12.221000+00:00"
}
```

### API Response Example

```json
{
  "status": "success",
  "data": {
    "slotID": "slot_1",
    "plantID": "tomato",
    "deviceID": "RPi_001",
    "slotName": "Zone A"
  },
  "message": "Garden slot retrieved successfully"
}
```

### Error Response Example

```json
{
  "status": "error",
  "code": "DEVICE_IN_USE",
  "message": "Device 'RPi_001' is already in use by slot 'slot_1'",
  "details": {
    "deviceID": "RPi_001",
    "used_by_slot": "slot_1"
  }
}
```

## 🔗 References

- [RFC 8428 - Sensor Markup Language (SenML)](https://tools.ietf.org/html/rfc8428)
- [MQTT 3.1.1 Specification](https://docs.oasis-open.org/mqtt/mqtt/v3.1.1/mqtt-v3.1.1.html)
- [JSON Schema](https://json-schema.org/)
- [OpenAPI 3.0.0](https://spec.openapis.org/oas/v3.0.0)
- [ISO 8601 Date/Time Format](https://www.iso.org/iso-8601-date-and-time-format.html)

## 📞 Support & Feedback

For questions or suggestions about data formats:
1. Check relevant documentation file
2. Review examples and schemas
3. Open GitHub issue with specific details
4. Reference this documentation

---

**Documentation Version**: 1.0  
**Last Updated**: May 18, 2024  
**Maintained By**: Smart Open Air Garden Project Team

