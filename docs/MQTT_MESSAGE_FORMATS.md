# MQTT Message Formats & Topic Structure

This document defines the standardized MQTT message formats and topic naming conventions for the Smart Open Air Garden system.

## Overview

- **Protocol**: MQTT 3.1.1
- **Primary Format**: SenML (Sensor Markup Language) - RFC 8428
- **Encoding**: UTF-8 JSON

## Topic Naming Convention

All MQTT topics follow a consistent hierarchical structure:

```
garden/{garden_id}/{slot_id}/{message_type}
garden/alerts/{alert_type}
```

### Topic Hierarchy

| Topic Pattern | Purpose | Publisher | Subscriber |
|---|---|---|---|
| `garden/{garden_id}/{slot_id}/telemetry` | Device sensor readings | Device Connector | Statistics Service, Influx Adaptor, Smart Irrigation, Fault Detection |
| `garden/{garden_id}/{slot_id}/pump` | Pump control commands | Smart Irrigation Service | Device Connector, Fault Detection |
| `garden/alerts/faults` | Fault detection alerts | Fault Detection Service | Telegram Bot, Statistics Service |

## Message Formats

### 1. Telemetry Data (Device Sensors)

**Topic**: `garden/{garden_id}/{slot_id}/telemetry`  
**Publisher**: Device Connector  
**Subscribers**: Statistics Service, Influx Adaptor, Smart Irrigation Service, Fault Detection Service

**Format**: SenML JSON Array (RFC 8428)

```json
[
  {
    "bn": "RPi_001/",
    "n": "temperature",
    "v": 20.5,
    "u": "Cel",
    "t": 1234567890
  },
  {
    "n": "air_humidity",
    "v": 45.0,
    "u": "%RH",
    "t": 1234567890
  },
  {
    "n": "soil_moisture",
    "v": 65.2,
    "u": "%",
    "t": 1234567890
  }
]
```

**Field Definitions**:
- `bn` (Base Name): Optional base identifier for the device/slot. Format: `{garden_id}/{slot_id}/`
- `n` (Name): Sensor/measurement name
  - Valid values: `temperature`, `air_humidity`, `soil_moisture`, `pump_status`
- `v` (Value): Measurement value (number, integer, boolean, or string)
- `u` (Unit): Unit of measurement
  - Temperature: `Cel` (Celsius)
  - Humidity: `%RH` (Relative Humidity)
  - Moisture: `%` (Percentage)
  - Pump: `on/off`
- `t` (Time): Unix timestamp in seconds (seconds since epoch)

**Constraints**:
- Each SenML entry MUST have `n` (name), `v` (value), and `t` (time)
- `bn` is optional but recommended
- Array MUST contain at least one entry
- All timestamps should be in UTC Unix time format

**Example Message**:
```
Topic: garden/G_001/P1_R1/telemetry
Payload:
[
  {"bn": "G_001/P1_R1/", "n": "temperature", "v": 22.3, "u": "Cel", "t": 1715930532},
  {"n": "air_humidity", "v": 48.5, "u": "%RH", "t": 1715930532},
  {"n": "soil_moisture", "v": 62.8, "u": "%", "t": 1715930532}
]
```

### 2. Pump Control Commands

**Topic**: `garden/{garden_id}/{slot_id}/pump`  
**Publisher**: Smart Irrigation Service  
**Subscribers**: Device Connector, Fault Detection Service

**Format**: SenML JSON Array (RFC 8428)

```json
[
  {
    "bn": "G_001/P1_R1/",
    "n": "pump_status",
    "v": 1,
    "u": "on/off",
    "t": 1234567890
  }
]
```

**Field Definitions**:
- `n`: MUST be `pump_status`
- `v`: Control value
  - `1` or `true`: Activate pump (ON)
  - `0` or `false`: Deactivate pump (OFF)
- `u`: MUST be `on/off`
- `t`: Command timestamp in Unix time

**Constraints**:
- MUST use SenML format (array with single entry)
- `v` must be boolean-compatible (0, 1, true, false)
- Commands should include current timestamp
- Device MUST acknowledge receipt within 5 seconds

**Example Messages**:

Pump ON:
```
Topic: garden/G_001/P1_R1/pump
Payload:
[
  {
    "bn": "G_001/P1_R1/",
    "n": "pump_status",
    "v": 1,
    "u": "on/off",
    "t": 1715930540
  }
]
```

Pump OFF:
```
Topic: garden/G_001/P1_R1/pump
Payload:
[
  {
    "bn": "G_001/P1_R1/",
    "n": "pump_status",
    "v": 0,
    "u": "on/off",
    "t": 1715930560
  }
]
```

