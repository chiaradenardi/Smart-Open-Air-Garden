import requests
import time
import random
import json
import os
import paho.mqtt.client as mqtt
import threading


class DeviceConnector(threading.Thread):
    """This class represents the Raspberry Pi in a garden. 
    It simulates sensor data and listens for pump commands."""

    def __init__(self, catalog_url, garden_id, device_id):
        """Creates the device object and sets default values for sensors and pump."""
        super().__init__()
        self.catalog_url = catalog_url
        self.garden_id   = garden_id
        self.device_id   = device_id

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
        self.stop_event  = threading.Event()

    # ── Catalog interactions ──────────────────────────────────────────────────

    def get_broker_config(self):
        """Asks the catalog where the MQTT broker is located."""
        try:
            r = requests.get(f"{self.catalog_url}/broker", timeout=5)
            r.raise_for_status()
            return r.json()
        except Exception:
            return None

    def get_garden_slots(self):
        """Downloads the list of active slots for this specific garden from the catalog."""
        try:
            r = requests.get(
                f"{self.catalog_url}/gardens/{self.garden_id}/slots",
                timeout=5
            )
            r.raise_for_status()
            return r.json()
        except Exception:
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
            print(f"[MQTT - {self.device_id}] Connection established with broker")
            for slot in self.slots:
                topic = f"garden/{self.garden_id}/{slot['slotID']}/pump"
                client.subscribe(topic)
                print(f"[MQTT - {self.device_id}] Subscribed to: {topic}")
        else:
            print(f"[MQTT - {self.device_id}] Connection failed with error code: {rc}")

    def _on_message(self, client, userdata, msg):
        """Reads incoming MQTT messages and turns the simulated pump ON or OFF."""
        payload_str = msg.payload.decode('utf-8')
        parts = msg.topic.split('/')   # garden / G_001 / P1_R1 / pump
        if len(parts) < 4:
            return
        slot_id = parts[2]

        print(f"\n[MQTT Received - {self.device_id}] Topic: {msg.topic} | Payload: {payload_str}")
        try:
            data = json.loads(payload_str)
            if isinstance(data, list):
                for entry in data:
                    if entry.get("n") == "pump_status":
                        if entry.get("v") == 1:
                            self.pump_states[slot_id] = "ON"
                            print(f">>> [{self.garden_id}/{slot_id}] Pump activated")
                        elif entry.get("v") == 0:
                            self.pump_states[slot_id] = "OFF"
                            print(f">>> [{self.garden_id}/{slot_id}] Pump deactivated")
                        break
        except Exception as e:
            print(f"[ERROR - {self.device_id}] Failed to parse payload: {e}")

    def setup_mqtt(self):
        """Prepares the MQTT client with ID and callbacks."""
        self.client = mqtt.Client(client_id=self.client_id)
        self.client.on_connect = self._on_connect
        self.client.on_message = self._on_message

    def connect_mqtt(self):
        """Tries to connect to the broker, and keeps retrying if it fails."""
        while not self.stop_event.is_set():
            try:
                self.client.connect(self.broker_ip, self.broker_port, 60)
                break
            except Exception:
                time.sleep(5)

    # ── Telemetry publishing ──────────────────────────────────────────────────

    def publish_telemetry(self):
        """Sends the generated sensor data to MQTT using SenML format."""
        ts = int(time.time())
        # Periodically refresh slots list from catalog in case new slots were added/removed
        current_slots = self.get_garden_slots()
        if current_slots:
            # Add state for newly added slots
            for s in current_slots:
                sid = s["slotID"]
                if sid not in self.pump_states:
                    self.pump_states[sid] = "OFF"
                    self.slot_moisture[sid] = 60.0
            
            # Update subscriptions if active slots count changed
            active_sids = {s["slotID"] for s in current_slots}
            old_sids = {s["slotID"] for s in self.slots}
            if active_sids != old_sids and self.client and self.client.is_connected():
                # Unsubscribe from removed slots
                for sid in old_sids - active_sids:
                    self.client.unsubscribe(f"garden/{self.garden_id}/{sid}/pump")
                # Subscribe to new slots
                for sid in active_sids - old_sids:
                    self.client.subscribe(f"garden/{self.garden_id}/{sid}/pump")
            
            self.slots = current_slots

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

    def run(self):
        """Main thread function: gets config, connects to MQTT, and loops to send data every 5 seconds."""
        # 1. Wait for broker config
        broker_cfg = None
        while not broker_cfg and not self.stop_event.is_set():
            broker_cfg = self.get_broker_config()
            if not broker_cfg:
                time.sleep(5)
        if self.stop_event.is_set():
            return
        self.broker_ip = broker_cfg.get("broker_name", "message-broker")

        # 2. Wait for garden slots
        while not self.slots and not self.stop_event.is_set():
            self.slots = self.get_garden_slots()
            if not self.slots:
                time.sleep(5)
        if self.stop_event.is_set():
            return

        # Init per-slot state
        for s in self.slots:
            self.pump_states[s["slotID"]]   = "OFF"
            self.slot_moisture[s["slotID"]] = 60.0

        # 3. Setup and connect MQTT
        self.setup_mqtt()
        self.connect_mqtt()
        if self.stop_event.is_set():
            return
        self.client.loop_start()
        print(f"\n[INIT - {self.device_id}] Telemetry loop started for garden {self.garden_id} with {len(self.slots)} slot(s).")

        # 4. Telemetry loop
        try:
            while not self.stop_event.is_set():
                self.publish_telemetry()
                # sleep in small increments to respond quickly to stop events
                for _ in range(50):
                    if self.stop_event.is_set():
                        break
                    time.sleep(0.1)
        finally:
            print(f"\n[STOP - {self.device_id}] Connector terminated. Disconnecting.")
            self.stop()

    def stop(self):
        """Safely stops the MQTT loop and disconnects."""
        self.stop_event.set()
        if self.client:
            try:
                self.client.loop_stop()
                self.client.disconnect()
            except Exception:
                pass


