# Smart-Open-Air-Garden

## 📚 Documentation

**Complete API and data format documentation is available in the `/docs` directory:**

- **[API & Data Format Documentation](./docs/README.md)** - Quick start guide and overview
- **[Data Format Specification](./docs/DATA_FORMATS_SPECIFICATION.md)** - Complete data format reference
- **[MQTT Message Formats](./docs/MQTT_MESSAGE_FORMATS.md)** - MQTT topics, SenML format, and message structure
- **[REST API Standards](./docs/REST_API_STANDARDS.md)** - HTTP API standards and error handling
- **[OpenAPI Specifications](./docs/api/)** - Service-specific API documentation
- **[JSON Schemas](./docs/schemas/)** - Schema definitions for message validation

## 🔄 Data Flow & Architecture

### OOP Compliance Status ✅

All major Python services are implemented with proper object-oriented design:

- **DeviceConnector** - IoT device management and telemetry collection
- **StatisticsService** - Water savings calculation and pump history tracking
- **TelegramBot** - User notifications via Telegram
- **SmartIrrigation** - Intelligent irrigation control logic
- **FaultDetection** - Pump failure and leak detection
- **InfluxDBAdaptor** - Time-series data persistence
- **WeatherAdaptor** - Weather forecast integration

Each service follows:
- Class-based architecture (no global variables)
- Proper initialization with dependency injection
- Encapsulated state management
- Clear separation of concerns

### Standardized Data Formats ✅

All communication protocols follow strict standards:

**MQTT Messages**: SenML format (RFC 8428)
- Telemetry: `garden/{device_id}/telemetry`
- Commands: `garden/{device_id}/pump`
- Alerts: `garden/alerts/faults`

**REST APIs**: Standardized JSON responses
- Success envelope: `{status: "success", data: ...}`
- Error envelope: `{status: "error", code: "...", message: "..."}`
- HTTP status codes per standard convention

**Data Validation**: JSON Schema enforcement
- All message types defined in `/docs/schemas/`
- Validation utilities in `/shared_utils/validation.py`
- Input validation on all service boundaries