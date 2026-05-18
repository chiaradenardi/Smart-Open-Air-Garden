import requests
import time
import random
import json
import os
import paho.mqtt.client as mqtt


class DeviceConnector:
    """This class represents the Raspberry Pi in a garden. 
    It simulates sensor data and listens for pump commands."""

    def __init__(self):
        """Creates the device object and sets default values for sensors and pump."""
        self.catalog_url = os.getenv("CATALOG_URL", "http://service-catalog:8080")
        self.garden_id   = os.getenv("GARDEN_ID",   "G_001")
        self.device_id   = os.getenv("DEVICE_ID",   "RPi_001")

        # slot_id → pump state ("ON"/"OFF")
        self.pump_states = {}
        # slot_id → current soil moisture value
        self.slot_moisture = {}
        # slot metadata list fetched from catalog
        self.slots = []

        self.broker_ip   = None
        self.broker_port = 1883
        self.client_id   = f"Client_{self.device_id}"
        self.client      = None

    # ── Catalog interactions ──────────────────────────────────────────────────

    def get_broker_config(self):
        """Asks the catalog where the MQTT broker is located."""
        print("[INIT] Requesting broker config from Catalog")
        try:
            r = requests.get(f"{self.catalog_url}/broker", timeout=10)
            r.raise_for_status()
            cfg = r.json()
            print(f"[INIT] Broker config received: {cfg}")
            return cfg
        except requests.exceptions.RequestException as e:
            print(f"[ERROR] Failed to reach Catalog: {e}")
            return None

    def get_garden_slots(self):
        """Downloads the list of active slots for this specific garden from the catalog."""
        try:
            r = requests.get(
                f"{self.catalog_url}/gardens/{self.garden_id}/slots",
                timeout=10
            )
            r.raise_for_status()
            slots = r.json()
            print(f"[INIT] Garden {self.garden_id}: {len(slots)} slot(s) found")
            return slots
        except Exception as e:
            print(f"[ERROR] Cannot fetch slots for garden {self.garden_id}: {e}")
            return []

    # ── Sensor simulation ─────────────────────────────────────────────────────

    def simulate_sensors(self, slot_id):
        """Creates fake temperature and humidity data. If the pump is ON, moisture goes up."""
        temp         = round(random.uniform(20.0, 24.0), 1)
        air_humidity = round(random.uniform(40.0, 50.0), 1)

        current = self.slot_moisture.get(slot_id, 60.0)
        if self.pump_states.get(slot_id) == "ON":
            new_moisture = min(100.0, current + 2.0)
        else:
            new_moisture = max(30.0, current - 0.5)

        self.slot_moisture[slot_id] = new_moisture
        return temp, air_humidity, new_moisture

    # ── MQTT setup ────────────────────────────────────────────────────────────

    def _on_connect(self, client, userdata, flags, rc):
        """When connected to MQTT, it subscribes to the pump topics for all slots."""
        if rc == 0:
            print("[MQTT] Connection established with broker")
            for slot in self.slots:
                topic = f"garden/{self.garden_id}/{slot['slotID']}/pump"
                client.subscribe(topic)
                print(f"[MQTT] Subscribed to: {topic}")
        else:
            print(f"[MQTT] Connection failed with error code: {rc}")

    def _on_message(self, client, userdata, msg):
        """Reads incoming MQTT messages and turns the simulated pump ON or OFF."""
        payload_str = msg.payload.decode('utf-8')
        parts = msg.topic.split('/')   # garden / G_001 / P1_R1 / pump
        if len(parts) < 4:
            return
        slot_id = parts[2]

        print(f"\n[MQTT Received] Topic: {msg.topic} | Payload: {payload_str}")
        try:
            data = json.loads(payload_str)
            if isinstance(data, list):
                for entry in data:
                    if entry.get("n") == "pump_status":
                        if entry.get("v") == 1:
                            self.pump_states[slot_id] = "ON"
                            print(f">>> [{slot_id}] Pump activated")
                        elif entry.get("v") == 0:
                            self.pump_states[slot_id] = "OFF"
                            print(f">>> [{slot_id}] Pump deactivated")
                        break
        except Exception as e:
            print(f"[ERROR] Failed to parse payload: {e}")

    def setup_mqtt(self):
        """Prepares the MQTT client with ID and callbacks."""
        self.client = mqtt.Client(client_id=self.client_id)
        self.client.on_connect = self._on_connect
        self.client.on_message = self._on_message

    def connect_mqtt(self):
        """Tries to connect to the broker, and keeps retrying if it fails."""
        print(f"[SETUP] Connecting to broker at {self.broker_ip} as {self.client_id}")
        while True:
            try:
                self.client.connect(self.broker_ip, self.broker_port, 60)
                break
            except Exception as e:
                print(f"[ERROR] MQTT connection failed, retrying... ({e})")
                time.sleep(5)

    # ── Telemetry publishing ──────────────────────────────────────────────────

    def publish_telemetry(self):
        """Sends the generated sensor data to MQTT using SenML format."""
        ts = int(time.time())
        for slot in self.slots:
            s_id = slot["slotID"]
            temp, air_hum, moisture = self.simulate_sensors(s_id)

            payload = [
                {"bn": f"{self.garden_id}/{s_id}/", "n": "temperature",  "v": temp,     "u": "Cel",  "t": ts},
                {"n": "air_humidity",                                      "v": air_hum,  "u": "%RH",  "t": ts},
                {"n": "soil_moisture",                                     "v": round(moisture, 1), "u": "%RH", "t": ts}
            ]
            topic = f"garden/{self.garden_id}/{s_id}/telemetry"
            self.client.publish(topic, json.dumps(payload))
            print(f"[{self.garden_id}/{s_id}] Temp:{temp}°C | Moisture:{round(moisture,1)}% | Pump:{self.pump_states.get(s_id,'OFF')}")

    # ── Lifecycle ─────────────────────────────────────────────────────────────

    def start(self):
        """Main function: gets config, connects to MQTT, and loops to send data every 5 seconds."""
        # 1. Wait for broker config
        broker_cfg = None
        while not broker_cfg:
            broker_cfg = self.get_broker_config()
            if not broker_cfg:
                time.sleep(5)
        self.broker_ip = broker_cfg.get("broker_name", "message-broker")

        # 2. Wait for garden slots
        while not self.slots:
            self.slots = self.get_garden_slots()
            if not self.slots:
                time.sleep(5)

        # Init per-slot state
        for s in self.slots:
            self.pump_states[s["slotID"]]   = "OFF"
            self.slot_moisture[s["slotID"]] = 60.0

        # 3. Setup and connect MQTT
        self.setup_mqtt()
        self.connect_mqtt()
        self.client.loop_start()
        print(f"\n[INIT] Telemetry loop started for garden {self.garden_id} "
              f"with {len(self.slots)} slot(s). Press Ctrl+C to stop.")

        # 4. Telemetry loop
        try:
            while True:
                self.publish_telemetry()
                time.sleep(5)
        except KeyboardInterrupt:
            print("\n[STOP] Connector terminated by user. Disconnecting.")
            self.stop()

    def stop(self):
        """Safely stops the MQTT loop and disconnects."""
        if self.client:
            self.client.loop_stop()
            self.client.disconnect()


if __name__ == "__main__":
    connector = DeviceConnector()
    connector.start()