### 3. Fault Detection Alerts

**Topic**: `garden/alerts/faults`  
**Publisher**: Fault Detection Service  
**Subscribers**: Telegram Bot, Statistics Service

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

**Field Definitions**:
- `target`: Device ID where fault was detected
- `error`: Error type (currently only `PUMP_FAILURE_OR_LEAK`)
- `val_now`: Current soil moisture reading (%)
- `val_init`: Initial soil moisture when pump started (%)
- `time_iso`: ISO 8601 formatted timestamp

**Constraints**:
- All fields are REQUIRED
- `error` must be one of the defined error types
- Timestamps MUST be ISO 8601 format with timezone
- Alert indicates pump ran for >20 seconds with <0.8% moisture increase

**Example Alert**:
```
Topic: garden/alerts/faults
Payload:
{
  "target": "RPi_001",
  "error": "PUMP_FAILURE_OR_LEAK",
  "val_now": 65.2,
  "val_init": 60.0,
  "time_iso": "2024-05-18T12:42:12.221000+00:00"
}
```

## QoS Levels

- **Telemetry Messages** (garden/+/telemetry): QoS 1 (At Least Once)
  - Data loss is acceptable; occasional duplication is tolerable
- **Pump Commands** (garden/+/pump): QoS 1 (At Least Once)
  - Important control messages; must be delivered
- **Alert Messages** (garden/alerts/faults): QoS 1 (At Least Once)
  - Critical alerts; must be delivered to all subscribers

## Retained Messages

- **Telemetry**: NOT retained (current readings are time-sensitive)
- **Pump Status**: NOT retained (status is managed by device state)
- **Alerts**: NOT retained (alerts are event-driven, not state-based)

## Standard Measurement Types & Units

| Measurement | Unit Code | Unit Name | Valid Range | Resolution |
|---|---|---|---|---|
| temperature | Cel | Celsius | -40 to +60 | 0.1 |
| air_humidity | %RH | Relative Humidity | 0 to 100 | 0.1 |
| soil_moisture | % | Percentage | 0 to 100 | 0.1 |
| pump_status | on/off | On/Off | 0, 1 | N/A |

## Timestamp Format

All timestamps in MQTT messages MUST be:
- **Unix Time Format** (seconds since epoch, UTC)
- **Integer values** (no fractional seconds)
- **UTC timezone** (no local time conversions)

Example: `1715930532` represents Saturday, May 18, 2024 12:42:12 UTC

For ISO 8601 timestamps (in fault alerts):
- Format: `YYYY-MM-DDTHH:MM:SS.ssssss+HH:MM`
- Always include timezone offset
- Example: `2024-05-18T12:42:12.221000+00:00`

## Backward Compatibility

While SenML is the standard format, legacy devices may publish in simple dictionary format:

```json
{
  "soil_moisture": 65.2,
  "air_humidity": 45.0,
  "temperature": 20.5
}
```

**Note**: This format is **deprecated**. All new services should use SenML exclusively.
Services MUST support both formats for parsing but SHOULD publish only SenML.

## Error Handling

### Invalid Messages

If a message violates the format specification:
1. Log the error with full message details
2. Drop the message (do not process)
3. Count violations for monitoring

### Malformed JSON

If JSON cannot be parsed:
1. Log the parsing error
2. Drop the message
3. Alert monitoring system

### Missing Required Fields

If required fields are missing:
1. Log which fields are missing
2. Drop the message
3. Skip processing for this update

## Connection & Subscription

### Device Connection

```
Client ID: Client_{device_id}
Username: (optional, if broker requires authentication)
Password: (optional, if broker requires authentication)
Clean Session: true
Keep Alive: 60 seconds
```

### Service Connection

```
Client ID: {service-name} (e.g., "statistics-service")
Username: (optional)
Password: (optional)
Clean Session: true
Keep Alive: 60 seconds
```

### Default Subscriptions

- **Device Connector**: Subscribe to `garden/{garden_id}/+/pump`
- **Smart Irrigation Service**: Subscribe to `garden/+/+/telemetry`
- **Fault Detection Service**: Subscribe to `garden/+/+/telemetry` and `garden/+/+/pump`
- **Influx Adaptor**: Subscribe to `garden/#`
- **Statistics Service**: Subscribe to `garden/alerts/faults`
- **Telegram Bot**: Subscribe to `garden/alerts/faults` and `garden/+/pump`

## References

- RFC 8428 - Sensor Markup Language (SenML)
- MQTT 3.1.1 Specification
- ISO 8601 - Date and Time Format

