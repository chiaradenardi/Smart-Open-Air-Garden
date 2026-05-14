import time
import json
import random
import requests
from MyMQTT import MyMQTT

class MultiSensorSim:
    def __init__(self, clientID, broker, port, catalog_url):
        self.broker = broker
        self.port = port
        self.catalog_url = catalog_url
        self.devices = {}
        self.clientID = clientID
        
        # 1. get devices from catalog
        self.get_devices_from_catalog()
            
        self.client = MyMQTT(clientID, broker, port, self)

    def get_devices_from_catalog(self):
        """Si collega al Catalogo e scarica tutti i deviceID registrati negli slots"""
        try:
            print(f"[SIM] Recupero dispositivi da: {self.catalog_url}/slots")
            response = requests.get(f"{self.catalog_url}/slots")
            if response.status_code == 200:
                slots_list = response.json()
                for slot in slots_list:
                    d_id = slot.get("deviceID")
                    if d_id and d_id not in self.devices:
                        self.devices[d_id] = {
                            "moisture": 80.0,
                            "pump_active": False,
                            "topic_pub": f"garden/{d_id}/telemetry",
                            "topic_sub": f"garden/{d_id}/pump"
                        }
                print(f"[SIM] Trovati {len(self.devices)} dispositivi: {list(self.devices.keys())}")
            else:
                print(f"[!] Errore Catalogo: {response.status_code}")
        except Exception as e:
            print(f"[!] Impossibile contattare il Catalogo: {e}")

    def startSim(self):
        self.client.start()
        for d_id in self.devices:
            self.client.mySubscribe(self.devices[d_id]["topic_sub"])
            print(f"[SIM] Listening for {d_id} on: {self.devices[d_id]['topic_sub']}")

    def stopSim(self):
        self.client.stop()

    def notify(self, topic, payload):
        """Riceve i comandi dal Cervello"""
        if isinstance(payload, bytes):
            payload = payload.decode('utf-8')
        msg = json.loads(payload)
        if isinstance(msg, str):
            msg = json.loads(msg)

        # support for SenML array: extract first dictionary if list
        if isinstance(msg, list) and len(msg) > 0:
            msg = msg[0]

        target_device = topic.split('/')[1]
        
        if target_device in self.devices:
            # check old key 'status' and new key 'v' (SenML)
            status = msg.get("status")
            v_value = msg.get("v")
            
            # turns on if status is "ON" or if the SenML value is 1
            if status == "ON" or v_value == 1:
                self.devices[target_device]["pump_active"] = True
                print(f"[SIM] {target_device} -> Pump turned ON")
            elif status == "OFF" or v_value == 0:
                self.devices[target_device]["pump_active"] = False
                print(f"[SIM] {target_device} -> Pump turned OFF")

    def run_cycle(self):
        # update and publish data of all sensors found
        timestamp = int(time.time())
        if not self.devices:
            print("[SIM] No device to simulate. Check the Catalog.")
            return

        for d_id, data in self.devices.items():
            if data["pump_active"]:
                data["moisture"] += round(random.uniform(5.0, 10.0), 1)
                if data["moisture"] > 90: data["moisture"] = 90.0
            else:
                data["moisture"] -= round(random.uniform(0.5, 2.0), 1)
                if data["moisture"] < 10: data["moisture"] = 10.0

            temp = round(random.uniform(20.0, 25.0), 2)
            packet = [
                {"bn": f"{d_id}/", "n": "temperature", "v": temp, "u": "Cel", "t": timestamp},
                {"n": "soil_moisture", "v": round(data["moisture"], 1), "u": "%RH", "t": timestamp}
            ]

            self.client.myPublish(data["topic_pub"], packet)
            print(f"[SIM] {d_id} | Humidity: {round(data['moisture'], 1)}% | Pump: {'ON' if data['pump_active'] else 'OFF'}")

if __name__ == "__main__":
    # URL of the catalog (localhost because the script runs outside Docker)
    CATALOG_URL = "http://localhost:8080" 
    
    sim = MultiSensorSim("MultiSim_Dinamico", "localhost", 1883, CATALOG_URL)
    sim.startSim()
    
    try:
        while True:
            sim.run_cycle()
            print("-" * 50)
            time.sleep(5) 
    except KeyboardInterrupt:
        sim.stopSim()