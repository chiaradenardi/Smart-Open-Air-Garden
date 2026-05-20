import time
import json
import requests
from shared_utils.MyMQTT import MyMQTT


class SmartIrrigation:
    """This is the brain of the system. It decides when to turn the pump on or off based on moisture and weather."""
    def __init__(self, clientID, broker, port, catalog_url):
        """Initializes the irrigation logic and connects to the MQTT broker."""
        self.client      = MyMQTT(clientID, broker, port, self)
        self.catalog_url = catalog_url
        # key: "gardenID/slotID" → bool (pump on?)
        self.pumps_status       = {}
        self.last_weather_check = {}
        self.weather_cooldown   = 900   # 15 min

        import os
        self.weather_adaptor_url = os.getenv("WEATHER_URL", "http://weather-service-adaptor:8085")
        # 4-level wildcard: garden / gardenID / slotID / telemetry
        self.topic_sub = "garden/+/+/telemetry"

    def start(self):
        """Starts the MQTT connection and subscribes to telemetry messages."""
        self.client.start()
        self.client.mySubscribe(self.topic_sub)
        print("--- Smart Irrigation multi-garden started ---")
        print(f"Catalog: {self.catalog_url}")
        print(f"Weather: {self.weather_adaptor_url}")

    def notify(self, topic, payload):
        """Receives sensor data. Checks if moisture is too low, checks the weather, and turns the pump on or off."""
        try:
            if isinstance(payload, bytes):
                payload = payload.decode('utf-8')
            msg = json.loads(payload)

            # Extract soil_moisture from SenML
            current_moisture = None
            if isinstance(msg, list):
                for entry in msg:
                    if entry.get("n") == "soil_moisture":
                        current_moisture = entry.get("v")
                        break
            elif isinstance(msg, dict):
                current_moisture = msg.get("soil_moisture")

            if current_moisture is None:
                return

            # Parse topic: garden / gardenID / slotID / telemetry
            parts = topic.split('/')
            if len(parts) < 4:
                return
            garden_id = parts[1]
            slot_id   = parts[2]
            key       = f"{garden_id}/{slot_id}"

            # Init pump state on first message
            if key not in self.pumps_status:
                self.pumps_status[key] = False

            # Fetch slot info from catalog to get plantID
            try:
                slot_res = requests.get(
                    f"{self.catalog_url}/gardens/{garden_id}/slots/{slot_id}",
                    timeout=5
                ).json()
            except Exception as e:
                print(f"[!] Cannot fetch slot {key}: {e}")
                return

            plant_id  = slot_res.get("plantID")
            slot_name = slot_res.get("slotName", key)
            if not plant_id:
                print(f"[!] No plantID for slot {key}")
                return

            # Fetch irrigation strategy
            strat = requests.get(
                f"{self.catalog_url}/strategies/{plant_id}", timeout=5
            ).json()
            moisture_threshold = strat.get("min_moisture_threshold", 40.0)
            plant_name         = strat.get("name", "Crop")
            target_moisture    = moisture_threshold + 20.0

            print(f"[{slot_name}] {plant_name}: {current_moisture}% | range {moisture_threshold}%–{target_moisture}%")

            pump_topic    = f"garden/{garden_id}/{slot_id}/pump"

            # Turn ON logic
            if current_moisture < moisture_threshold:
                if not self.pumps_status[key]:
                    now        = time.time()
                    last_check = self.last_weather_check.get(key, 0)
                    if (now - last_check) < self.weather_cooldown:
                        return
                    print(f"[{key}] Critical moisture. Checking weather...")
                    self.last_weather_check[key] = now

                    rain_6h = 0
                    try:
                        wr      = requests.get(self.weather_adaptor_url, timeout=5).json()
                        rain_6h = wr.get("total_rain_accumulation_6h", 0)
                    except Exception as e:
                        print(f"  [!] Weather error: {e}. Proceeding with irrigation.")

                    if rain_6h < 2.0:
                        print(f"[{key}] START irrigation (rain: {rain_6h}mm)")
                        cmd = [{"bn": f"{garden_id}/{slot_id}/", "n": "pump_status", "v": 1, "u": "on/off", "t": int(time.time())}]
                        self.client.myPublish(pump_topic, cmd)
                        self.pumps_status[key] = True
                    else:
                        print(f"[{key}] SKIP (rain expected: {rain_6h}mm)")

            # Turn OFF logic 
            elif current_moisture >= target_moisture:
                if self.pumps_status[key]:
                    print(f"[{key}] Moisture restored. STOP.")
                    cmd = [{"bn": f"{garden_id}/{slot_id}/", "n": "pump_status", "v": 0, "u": "on/off", "t": int(time.time())}]
                    self.client.myPublish(pump_topic, cmd)
                    self.pumps_status[key] = False
                    self.last_weather_check[key] = 0

        except Exception as e:
            print(f"[ERROR] notify() for {topic}: {e}")


if __name__ == "__main__":
    print("Smart Irrigation initializing...")
    brain = SmartIrrigation("IrrigationBrain", "message-broker", 1883, "http://service-catalog:8080")
    brain.start()
    print("System started and listening!")
    while True:
        time.sleep(1)