import requests
import time
import random
import json
import os
import paho.mqtt.client as mqtt


class DeviceConnector:
    """IoT device connector for simulating sensors and controlling actuators via MQTT."""
    
    def __init__(self):
        """Initialize the device connector with configuration from environment."""
        self.catalog_url = os.getenv("CATALOG_URL", "http://service-catalog:8080/broker")
        self.device_id = os.getenv("DEVICE_ID", "RPi_001")
        self.pump_state = "OFF"
        self.soil_moisture = 60.0
        
        self.broker_ip = None
        self.broker_port = 1883
        self.device_client_id = f"Client_{self.device_id}"
        self.telemetry_topic = f"garden/{self.device_id}/telemetry"
        self.command_topic = f"garden/{self.device_id}/pump"
        
        self.client = None
    
    def get_broker_config(self):
        """Fetch broker configuration from the Service Catalog."""
        print("[INIT] Requesting configuration from Catalog")
        try:
            response = requests.get(self.catalog_url, timeout=10)
            response.raise_for_status()
            configuration_data = response.json()
            print(f"[INIT] Settings received: {configuration_data}")
            return configuration_data
        except requests.exceptions.RequestException as e:
            print(f"[ERROR] Failed to reach Catalog. Details: {e}")
            return None
    
    def fetch_device_client_id(self):
        """Fetch device-specific Client ID from the Service Catalog."""
        try:
            catalog_base = self.catalog_url.replace("/broker", "")
            res = requests.get(f"{catalog_base}/devices/{self.device_id}", timeout=10)
            if res.status_code == 200 and "config" in res.json():
                self.device_client_id = res.json()["config"].get("clientID", self.device_client_id)
                print(f"[INIT] Device Client ID fetched: {self.device_client_id}")
        except Exception as e:
            print(f"[WARNING] Could not fetch specific device config, using fallback ID {self.device_client_id}: {e}")
    
    def _on_connect(self, client, userdata, flags, rc):
        """MQTT connection callback."""
        if rc == 0:
            print("[MQTT] Connection established with broker")
            client.subscribe(self.command_topic)
            print(f"[MQTT] Listening to topic commands: {self.command_topic}")
        else:
            print(f"[MQTT] Connection failed with error code: {rc}")
    
    def _on_message(self, client, userdata, msg):
        """MQTT message callback - updates pump state based on received commands."""
        payload_str = msg.payload.decode('utf-8')
        print(f"\n[MQTT Received] Topic: {msg.topic} | Action: {payload_str}")
        
        try:
            data = json.loads(payload_str)
            # Handle SenML format
            if isinstance(data, list):
                for entry in data:
                    if entry.get("n") == "pump_status":
                        if entry.get("v") == 1:
                            self.pump_state = "ON"
                            print(">>> SYSTEM UPDATE: Pump activated")
                        elif entry.get("v") == 0:
                            self.pump_state = "OFF"
                            print(">>> SYSTEM UPDATE: Pump deactivated")
                        break
        except Exception as e:
            print(f"[ERROR] Failed to parse payload: {e}")
    
    def simulate_sensors(self):
        """Simulate DHT11 and soil moisture sensor readings."""
        temp = round(random.uniform(20.0, 24.0), 1)
        air_humidity = round(random.uniform(40.0, 50.0), 1)
        
        if self.pump_state == "ON":
            new_moisture = min(100.0, self.soil_moisture + 2.0)
        else:
            new_moisture = max(30.0, self.soil_moisture - 0.5)
        
        self.soil_moisture = new_moisture
        return temp, air_humidity, new_moisture
    
    def setup_mqtt(self):
        """Initialize and setup MQTT client."""
        self.client = mqtt.Client(client_id=self.device_client_id)
        self.client.on_connect = self._on_connect
        self.client.on_message = self._on_message
    
    def connect_mqtt(self):
        """Connect to the MQTT broker with retry logic."""
        print(f"[SETUP] Connecting to broker at: {self.broker_ip} with ID {self.device_client_id}")
        while True:
            try:
                self.client.connect(self.broker_ip, self.broker_port, 60)
                break
            except Exception as e:
                print(f"[ERROR] MQTT Connection failed. Retrying... ({e})")
                time.sleep(5)
    
    def publish_telemetry(self):
        """Publish sensor readings to the broker in SenML format."""
        temp, air_hum, soil_moisture = self.simulate_sensors()
        
        payload = [
            {"bn": f"{self.device_id}/", "n": "temperature", "v": temp, "u": "Cel", "t": int(time.time())},
            {"n": "air_humidity", "v": air_hum, "u": "%RH", "t": int(time.time())},
            {"n": "soil_moisture", "v": soil_moisture, "u": "%RH", "t": int(time.time())}
        ]
        
        self.client.publish(self.telemetry_topic, json.dumps(payload))
        print(f"[TELEMETRY] Temp: {temp}°C | Soil Moisture: {soil_moisture}% | Pump State: {self.pump_state}")
    
    def start(self):
        """Start the device connector."""
        # Fetch broker configuration
        broker_configuration = None
        while not broker_configuration:
            broker_configuration = self.get_broker_config()
            if not broker_configuration:
                time.sleep(5)
        
        self.broker_ip = broker_configuration.get("broker_name", "message-broker")
        
        # Fetch device-specific client ID
        self.fetch_device_client_id()
        
        # Setup MQTT
        self.setup_mqtt()
        
        # Connect to broker
        self.connect_mqtt()
        
        # Start the MQTT loop
        self.client.loop_start()
        print("\n[INIT] Telemetry loop started. Press Ctrl+C to stop.")
        
        try:
            while True:
                self.publish_telemetry()
                time.sleep(5)
        except KeyboardInterrupt:
            print("\n[STOP] Connector terminated by user. Disconnecting.")
            self.client.loop_stop()
            self.client.disconnect()
    
    def stop(self):
        """Stop the device connector."""
        if self.client:
            self.client.loop_stop()
            self.client.disconnect()


if __name__ == "__main__":
    connector = DeviceConnector()
    connector.start()