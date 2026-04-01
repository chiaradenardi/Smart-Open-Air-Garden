import json
import requests
import time
from MyMQTT import MyMQTT 
from influxdb_client import InfluxDBClient
from influxdb_client.client.write_api import SYNCHRONOUS
from influxdb_client.domain.write_precision import WritePrecision
import cherrypy

class InfluxDBAdaptor:
    def __init__(self, clientID, catalog_url):
        self.clientID = clientID
        self.catalog_url = catalog_url
        
        # --- DATI INFLUXDB (Hardcoded per ora, in futuro potresti prenderli dal Catalogo) ---
        self.influx_url = "http://influxdb:8086"
        self.influx_token = "dOzXCt01RpXm58Zh_Twn57mRkeRttHvtmbJi6FdPdM0kJh4D-7t2ldF2Ni8YeUg8QCXCqShqC6xMn8IViISstA==" # Quello che hai messo nel docker-compose
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
            brok = config_data["broker_name"]
            port = config_data["broker_port"]
            tupla_to_send=(brok,port)
            print(f"[INIT] Configurazione ricevuta: {tupla_to_send}")
            return tupla_to_send
        except requests.exceptions.RequestException as e:
            print(f"!!! ERRORE SCRITTURA INFLUX !!!: {e}")
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
        #******************************************************************************
        # DA COMPLETARE
        #******************************************************************************

        


        msg_string = payload.decode('utf-8')
        print(f"--- MESSAGGIO RICEVUTO --- Topic: {topic} | Contenuto: {msg_string}")
        try:
            senml_data = json.loads(payload.decode('utf-8'))
            # 2. CONTROLLO DI SICUREZZA: Se arriva un dizionario {} invece di una lista [], lo forziamo a diventare una lista
            if isinstance(senml_data, dict):
                senml_data = [senml_data]

            # 3. CONTROLLO DI SICUREZZA: Se è vuoto o non è una lista, ignoralo per non crashare
            if not isinstance(senml_data, list) or len(senml_data) == 0:
                return

            #**************************** ESEMPIO senML Format ********************************
            #[
                #{"bn": "RPi_001/", "n": "temperature", "v": 22.5, "u": "Cel", "t": 1678888888},
                #{"n": "soil_moisture", "v": 45.0, "u": "%RH", "t": 1678888888}
            #]
            #**********************************************************************************
    
            
            device_id = "unknown"
            if "bn" in senml_data[0]:
                device_id = senml_data[0]["bn"].replace("/", "")
            
            for measurement in senml_data:
                if "v" not in measurement:
                    continue # Salta il base name o gestiscilo se ha anche un valore
                    
                sensor_name = measurement["n"]
                value = measurement["v"]
                timestamp = measurement["t"]

                if "pump" in topic:
                    #*************************************************************************
                    #[{"bn": "RPi_001/","n": "pump_status","v": 1,"u": "on/off","t": 1773413500}]
                    #*************************************************************************
                    name_measurement="actuator_activity"
                elif "telemetry" in topic:
                    name_measurement="environmental_data"
                else:
                    # Se non è né pompa né telemetria, saltiamo questo giro e andiamo al prossimo
                    print(f"[DEBUG] Topic ignorato: {topic}")
                    continue

                
                # 3. Crei il dizionario JSON per InfluxDB
                record_json = {
                    "measurement": name_measurement,
                    "tags": {
                        "device": device_id,
                        "sensor_type": sensor_name
                    },
                    "fields": {
                        "value": float(value)
                    },
                    "time": int(timestamp) # Influx ama i timestamp!
                }
                
                # 4. Scrivi passando direttamente il JSON!
                self.write_api.write(bucket=self.influx_bucket, record=record_json, write_precision=WritePrecision.S)
                print("messaggio inviato ad influx")

            print(f"[INFLUX] Salvato pacchetto SenML da {device_id}")

        except Exception as e:
            # Se arriva roba incomprensibile, la ignora silenziosamente!
            print(f"[WARNING] Dati ignorati sul topic {topic}. Formato non supportato.")

class InfluxRESTService:
    exposed=True

    #http://localhost:8081/history?sensor_type=soil_moisture&period=7d
    def __init__(self, db_client):
        self.db_client = db_client

    def GET(self,*uri,**params):
        # 1. Recuperi i parametri dall'URL (es. ?sensor_type=soil_moisture&period=7d)
        sensor_type = params.get("sensor_type", "temperature")
        period = params.get("period", "7d") # default ultimi 7 giorni

        if sensor_type == "pump_status":
            query = f"""
            from(bucket: "telemetry_data")
            |> range(start: -{period})
            |> filter(fn: (r) => r._measurement == "actuator_activity")
            |> filter(fn: (r) => r.sensor_type == "{sensor_type}")
            |> filter(fn: (r) => r._field == "value")
        """
        else:
            # 2. Scrivi la "Flux Query" (la richiesta per il database)
            query = f"""
                from(bucket: "telemetry_data")
                |> range(start: -{period})
                |> filter(fn: (r) => r._measurement == "environmental_data")
                |> filter(fn: (r) => r.sensor_type == "{sensor_type}")
                |> filter(fn: (r) => r._field == "value")
            """
        try:
            # 3. Esegui la query
            tabelle_risultato = self.db_client.query_api().query(org="SmartGarden", query=query)
            
            # --- 4. TRASFORMAZIONE IN JSON ---
            lista_dati = []
            
            # Cicliamo sulle tabelle e poi sulle singole righe (records)
            for tabella in tabelle_risultato:
                for record in tabella.records:
                    # Estraiamo i campi puliti e li mettiamo nel nostro dizionario
                    lista_dati.append({
                        # get_time().isoformat() trasforma l'orario del DB in una stringa di testo standard
                        "time": record.get_time().isoformat(), 
                        "value": record.get_value(),           
                        "device": record.values.get("device"), 
                        "sensor": record.values.get("sensor_type")
                    })
            
            # Diciamo a chi fa la richiesta (es. Node-RED) che gli stiamo mandando un JSON
            cherrypy.response.headers['Content-Type'] = 'application/json'
            
            # Restituiamo la lista convertita in stringa JSON
            return json.dumps(lista_dati).encode('utf-8')
            
        except Exception as e:
            # Se la query fallisce (es. InfluxDB è spento), restituiamo un errore pulito
            cherrypy.response.status = 500
            cherrypy.response.headers['Content-Type'] = 'application/json'
            return json.dumps({"errore": str(e)}).encode('utf-8')

     

        
class CatalogRoot: #empty class which contains all the endpoints
    pass      


if __name__ == "__main__":
    CATALOG_URL = "http://service-catalog:8080" 
    adaptor = InfluxDBAdaptor("InfluxAdaptor_001", CATALOG_URL)
    root = CatalogRoot()
    root.history = InfluxRESTService(adaptor.db_client) 


    conf = {
        '/': {
            'request.dispatch': cherrypy.dispatch.MethodDispatcher(),
            'tools.sessions.on': True
        }
    }
    cherrypy.tree.mount(root, '/', conf)
    cherrypy.config.update({'server.socket_host': '0.0.0.0'})
    cherrypy.config.update({'server.socket_port': 8081}) # Porta 8081 per l'Adaptor!

    adaptor.start()
    print("[RUN] InfluxDB Adaptor avviato. In ascolto su MQTT e REST (Porta 8081)...")
    
    cherrypy.engine.start()
    cherrypy.engine.block()