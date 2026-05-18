import json
import requests
import time
import os
from MyMQTT import MyMQTT
from influxdb_client import InfluxDBClient, WritePrecision
from influxdb_client.client.write_api import SYNCHRONOUS
import cherrypy


class InfluxDBAdaptor:
    def __init__(self, clientID, catalog_url):
        self.clientID    = clientID
        self.catalog_url = catalog_url

        self.influx_url    = os.getenv("INFLUX_URL",    "http://influxdb:8086")
        self.influx_token  = os.getenv("INFLUX_TOKEN",  "u66UJ0P2mY0WxolaK1-dqhn6Kl70Q1LDuMcsL_28Jej0FnUoiH31VHzpz6O73Z2gNqfakdWYPhOoSd1aVNKdAA==")
        self.influx_org    = os.getenv("INFLUX_ORG",    "e5fa79d45d607722")
        self.influx_bucket = os.getenv("INFLUX_BUCKET", "garden_metrics")

        self.db_client  = InfluxDBClient(url=self.influx_url, token=self.influx_token, org=self.influx_org)
        self.write_api  = self.db_client.write_api(write_options=SYNCHRONOUS)

        self.broker_ip, self.broker_port = self._get_broker_config()
        self.mqtt_client = MyMQTT(clientID, self.broker_ip, self.broker_port, self)

    def _get_broker_config(self):
        print("[INIT] Contacting Catalog for broker config...")
        try:
            r    = requests.get(self.catalog_url + "/broker", timeout=10)
            r.raise_for_status()
            cfg  = r.json()
            pair = (cfg["broker_name"], cfg["broker_port"])
            print(f"[INIT] Broker: {pair}")
            return pair
        except Exception as e:
            print(f"[ERROR] {e}")
            return ("message-broker", 1883)

    def start(self):
        self.mqtt_client.start()
        self.mqtt_client.mySubscribe("garden/#")

    def stop(self):
        self.mqtt_client.unsubscribe()
        self.mqtt_client.stop()
        self.db_client.close()

    def notify(self, topic, payload):
        msg_str = payload.decode('utf-8') if isinstance(payload, bytes) else payload
        print(f"[MQTT] {topic}: {msg_str[:80]}")
        try:
            senml = json.loads(msg_str)
            if isinstance(senml, dict):
                senml = [senml]
            if not isinstance(senml, list) or len(senml) == 0:
                return

            # Parse topic to extract garden_id and slot_id
            # Expected: garden/{gardenID}/{slotID}/telemetry|pump
            parts     = topic.split('/')
            garden_id = parts[1] if len(parts) > 1 else "unknown"
            slot_id   = parts[2] if len(parts) > 2 else "unknown"

            # Determine measurement type
            if "pump" in topic:
                measurement = "actuator_activity"
            elif "telemetry" in topic:
                measurement = "environmental_data"
            else:
                return

            for entry in senml:
                if "v" not in entry:
                    continue
                record = {
                    "measurement": measurement,
                    "tags": {
                        "garden_id":      garden_id,
                        "slot_id":        slot_id,
                        "garden_slot_id": f"{garden_id}/{slot_id}",
                        "sensor_type":    entry["n"]
                    },
                    "fields": {"value": float(entry["v"])},
                    "time":   int(entry.get("t", time.time()))
                }
                self.write_api.write(
                    bucket=self.influx_bucket,
                    record=record,
                    write_precision=WritePrecision.S
                )
            print(f"[INFLUX] Saved from {garden_id}/{slot_id}")

        except Exception as e:
            print(f"[WARNING] {topic}: {e}")


class InfluxRESTService:
    exposed = True

    def __init__(self, db_client, influx_org, influx_bucket):
        self.db_client     = db_client
        self.influx_org    = influx_org
        self.influx_bucket = influx_bucket

    def GET(self, *uri, **params):
        sensor_type = params.get("sensor_type", "temperature")
        period      = params.get("period", "7d")
        garden_id   = params.get("garden_id", None)
        slot_id     = params.get("slot_id",   None)

        # Build Flux filter
        extra = ""
        if garden_id:
            extra += f'\n  |> filter(fn: (r) => r.garden_id == "{garden_id}")'
        if slot_id:
            extra += f'\n  |> filter(fn: (r) => r.slot_id == "{slot_id}")'

        if sensor_type == "pump_status":
            query = f"""
from(bucket: "{self.influx_bucket}")
  |> range(start: -{period})
  |> filter(fn: (r) => r._measurement == "actuator_activity")
  |> filter(fn: (r) => r.sensor_type == "{sensor_type}")
  |> filter(fn: (r) => r._field == "value"){extra}
"""
        else:
            query = f"""
from(bucket: "{self.influx_bucket}")
  |> range(start: -{period})
  |> filter(fn: (r) => r._measurement == "environmental_data")
  |> filter(fn: (r) => r.sensor_type == "{sensor_type}")
  |> filter(fn: (r) => r._field == "value"){extra}
"""
        try:
            tables = self.db_client.query_api().query(org=self.influx_org, query=query)
            output = []
            for table in tables:
                for row in table.records:
                    output.append({
                        "time":           row.get_time().isoformat(),
                        "value":          row.get_value(),
                        "garden_id":      row.values.get("garden_id"),
                        "slot_id":        row.values.get("slot_id"),
                        "garden_slot_id": row.values.get("garden_slot_id"),
                        "sensor":         row.values.get("sensor_type")
                    })
            cherrypy.response.headers['Content-Type'] = 'application/json'
            return json.dumps(output).encode('utf-8')
        except Exception as e:
            cherrypy.response.status = 500
            return json.dumps({"status": "error", "msg": str(e)}).encode('utf-8')


class CatalogRoot:
    pass


if __name__ == "__main__":
    CATALOG_URL = "http://service-catalog:8080"
    adaptor = InfluxDBAdaptor("InfluxAdaptor_001", CATALOG_URL)

    root = CatalogRoot()
    root.history = InfluxRESTService(
        adaptor.db_client,
        adaptor.influx_org,
        adaptor.influx_bucket
    )

    conf = {
        '/': {
            'request.dispatch': cherrypy.dispatch.MethodDispatcher(),
            'tools.sessions.on': True
        }
    }
    cherrypy.tree.mount(root, '/', conf)
    cherrypy.config.update({'server.socket_host': '0.0.0.0', 'server.socket_port': 8081})

    adaptor.start()
    print("[RUN] InfluxDB Adaptor running...")
    cherrypy.engine.start()
    cherrypy.engine.block()