import requests
import time
import random
import json
import os
import paho.mqtt.client as mqtt

CATALOG_URL = os.getenv("CATALOG_URL", "http://service-catalog:8080")
GARDEN_ID   = os.getenv("GARDEN_ID",   "G_001")
DEVICE_ID   = os.getenv("DEVICE_ID",   "RPi_001")

# slot_id -> pump state ("ON"/"OFF")
pump_states = {}


def get_broker_config():
    print("[INIT] Requesting broker config from Catalog")
    try:
        r = requests.get(f"{CATALOG_URL}/broker", timeout=10)
        r.raise_for_status()
        return r.json()
    except Exception as e:
        print(f"[ERROR] Cannot reach Catalog: {e}")
        return None


def get_garden_slots():
    """Fetch the list of slots for this garden from the Catalog."""
    try:
        r = requests.get(f"{CATALOG_URL}/gardens/{GARDEN_ID}/slots", timeout=10)
        r.raise_for_status()
        slots = r.json()
        print(f"[INIT] Garden {GARDEN_ID}: {len(slots)} slot(s) found")
        return slots
    except Exception as e:
        print(f"[ERROR] Cannot fetch slots for garden {GARDEN_ID}: {e}")
        return []


def simulate_sensors(slot_id, current_moisture):
    temp        = round(random.uniform(20.0, 24.0), 1)
    air_humidity = round(random.uniform(40.0, 50.0), 1)
    if pump_states.get(slot_id) == "ON":
        new_moisture = min(100.0, current_moisture + 2.0)
    else:
        new_moisture = max(30.0, current_moisture - 0.5)
    return temp, air_humidity, new_moisture


def on_connect(client, userdata, flags, rc):
    if rc == 0:
        print("[MQTT] Connected to broker")
        # subscribe to pump commands for every slot
        for slot_id in userdata["slot_ids"]:
            topic = f"garden/{GARDEN_ID}/{slot_id}/pump"
            client.subscribe(topic)
            print(f"[MQTT] Subscribed to: {topic}")
    else:
        print(f"[MQTT] Connection failed: {rc}")


def on_message(client, userdata, msg):
    global pump_states
    payload_str = msg.payload.decode('utf-8')
    parts = msg.topic.split('/')          # garden / G_001 / P1_R1 / pump
    if len(parts) < 4:
        return
    slot_id = parts[2]
    try:
        data = json.loads(payload_str)
        if isinstance(data, list):
            for entry in data:
                if entry.get("n") == "pump_status":
                    if entry.get("v") == 1:
                        pump_states[slot_id] = "ON"
                        print(f"[{slot_id}] Pump activated")
                    elif entry.get("v") == 0:
                        pump_states[slot_id] = "OFF"
                        print(f"[{slot_id}] Pump deactivated")
                    break
    except Exception as e:
        print(f"[ERROR] Payload parse error: {e}")


if __name__ == "__main__":
    # 1. Wait for catalog
    broker_cfg = None
    while not broker_cfg:
        broker_cfg = get_broker_config()
        if not broker_cfg:
            time.sleep(5)

    # 2. Fetch garden slots
    slots = []
    while not slots:
        slots = get_garden_slots()
        if not slots:
            time.sleep(5)

    # Init per-slot state
    slot_moisture = {s["slotID"]: 60.0 for s in slots}
    for s in slots:
        pump_states[s["slotID"]] = "OFF"

    slot_ids = [s["slotID"] for s in slots]

    # 3. Connect MQTT
    broker_ip = broker_cfg.get("broker_name", "message-broker")
    client_id = f"Client_{DEVICE_ID}"
    client = mqtt.Client(client_id=client_id, userdata={"slot_ids": slot_ids})
    client.on_connect = on_connect
    client.on_message = on_message

    print(f"[SETUP] Connecting to broker {broker_ip} as {client_id}")
    while True:
        try:
            client.connect(broker_ip, 1883, 60)
            break
        except Exception as e:
            print(f"[ERROR] MQTT connection failed, retrying... ({e})")
            time.sleep(5)

    client.loop_start()
    print(f"[INIT] Telemetry loop started for garden {GARDEN_ID} with {len(slots)} slot(s).")

    try:
        while True:
            ts = int(time.time())
            for s in slots:
                slot_id = s["slotID"]
                temp, air_hum, slot_moisture[slot_id] = simulate_sensors(slot_id, slot_moisture[slot_id])

                payload = [
                    {"bn": f"{DEVICE_ID}/{slot_id}/", "n": "temperature",    "v": temp,                            "u": "Cel",  "t": ts},
                    {"n": "air_humidity",                                      "v": air_hum,                         "u": "%RH",  "t": ts},
                    {"n": "soil_moisture",                                     "v": round(slot_moisture[slot_id], 1), "u": "%RH",  "t": ts}
                ]
                topic = f"garden/{GARDEN_ID}/{slot_id}/telemetry"
                client.publish(topic, json.dumps(payload))
                print(f"[{GARDEN_ID}/{slot_id}] Temp:{temp}°C Moisture:{round(slot_moisture[slot_id],1)}% Pump:{pump_states[slot_id]}")

            time.sleep(5)

    except KeyboardInterrupt:
        print("[STOP] Connector stopped.")
        client.loop_stop()
        client.disconnect()