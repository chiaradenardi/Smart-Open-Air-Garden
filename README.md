# Smart Open Air Garden

## Documentation

Full API and data format docs are in the `/docs` folder:

- [API & Data Format Overview](./docs/README.md)
- [Data Format Specification](./docs/DATA_FORMATS_SPECIFICATION.md)
- [MQTT Message Formats](./docs/MQTT_MESSAGE_FORMATS.md)
- [REST API Standards](./docs/REST_API_STANDARDS.md)
- [OpenAPI Specs](./docs/api/) — per-service API docs
- [JSON Schemas](./docs/schemas/) — schema definitions for validation

## Architecture

The project is built as a set of microservices, each running in its own Docker container. They communicate through MQTT (for sensor data and commands) and REST APIs (for configuration and queries).

### Services

- **DeviceConnector** — Represents a Raspberry Pi in a garden. Reads sensors and controls the pump.
- **SmartIrrigation** — Decides when to turn the pump on/off based on soil moisture and weather.
- **FaultDetection** — Watches for broken pumps (pump is ON but moisture doesn't go up).
- **InfluxDBAdaptor** — Saves all sensor data into InfluxDB for historical queries.
- **StatisticsService** — Calculates water and money savings compared to a fixed timer.
- **WeatherAdaptor** — Gets rain forecasts from Tomorrow.io API.
- **TelegramBot** — Lets users manage gardens, slots, and devices from Telegram.
- **ServiceCatalog** — Central registry that stores all gardens, devices, users, and settings.

### MQTT Topics

All sensor data uses SenML format (RFC 8428).

| Topic | Direction | Description |
|---|---|---|
| `garden/{gardenID}/{slotID}/telemetry` | Device -> Cloud | Sensor readings (temp, humidity, moisture) |
| `garden/{gardenID}/{slotID}/pump` | Cloud -> Device | Pump ON/OFF commands |
| `garden/alerts/faults` | FaultDetection -> Bot | Pump failure alerts |
| `garden/statistics/water-saved` | Statistics -> Bot | Water savings updates |

### REST APIs

Each service exposes its own REST API via CherryPy with `MethodDispatcher`.
Responses follow this format:

```json
{"status": "success", "data": { ... }}
{"status": "error", "code": "NOT_FOUND", "message": "..."}
```

## How to Run

```bash
docker-compose up --build -d
```

This starts all services. The Telegram Bot needs a valid token in `Telegram_Bot/.env`.

## Project Structure

```
Smart-Open-Air-Garden/
├── service_catalog/          # Central config and registry
├── device_connector/         # Raspberry Pi simulator
├── SmartIrrigationService/   # Irrigation logic
├── fault-detection-service/  # Pump fault detection
├── influx_adaptor/           # MQTT -> InfluxDB bridge
├── statistics-service/       # Water savings calculator
├── weather_service_adaptor/  # Tomorrow.io weather API
├── Telegram_Bot/             # User interface via Telegram
├── simulators/               # Test scripts
├── shared_utils/             # Shared validation helpers
├── node_red_data/            # Node-RED dashboard flows
└── docker-compose.yml
```