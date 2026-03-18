import requests
import time
import random
import json
import os
import paho.mqtt.client as mqtt

#DA MODIFICARE 

# --- CONFIGURATION FOR DOCKER VARIABLES ---
### NEED TO SET WITH CORRECT URL OF CATALOG (IF NOT USING DOCKER, DEFAULT IS LOCALHOST)
CATALOG_URL = os.getenv("CATALOG_URL", "http://127.0.0.1:8080/device_config")

# Global variable for state of simulated pump
pump_state = "OFF"  # Variabile globale che simula lo stato del nostro attuatore fisico

# --- HARDWARE SIMULATION ---
def simulate_sensors(current_moisture):
    """Simulation of DHT11 and humidity sensors"""
    temp = round(random.uniform(20.0, 24.0), 1)
    air_humidity = round(random.uniform(40.0, 50.0), 1)
    
    global pump_state
    if pump_state == "ON":
        new_moisture = 100.0  # Pump is on, soil is fully watered
    else:
        new_moisture = max(0.0, current_moisture - 0.5)  # Soil dries slowly
        
    return temp, air_humidity, new_moisture

# --- REST FUNCTIONS ---
def get_broker_config():
    """Contact the Catalog via REST to get the configurations at startup, in particular Broker's IP and topics."""
    print("[INIT] Contacting the Service & Resource Catalog via REST")
    try:
        response = requests.get(CATALOG_URL, timeout=10)
        response.raise_for_status()
        config_data = response.json()
        print(f"[INIT] Configuration received from Catalog: {config_data}")
        return config_data
    except requests.exceptions.RequestException as e:
        print(f"[ERROR] Impossible to contact Catalog. Detail: {e}")
        return None

# --- MQTT CALLBACK ---
def on_connect(client, userdata, flags, rc):
    """Callback eseguita quando il client si connette al broker."""
    if rc == 0:
        print("[MQTT] Successfully connected to MQTT Broker")
        # Once connected, it will act as a Subscriber by subscribing to the command topic
        client.subscribe(userdata['command_topic'])
        print(f"[MQTT] Listening to topic commands: {userdata['command_topic']}")
    else:
        print(f"[MQTT] Error connecting to MQTT Broker. Code: {rc}")

def on_message(client, userdata, msg):
    """When a message is received on a topic we are subscribed to, callback is executed."""
    global pump_state
    payload = msg.payload.decode('utf-8')
    print(f"\n[MQTT Received] Topic: {msg.topic} | Action: {payload}")
    
    # Attuatio logic: analizes the command and "turns on/off" the pump
    if "ON" in payload.upper():
        pump_state = "ON"
        print("PUMP TURNED ON: Water is flowing")
    elif "OFF" in payload.upper():
        pump_state = "OFF"
        print("PUMP TURNED OFF: Water is not flowing")

# --- MAIN FLOW ---
if __name__ == "__main__":
    # 1. retrieving configurations via REST from the Catalog (waits until the Catalog is available)
    broker_config = None
    while not broker_config:
        broker_config = get_broker_config()
        if not broker_config:
            time.sleep(5)

     #extracting necessary info from the json received from the Catalog
     ### INSERT CORRECT KEYS       
    broker_ip = broker_config.get("broker_ip", "localhost")
    telemetry_topic = broker_config.get("telemetry_topic", "garden/sensors/telemetry")
    command_topic = broker_config.get("command_topic", "garden/actuators/pump")
    
    # 2. Setup MQTT Client and connect to the broker
    client = mqtt.Client(userdata={'command_topic': command_topic})
    client.on_connect = on_connect
    client.on_message = on_message
    
    print(f"[SETUP] Connecting to MQTT Broker on {broker_ip}")
    while True:
        try:
            client.connect(broker_ip, 1883, 60)
            break  # Exit the loop if connection is successful
        except Exception as e:
            print(f"[ERROR MQTT] Connection failed: {e}. Retrying in 5 seconds.")
            time.sleep(5)  # Wait before retrying
        
    # Activate MQTT Loop: Start the MQTT loop in the background to handle message reception and pings
    client.loop_start()
    
    # 3. Main Cycle: Reading sensors and Publishing telemetry
    soil_moisture = 60.0  # Initial moisture
    print("\n[INIT] Starting the sensor simulation and telemetry publishing loop.")    
    
    try:
        while True:               
            # Reads sensors simulation (temperature, air humidity, soil moisture) and updates soil moisture based on pump state
            temp, air_hum, soil_moisture = simulate_sensors(soil_moisture)
            
            # Prepare the payload in JSON format
            payload = {
                "temperature": temp,
                "air_humidity": air_hum,
                "soil_moisture": soil_moisture,
                "timestamp": time.time()
            }
            
            # Acts as a Publisher sending the telemetry
            client.publish(telemetry_topic, json.dumps(payload))
            print(f"[TELEMETRY] Temp: {temp}°C | Soil Moisture: {soil_moisture}% | Pump State: {pump_state}")
            
            time.sleep(5)  # Sampling frequency
            
    except KeyboardInterrupt:
        print("\n[STOP] Connector terminated by user. Disconnecting.")
        client.loop_stop()
        client.disconnect()