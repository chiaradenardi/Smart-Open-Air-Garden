import requests
import time
import random
import json
import os
import paho.mqtt.client as mqtt

CATALOG_URL = os.getenv("CATALOG_URL", "http://service-catalog:8080/broker")
DEVICE_ID = os.getenv("DEVICE_ID", "RPi_001")
pump_state = "OFF"   # global variable for simulating the state of our physical actuator 


def simulate_sensors(current_moisture):
    #DHT11 and humidity sensors'simulation
    termp = round(random.uniform(20.0, 24.0), 1)
    air_humidity = round(random.uniform(40.0, 50.0), 1)
    
    global pump_state
    if pump_state == "ON":
        new_moisture = min(100.0, current_moisture + 2.0)  
    else:
        new_moisture = max(30.0, current_moisture - 0.5)  #soil drying
        
    return termp, air_humidity, new_moisture


def get_broker_config():
    #Fetches data via REST from catalog
    print("[INIT] Requesting configuration from Catalog")
    try:
        response = requests.get(CATALOG_URL, timeout=10)
        response.raise_for_status()
        configuration_data = response.json()
        print(f"[INIT] Settings received: {configuration_data}")
        return configuration_data
    except requests.exceptions.RequestException as e:
        print(f"[ERROR] Failed to reach Catalog. Details: {e}")
        return None


def on_connect(client, userdata, flags, rc): 
    if rc == 0:
        print("[MQTT] Connection established with broker")
        client.subscribe(userdata['command_topic'])
        print(f"[MQTT] Listening to topic commands: {userdata['command_topic']}")
    else:
        print(f"[MQTT] Connection failed with error code: {rc}")

def on_message(client, userdata, msg):
    #toggle pump (on/off) based on message content
    global pump_state
    payload = msg.payload.decode('utf-8')
    print(f"\n[MQTT Received] Topic: {msg.topic} | Action: {payload}")
    
    if "ON" in payload.upper():
        pump_state = "ON"
        print(">>> SYSTEM UPDATE: Pump activated")
    elif "OFF" in payload.upper():
        pump_state = "OFF"
        print(">>> SYSTEM UPDATE: Pump deactivated")


if __name__ == "__main__":
    broker_configuration = None
    while not broker_configuration: 
        broker_configuration = get_broker_config() # when Catalog is availabe 
        if not broker_configuration:
            time.sleep(5)
            
    # Ottieni la configurazione specifica del dispositivo dal catalogo per leggere il Client ID
    device_client_id = f"Client_{DEVICE_ID}" # Fallback
    try:
        catalog_base = CATALOG_URL.replace("/broker", "")
        res = requests.get(f"{catalog_base}/devices/{DEVICE_ID}", timeout=10)
        if res.status_code == 200 and "config" in res.json():
            device_client_id = res.json()["config"].get("clientID", device_client_id)
            print(f"[INIT] Device Client ID fetched: {device_client_id}")
    except Exception as e:
        print(f"[WARNING] Could not fetch specific device config, using fallback ID {device_client_id}: {e}")

    broker_ip = broker_configuration.get("broker_name", "message-broker") 
    telemetry_topic = f"garden/{DEVICE_ID}/telemetry"  
    command_topic = f"garden/{DEVICE_ID}/pump"  
    
    # setup MQTT Client passing topics through callback and setting the Client ID
    client = mqtt.Client(client_id=device_client_id, userdata={'command_topic': command_topic})
    client.on_connect = on_connect
    client.on_message = on_message
    
    print(f"[SETUP] Connecting to broker at: {broker_ip} with ID {device_client_id}")
    while True:
        try:
            client.connect(broker_ip, 1883, 60)
            break 
        except Exception as e:
            print(f"[ERROR] MQTT Connection failed. Retrying... ({e})")
            time.sleep(5)  
        

    client.loop_start()
    soil_moisture = 60.0  # default
    print("\n[INIT] Telemetry loop started. Press Ctrl+C to stop.")    
    
    try:
        while True:               
            # data acquisition from our simulated sensors
            temp, air_hum, soil_moisture = simulate_sensors(soil_moisture)
            
            # our message payload to be sent to the broker in SenML format
            payload = [
                {"bn": f"{DEVICE_ID}/", "n": "temperature", "v": temp, "u": "Cel", "t": int(time.time())},
                {"n": "air_humidity", "v": air_hum, "u": "%RH", "t": int(time.time())},
                {"n": "soil_moisture", "v": soil_moisture, "u": "%RH", "t": int(time.time())}
            ]
            
            client.publish(telemetry_topic, json.dumps(payload))
            print(f"[TELEMETRY] Temp: {temp}°C | Soil Moisture: {soil_moisture}% | Pump State: {pump_state}")
            
            time.sleep(5)  
            
    except KeyboardInterrupt:
        print("\n[STOP] Connector terminated by user. Disconnecting.")
        client.loop_stop()
        client.disconnect()