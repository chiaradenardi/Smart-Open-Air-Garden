import time
import json
import requests
from MyMQTT import MyMQTT

class SmartIrrigation:
    def __init__(self, clientID, broker, port, catalog_url):
        self.client = MyMQTT(clientID, broker, port, self)
        self.catalog_url = catalog_url
        
        #Dictionary to manage the pump status of each device separately
        #Example: {"RPi_001": True, "RPi_002": False}
        self.pumps_status = {} 
        
        #dictionary to avoid querying the weather repeatedly if we have already decided not to irrigate
        self.last_weather_check = {} 
        self.weather_cooldown = 900 # Cooldown of 15 minutes in seconds
        
        import os
        self.weather_adaptor_url = os.getenv("WEATHER_URL", "http://weather-service-adaptor:8085")
        self.topic_sub = "garden/+/telemetry"

    def start(self):
        self.client.start()
        self.client.mySubscribe(self.topic_sub)
        print(f"--- Smart Irrigation multizone started ---")
        print(f"Catalog: {self.catalog_url}")
        print(f"Weather: {self.weather_adaptor_url}")

    def notify(self, topic, payload):
        try:
            if isinstance(payload, bytes):
                payload = payload.decode('utf-8')
            msg = json.loads(payload)
            
            current_moisture = None
        
        # If the message is a list (SenML)
            if isinstance(msg, list):
                for entry in msg:
                    if entry.get("n") == "soil_moisture":
                        current_moisture = entry.get("v")
                        break
        # If the message is a simple dictionary (for compatibility)
            elif isinstance(msg, dict):
                current_moisture = msg.get("soil_moisture")
            
            if current_moisture is None: 
                return

            # Identification of the device
            device_id = topic.split('/')[1]

            # Skip messages from generic/non-device topics
            if not device_id.lower().startswith("rpi"):
                return

            # Initialise pump state for this device on first sight
            if device_id not in self.pumps_status:
                self.pumps_status[device_id] = False

            # Find which plant is associated with this device_id
            slots_res = requests.get(f"{self.catalog_url}/slots").json()
            
            plant_id = None
            slot_name = "Unknown"
            for slot in slots_res:
                if slot.get("deviceID") == device_id:
                    plant_id = slot.get("plantID")
                    slot_name = slot.get("slotName", "Zone")
                    break
            
            if not plant_id:
                print(f"[!] {device_id} not associated with any crop in the catalog.")
                return

            # Get the specific threshold for that plant
            strat_res = requests.get(f"{self.catalog_url}/strategies/{plant_id}").json()
            moisture_threshold = strat_res.get("min_moisture_threshold", 40.0)
            plant_name = strat_res.get("name", "Crop")
            
            # Stop threshold (20% above the minimum)
            target_moisture = moisture_threshold + 20.0

            print(f"[{slot_name} - {device_id}] {plant_name}: {current_moisture}% | Range: {moisture_threshold}%-{target_moisture}%")

            # Control logic (independent for each device)
        
            if current_moisture < moisture_threshold:
                if not self.pumps_status[device_id]:
                    # Check if we have already queried the weather recently for this device
                    now = time.time()
                    last_check = self.last_weather_check.get(device_id, 0)
                    
                    if (now - last_check) < self.weather_cooldown:
                        # We checked recently and saw it was raining.
                        # Exit to avoid flooding with weather requests.
                        return
                    
                    print(f"[{device_id}] Critical moisture. Checking weather...")
                    self.last_weather_check[device_id] = now
                    
                    rain_6h = 0
                    try:
                        weather_res = requests.get(self.weather_adaptor_url, timeout=5).json()
                        rain_6h = weather_res.get("total_rain_accumulation_6h", 0)
                        #STRESS TEST
                        #rain_6h = 50.0
                    except Exception as e:
                        print(f"  [!] Weather Error: {e}. Proceeding with safety irrigation.")

                    if rain_6h < 2.0:
                        print(f"[{device_id}] Action: START Irrigation (Rain expected: {rain_6h}mm)")
                        command_payload = [{
                            "bn": f"{device_id}/",
                            "n": "pump_status",
                            "v": 1, # 1 = ON
                            "u": "on/off",
                            "t": int(time.time())
                        }]
                        self.client.myPublish(f"garden/{device_id}/pump", command_payload)
                        self.pumps_status[device_id] = True
                        
                    else:
                        print(f"[{device_id}] Action: SKIP (Rain expected)")

            #Turning off
            elif current_moisture >= target_moisture:
                if self.pumps_status[device_id]:
                    print(f"[{device_id}] Humidity restored. Action: STOP.")
                    command_payload = [{
                        "bn": f"{device_id}/",
                        "n": "pump_status",
                        "v": 0, # 0 = OFF
                        "u": "on/off",
                        "t": int(time.time())
                    }]
                    self.client.myPublish(f"garden/{device_id}/pump", command_payload)
                    self.pumps_status[device_id] = False
                    
                    #RESET COOLDOWN
                    self.last_weather_check[device_id] = 0
        except Exception as e:
            print(f"Error notify for {topic}: {e}")

if __name__ == "__main__":
    print("Brain initializing...")
    # NOTE: catalog_url must be without the trailing slash
    brain = SmartIrrigation("IrrigationBrain", "message-broker", 1883, "http://service-catalog:8080")
    brain.start()
    print("System started and listening!")
    while True:
        time.sleep(1)