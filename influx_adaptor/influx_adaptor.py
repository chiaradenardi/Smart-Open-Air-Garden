import json
import requests
import time
from MyMQTT import MyMQTT 
from influxdb_client import InfluxDBClient
from influxdb_client.client.write_api import SYNCHRONOUS

class InfluxDBAdaptor:
    def __init__(self, clientID, catalog_url):
        self.clientID = clientID
        self.catalog_url = catalog_url
        
        # --- DATI INFLUXDB (Hardcoded per ora, in futuro potresti prenderli dal Catalogo) ---
        self.influx_url = "http://localhost:8086"
        self.influx_token = "Token_123456789" # Quello che hai messo nel docker-compose
        self.influx_org = "SmartGarden"
        self.influx_bucket = "telemetry_data"
        
        # Inizializza il client di InfluxDB
        self.db_client = InfluxDBClient(url=self.influx_url, token=self.influx_token, org=self.influx_org)
        self.write_api = self.db_client.write_api(write_options=SYNCHRONOUS)
        
        # TODO STEP 1: Richiama una tua funzione per fare una GET al Catalogo

        self.broker_ip, self.broker_port = self.get_broker_config()
        
        # TODO STEP 2: Inizializza la tua classe MyMQTT passando 'self' come notifier
        self.mqtt_client = MyMQTT(clientID,self.broker_ip,self.broker_port,self)
        
    def get_broker_config(self):
        # TODO: Fai una requests.get() a self.catalog_url + "/broker" 
        # e restituisci ip e porta. (Puoi copiare la logica che abbiamo usato nel sensore!)

        print("[INIT] Contattando il Service & Resource Catalog via REST...")
        try:
            response = requests.get(self.catalog_url + "/broker", timeout=10)
            response.raise_for_status()
            config_data = response.json()
            brok=config_data["broker_name"]
            port=config_data["port"]
            tupla_to_send=(brok,port)
            print(f"[INIT] Configurazione ricevuta: {tupla_to_send}")
            return tupla_to_send
        except requests.exceptions.RequestException as e:
            print(f"[ERRORE] Impossibile contattare il Catalog. Dettaglio: {e}")
            return None


    def start(self):
        self.mqtt_client.start()
        self.mqtt_client.mySubscribe("garden/#")
        pass

    def stop(self):
        self.mqtt_client.unsubscribe()
        self.mqtt_client.stop()
        
        self.db_client.close()

    def notify(self, topic, payload):
        senml_data = json.loads(payload.decode('utf-8'))

        #**************************** ESEMPIO senML Format ********************************
        #[
            #{"bn": "RPi_001/", "n": "temperature", "v": 22.5, "u": "Cel", "t": 1678888888},
            #{"n": "soil_moisture", "v": 45.0, "u": "%RH", "t": 1678888888}
        #]
        #**********************************************************************************
  
        device_id = senml_data[0]["bn"].replace("/", "") # Prende "RPi_001"
        
        for misurazione in senml_data:
            if not "v" in misurazione:
                continue # Salta il base name o gestiscilo se ha anche un valore
                
            nome_sensore = misurazione["n"]
            valore = misurazione["v"]
            timestamp = misurazione["t"]
            
            # 3. Crei il dizionario JSON per InfluxDB
            record_json = {
                "measurement": "environmental_data",
                "tags": {
                    "device": device_id,
                    "sensor_type": nome_sensore
                },
                "fields": {
                    "value": float(valore)
                },
                "time": int(timestamp) # Influx ama i timestamp!
            }
            
            # 4. Scrivi passando direttamente il JSON!
            self.write_api.write(bucket=self.influx_bucket, record=record_json)
            
        print(f"[INFLUX] Salvato pacchetto SenML da {device_id}")


if __name__ == "__main__":
    CATALOG_URL = "http://localhost:8080" 
    adaptor = InfluxDBAdaptor("InfluxAdaptor_001", CATALOG_URL)
    
    adaptor.start()
    
    while True:
        time.sleep(1)