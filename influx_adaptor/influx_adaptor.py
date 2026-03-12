from MyMQTT import*
import time
import json
import cherrypy
import requests

CATALOG_URL = "http://localhost:8080/broker"

def get_broker_config():
    """Contatta il Catalog via REST per ottenere le configurazioni all'avvio[cite: 42]."""
    print("[INIT] Contattando il Service & Resource Catalog via REST...")
    try:
        response = requests.get(CATALOG_URL, timeout=10)
        response.raise_for_status()
        config_data = response.json()
        print(f"[INIT] Configurazione ricevuta: {config_data}")
        return config_data
    except requests.exceptions.RequestException as e:
        print(f"[ERRORE] Impossibile contattare il Catalog. Dettaglio: {e}")
        return None
    
class InfluxAdaptor:
    def __init__(self,clientID,broker,port,topic_sub)
        self.InfluxClientSub=MyMQTT(clientID,broker,port,self)
        self.topic_sub=topic_sub

    def notify(self,topic,payload):
        message_json = json.loads(payload)

    
    def startSim(self):
        self.InfluxClientSub.start()
        self.InfluxClientSub.mySubscribe(self.topic_sub)
    
    def stopSim(self):
        self.InfluxClientSub.unsubscribe()
        self.InfluxClientSub.stop()
    