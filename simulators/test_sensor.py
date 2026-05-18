import time
import json
import random
import requests
from MyMQTT import MyMQTT


class MultiSensorSim:
    def __init__(self, clientID, broker, port, catalog_url):
        self.broker      = broker
        self.port        = port
        self.catalog_url = catalog_url
        self.clientID    = clientID
        # key: "gardenID/slotID" → {moisture, pump_active, topic_pub, topic_sub}
        self.devices = {}

        self._load_from_catalog()
        self.client = MyMQTT(clientID, broker, port, self)

    def _load_from_catalog(self):
        """Fetch all gardens and their slots from the catalog."""
        try:
            print(f"[SIM] Fetching gardens from: {self.catalog_url}/gardens")
            r = requests.get(f"{self.catalog_url}/gardens", timeout=10)
            r.raise_for_status()
            gardens = r.json()
            for garden in gardens:
                g_id = garden["gardenID"]
                for slot in garden.get("slots", []):
                    s_id = slot["slotID"]
                    key  = f"{g_id}/{s_id}"
                    self.devices[key] = {
                        "gardenID":   g_id,
                        "slotID":     s_id,
                        "moisture":   80.0,
                        "pump_active": False,
                        "topic_pub":  f"garden/{g_id}/{s_id}/telemetry",
                        "topic_sub":  f"garden/{g_id}/{s_id}/pump"
                    }
            print(f"[SIM] Loaded {len(self.devices)} slot(s): {list(self.devices.keys())}")
        except Exception as e:
            print(f"[!] Cannot contact Catalog: {e}")

    def startSim(self):
        self.client.start()
        for key, d in self.devices.items():
            self.client.mySubscribe(d["topic_sub"])
            print(f"[SIM] Listening on: {d['topic_sub']}")

    def stopSim(self):
        self.client.stop()

    def notify(self, topic, payload):
        """Receives pump commands: garden/{gardenID}/{slotID}/pump"""
        if isinstance(payload, bytes):
            payload = payload.decode('utf-8')
        msg = json.loads(payload)
        if isinstance(msg, str):
            msg = json.loads(msg)

        # SenML list → take first entry
        if isinstance(msg, list) and len(msg) > 0:
            msg = msg[0]

        parts = topic.split('/')       # ['garden', 'G_001', 'P1_R1', 'pump']
        if len(parts) < 4:
            return
        key = f"{parts[1]}/{parts[2]}"

        if key not in self.devices:
            return

        v_value = msg.get("v")
        status  = msg.get("status")

        if status == "ON" or v_value == 1:
            self.devices[key]["pump_active"] = True
            print(f"[SIM] {key} → Pump ON")
        elif status == "OFF" or v_value == 0:
            self.devices[key]["pump_active"] = False
            print(f"[SIM] {key} → Pump OFF")

    def run_cycle(self):
        ts = int(time.time())
        if not self.devices:
            print("[SIM] No devices to simulate. Check the Catalog.")
            return

        for key, d in self.devices.items():
            # Update moisture
            if d["pump_active"]:
                d["moisture"] = min(100.0, d["moisture"] + round(random.uniform(5.0, 10.0), 1))
            else:
                d["moisture"] = max(10.0,  d["moisture"] - round(random.uniform(0.5, 2.0), 1))

            temp    = round(random.uniform(20.0, 25.0), 2)
            air_hum = round(random.uniform(40.0, 50.0), 1)

            packet = [
                {"bn": f"{d['gardenID']}/{d['slotID']}/", "n": "temperature",  "v": temp,                    "u": "Cel",  "t": ts},
                {"n": "air_humidity",                                            "v": air_hum,                 "u": "%RH",  "t": ts},
                {"n": "soil_moisture",                                           "v": round(d["moisture"], 1), "u": "%RH",  "t": ts}
            ]
            self.client.myPublish(d["topic_pub"], packet)
            print(f"[SIM] {key} | Moisture: {round(d['moisture'],1)}% | Pump: {'ON' if d['pump_active'] else 'OFF'}")


if __name__ == "__main__":
    CATALOG_URL = "http://localhost:8080"

    sim = MultiSensorSim("MultiSim_Garden", "localhost", 1883, CATALOG_URL)
    sim.startSim()

    try:
        while True:
            sim.run_cycle()
            print("-" * 50)
            time.sleep(5)
    except KeyboardInterrupt:
        sim.stopSim()