class DeviceConnectorManager:
    """Manages dynamic discovery and simulation of registered devices in all gardens."""

    def __init__(self):
        self.catalog_url = os.getenv("CATALOG_URL", "http://service-catalog:8080")
        self.active_connectors = {}  # garden_id -> DeviceConnector instance

    def fetch_gardens(self):
        try:
            r = requests.get(f"{self.catalog_url}/gardens", timeout=5)
            r.raise_for_status()
            return r.json()
        except Exception as e:
            print(f"[MANAGER] Catalog unreachable: {e}")
            return []

    def start(self):
        print("[MANAGER] Starting dynamic Device Connector Manager...")
        try:
            while True:
                gardens = self.fetch_gardens()
                current_active_gardens = {}

                for g in gardens:
                    g_id = g.get("gardenID")
                    device_info = g.get("device", {})
                    device_id = device_info.get("deviceID")
                    
                    if device_id and device_info.get("status") == "active":
                        current_active_gardens[g_id] = device_id

                # 1. Start connectors for new active garden devices
                for g_id, d_id in current_active_gardens.items():
                    if g_id not in self.active_connectors:
                        print(f"[MANAGER] New active device detected for garden {g_id}: {d_id}. Starting simulator...")
                        connector = DeviceConnector(self.catalog_url, g_id, d_id)
                        connector.start()
                        self.active_connectors[g_id] = connector
                    elif self.active_connectors[g_id].device_id != d_id:
                        # Device ID changed for this garden
                        print(f"[MANAGER] Device changed for garden {g_id}: {self.active_connectors[g_id].device_id} -> {d_id}. Restarting simulator...")
                        self.active_connectors[g_id].stop()
                        self.active_connectors[g_id].join()
                        connector = DeviceConnector(self.catalog_url, g_id, d_id)
                        connector.start()
                        self.active_connectors[g_id] = connector

                # 2. Stop connectors for gardens that are no longer active/deleted
                for g_id in list(self.active_connectors.keys()):
                    if g_id not in current_active_gardens:
                        print(f"[MANAGER] Device/garden removed for {g_id}. Stopping simulator...")
                        self.active_connectors[g_id].stop()
                        self.active_connectors[g_id].join()
                        del self.active_connectors[g_id]

                time.sleep(10)
        except KeyboardInterrupt:
            print("[MANAGER] Terminating manager. Stopping all simulators...")
            for connector in self.active_connectors.values():
                connector.stop()
            for connector in self.active_connectors.values():
                connector.join()
            print("[MANAGER] Done.")


if __name__ == "__main__":
    manager = DeviceConnectorManager()
    manager.start()
