# REST API Standardization Guide

This document defines the standardized request and response formats for all REST API services in the Smart Open Air Garden system.

## HTTP Status Codes

All endpoints MUST use appropriate HTTP status codes:

| Code | Meaning | Use Case |
|---|---|---|
| 200 | OK | Successful GET, PUT, DELETE |
| 201 | Created | Successful POST |
| 400 | Bad Request | Validation error, missing fields |
| 404 | Not Found | Resource doesn't exist |
| 409 | Conflict | Duplicate ID, device already in use |
| 500 | Internal Server Error | Server-side error, exception occurred |

## Standard Response Format

### Success Response

All successful responses MUST follow this format:

```json
{
  "status": "success",
  "data": { /* response payload */ },
  "message": "Optional human-readable message"
}
```

**Examples**:

GET with object response:
```json
{
  "status": "success",
  "data": {
    "slotID": "slot_1",
    "plantID": "tomato",
    "deviceID": "RPi_001",
    "slotName": "Zone A"
  }
}
```

GET with array response:
```json
{
  "status": "success",
  "data": [
    {
      "slotID": "slot_1",
      "plantID": "tomato",
      "deviceID": "RPi_001"
    },
    {
      "slotID": "slot_2",
      "plantID": "lettuce",
      "deviceID": "RPi_002"
    }
  ],
  "message": "Retrieved 2 garden slots"
}
```

POST/PUT response:
```json
{
  "status": "success",
  "data": {
    "newPrice": 1.5
  },
  "message": "Water price successfully updated"
}
```

### Error Response

All error responses MUST follow this standardized format:

```json
{
  "status": "error",
  "code": "ERROR_CODE",
  "message": "Human-readable error message",
  "details": {
    /* Optional error-specific context */
  }
}
```

**Error Codes**:

| Code | HTTP Status | Description |
|---|---|---|
| VALIDATION_ERROR | 400 | Missing or invalid input parameters |
| NOT_FOUND | 404 | Requested resource doesn't exist |
| CONFLICT | 409 | Resource already exists or constraint violated |
| DUPLICATE_ID | 409 | Duplicate ID already in the system |
| DEVICE_IN_USE | 409 | Device is already associated with another slot |
| INVALID_OPERATION | 400 | Operation cannot be performed in current state |
| SERVER_ERROR | 500 | Internal server error |

**Examples**:

Validation Error:
```json
{
  "status": "error",
  "code": "VALIDATION_ERROR",
  "message": "Missing required field",
  "details": {
    "field": "NewWaterPricePerM3",
    "reason": "Field is required in request body"
  }
}
```

Not Found:
```json
{
  "status": "error",
  "code": "NOT_FOUND",
  "message": "Slot with ID 'invalid_slot' not found in catalog",
  "details": {
    "slotID": "invalid_slot"
  }
}
```

Conflict - Device in Use:
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

Server Error:
```json
{
  "status": "error",
  "code": "SERVER_ERROR",
  "message": "Internal server error",
  "details": {
    "error_id": "err_12345",
    "timestamp": "2024-05-18T12:42:12Z"
  }
}
```

## Service-Specific APIs

### Service Catalog API

**Base URL**: `http://service-catalog:8080`

#### GET /broker
Retrieve MQTT broker configuration.

**Response** (200):
```json
{
  "status": "success",
  "data": {
    "broker_name": "message-broker",
    "broker_port": 1883
  }
}
```

#### GET /price
Retrieve current water price.

**Response** (200):
```json
{
  "status": "success",
  "data": {
    "price": 1.5
  },
  "message": "Water price in €/m³"
}
```

#### PUT /price
Update water price.

**Request**:
```json
{
  "NewWaterPricePerM3": 2.0
}
```

**Response** (200):
```json
{
  "status": "success",
  "data": {
    "newPrice": 2.0
  },
  "message": "Water price successfully updated"
}
```

#### GET /slots
Retrieve all garden slots.

**Response** (200):
```json
{
  "status": "success",
  "data": [
    {
      "slotID": "slot_1",
      "slotName": "Zone A",
      "plantID": "tomato",
      "deviceID": "RPi_001",
      "lastUpdate": "2024-05-18T12:00:00.000Z"
    }
  ],
  "message": "Retrieved 1 garden slot"
}
```

#### POST /slots
Create new garden slot.

**Request**:
```json
{
  "slotID": "slot_1",
  "plantID": "tomato",
  "deviceID": "RPi_001"
}
```

**Response** (201):
```json
{
  "status": "success",
  "data": {
    "slotID": "slot_1",
    "plantID": "tomato",
    "deviceID": "RPi_001"
  },
  "message": "Slot successfully created"
}
```

**Error Response** (409 - Device in Use):
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

#### GET /slots/{slotID}
Retrieve specific garden slot.

