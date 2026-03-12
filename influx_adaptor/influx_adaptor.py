import json
import requests
import time
from MyMQTT import MyMQTT 
from influxdb_client import InfluxDBClient, Point
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
        # self.broker_ip, self.broker_port = self.get_broker_config()
        
        # TODO STEP 2: Inizializza la tua classe MyMQTT passando 'self' come notifier
        # self.mqtt_client = MyMQTT(...)
        
    def get_broker_config(self):
        # TODO: Fai una requests.get() a self.catalog_url + "/broker" 
        # e restituisci ip e porta. (Puoi copiare la logica che abbiamo usato nel sensore!)
        pass

    def start(self):
        # TODO STEP 2.1: Fai partire il client MQTT
        # TODO STEP 2.2: Iscriviti al topic "garden/#" per ascoltare TUTTO
        pass

    def stop(self):
        # Ferma in modo pulito tutto
        # TODO: Ferma il client MQTT
        self.db_client.close()

    def notify(self, topic, payload):
        # TODO STEP 3: Decodifica il payload da byte a JSON (stringa -> dizionario)
        
        # TODO STEP 4: Formatta il dato per InfluxDB e salvalo
        # Suggerimento: 
        # punto = Point("measurement_name").tag("sensor", "RPi_001").field("temperatura", valore_temp)
        # self.write_api.write(bucket=self.influx_bucket, record=punto)
        
        print(f"[INFLUX SALVATO] Dati dal topic {topic} salvati nel DB!")


if __name__ == "__main__":
    CATALOG_URL = "http://localhost:8080" 
    adaptor = InfluxDBAdaptor("InfluxAdaptor_001", CATALOG_URL)
    
    # adaptor.start()
    
    # while True:
    #     time.sleep(1)