**Response** (200):
```json
{
  "status": "success",
  "data": {
    "slotID": "slot_1",
    "slotName": "Zone A",
    "plantID": "tomato",
    "deviceID": "RPi_001"
  }
}
```

#### PUT /slots/{slotID}
Update garden slot.

**Request**:
```json
{
  "slotID": "slot_1",
  "plantID": "lettuce"
}
```

**Response** (200):
```json
{
  "status": "success",
  "data": {
    "slotID": "slot_1",
    "plantID": "lettuce",
    "deviceID": "RPi_001"
  },
  "message": "Slot updated successfully"
}
```

#### DELETE /slots/{slotID}
Delete garden slot.

**Response** (200):
```json
{
  "status": "success",
  "data": null,
  "message": "Slot successfully removed"
}
```

#### GET /devices/{deviceID}
Retrieve device information.

**Response** (200):
```json
{
  "status": "success",
  "data": {
    "deviceID": "RPi_001",
    "config": {
      "clientID": "Client_RPi_001"
    },
    "lastUpdate": "2024-05-18T12:00:00.000Z"
  }
}
```

#### GET /location
Retrieve location configuration.

**Response** (200):
```json
{
  "status": "success",
  "data": {
    "location": "Turin,IT"
  }
}
```

### Weather Service API

**Base URL**: `http://weather-service-adaptor:8085`

#### GET /
Retrieve weather forecast.

**Response** (200):
```json
{
  "status": "success",
  "data": {
    "location": "Turin,IT",
    "max_precipitation_probability_6h": 30,
    "total_rain_accumulation_6h": 2.5
  }
}
```

**Error Response** (500):
```json
{
  "status": "error",
  "code": "SERVER_ERROR",
  "message": "Error connecting to Tomorrow.io API"
}
```

### Statistics Service API

**Base URL**: `http://statistics-service:8090`

#### GET /statistics/{period}
Retrieve water savings statistics.

**Parameters**:
- `period`: One of `7d`, `30d`, `1y`

**Response** (200):
```json
{
  "status": "success",
  "data": {
    "period": "7d",
    "water_saved_liters": 280,
    "money_saved_euros": 1.12,
    "average_daily_savings": 40,
    "pump_runtime_minutes": 140
  }
}
```

#### GET /pump-history/{period}
Retrieve pump operation history.

**Response** (200):
```json
{
  "status": "success",
  "data": [
    {
      "timestamp": "2024-05-18T10:30:00Z",
      "device_id": "RPi_001",
      "action": "ON",
      "duration_minutes": 15,
      "water_used_liters": 30
    },
    {
      "timestamp": "2024-05-18T10:45:00Z",
      "device_id": "RPi_001",
      "action": "OFF",
      "duration_minutes": 0,
      "water_used_liters": 0
    }
  ],
  "message": "Retrieved 2 pump history entries"
}
```

## Header Requirements

### Request Headers

All requests SHOULD include:
```
Content-Type: application/json
Accept: application/json
```

### Response Headers

All responses MUST include:
```
Content-Type: application/json
```

Services MAY include:
```
X-Request-ID: unique-identifier
X-Response-Time: milliseconds
```

## Data Validation

All services MUST validate:

1. **Required Fields**: Check all mandatory fields are present
2. **Data Types**: Validate field types match schema
3. **Field Values**: Validate values match acceptable ranges
4. **String Formats**: Validate ID formats, email addresses, etc.
5. **Numeric Ranges**: Check min/max values

## Pagination

For endpoints returning arrays, services SHOULD support pagination using query parameters:

```
GET /slots?page=1&limit=20
```

Response format:
```json
{
  "status": "success",
  "data": [ /* items */ ],
  "pagination": {
    "total": 150,
    "page": 1,
    "limit": 20,
    "pages": 8
  }
}
```

## Rate Limiting

Services MAY implement rate limiting. If rate-limited:

**Response** (429):
```json
{
  "status": "error",
  "code": "RATE_LIMIT_EXCEEDED",
  "message": "Too many requests",
  "details": {
    "retry_after": 60
  }
}
```

## Error Logging

All errors MUST be logged with:
- Timestamp (ISO 8601)
- Request ID (if available)
- Endpoint path
- HTTP method
- Status code
- Error code and message
- Stack trace (for server errors only)

## Schema Validation

All services MUST validate incoming requests against JSON Schema.
Schema files are provided in `/docs/schemas/` directory.

## Implementation Checklist

- [ ] Use standardized error response format
- [ ] Return appropriate HTTP status codes
- [ ] Validate all input parameters
- [ ] Log all errors with sufficient context
- [ ] Include proper Content-Type headers
- [ ] Handle exceptions gracefully
- [ ] Return meaningful error messages to clients
- [ ] Test error scenarios thoroughly

