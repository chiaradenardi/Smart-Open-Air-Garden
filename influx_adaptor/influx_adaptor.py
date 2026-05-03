import json
import requests
import time
from MyMQTT import MyMQTT 
from influxdb_client import InfluxDBClient
from influxdb_client.client.write_api import SYNCHRONOUS
from influxdb_client.domain.write_precision import WritePrecision
import cherrypy

# MQTT
class InfluxDBAdaptor:
    def __init__(self, clientID, catalog_url):
        self.clientID = clientID
        self.catalog_url = catalog_url
        
        # influxDB configuration
        self.influx_url = "https://us-east-1-1.aws.cloud2.influxdata.com"
        self.influx_token = "u66UJ0P2mY0WxolaK1-dqhn6Kl70Q1LDuMcsL_28Jej0FnUoiH31VHzpz6O73Z2gNqfakdWYPhOoSd1aVNKdAA==" # Quello che hai messo nel docker-compose
        self.influx_org = "e5fa79d45d607722" 
        self.influx_bucket = "telemetry_data"
        self.db_client = InfluxDBClient(url=self.influx_url, token=self.influx_token, org=self.influx_org)
        self.write_api = self.db_client.write_api(write_options=SYNCHRONOUS)

        # MQTT config fetched from Catalog
        self.broker_ip, self.broker_port = self.get_broker_config()
        self.mqtt_client = MyMQTT(clientID,self.broker_ip,self.broker_port,self)
        
    def get_broker_config(self):
        print("[INIT] Contattando il Service & Resource Catalog via REST...")
        try:
            response = requests.get(self.catalog_url + "/broker", timeout=10)
            response.raise_for_status()
            config_data = response.json()
            broker = config_data["broker_name"]
            port = config_data["broker_port"]
            tupla_to_send=(broker,port)
            print(f"[INIT] Configuration: {tupla_to_send}")
            return tupla_to_send
        except requests.exceptions.RequestException as e:
            print(f"[EXCEPT] Error: {e}")
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
        msg_string = payload.decode('utf-8')
        print(f" Message received on topic: {topic} with payload: {msg_string}")
        try:
            
            senml_data = json.loads(payload.decode('utf-8'))
            if isinstance(senml_data, dict):
                senml_data = [senml_data]
            if not isinstance(senml_data, list) or len(senml_data) == 0:
                return
            
            device_id = "unknown"
            if "bn" in senml_data[0]:
                device_id = senml_data[0]["bn"].replace("/", "")
            
            # iterate over measurements in the SenML package
            for measurement in senml_data:
                if "v" not in measurement:
                    continue 
                    
                sensor_name = measurement["n"]
                value = measurement["v"]
                timestamp = measurement["t"]

                if "pump" in topic:
                    name_measurement="actuator_activity"
                elif "telemetry" in topic:
                    name_measurement="environmental_data"
                else:
                    print(f"[DEBUG] Not matching: {topic}")
                    continue

                
                # create record JSON for InfluxDB
                record_json = {
                    "measurement": name_measurement,
                    "tags": {
                        "device": device_id,
                        "sensor_type": sensor_name
                    },
                    "fields": {
                        "value": float(value)
                    },
                    "time": int(timestamp) 
                }
                
                # write to InfluxDB
                self.write_api.write(bucket=self.influx_bucket, record=record_json, write_precision=WritePrecision.S)
                print("Message written to InfluxDB: " + json.dumps(record_json))

            print(f"[INFLUX] Saved SenML package from {device_id}")

        except Exception as e:
            print(f"[WARNING] Format not supported on topic {topic}. Error: {e}")

# REST API for querying historical data
class InfluxRESTService:
    exposed=True

    def __init__(self, db_client):
        self.db_client = db_client

    def GET(self,*uri,**params):
        sensor_type = params.get("sensor_type", "temperature")
        period = params.get("period", "7d") # default last 7 days

        if sensor_type == "pump_status":
            query = f"""
            from(bucket: "telemetry_data")
            |> range(start: -{period})
            |> filter(fn: (r) => r._measurement == "actuator_activity")
            |> filter(fn: (r) => r.sensor_type == "{sensor_type}")
            |> filter(fn: (r) => r._field == "value")
        """
        else:
            query = f"""
                from(bucket: "telemetry_data")
                |> range(start: -{period})
                |> filter(fn: (r) => r._measurement == "environmental_data")
                |> filter(fn: (r) => r.sensor_type == "{sensor_type}")
                |> filter(fn: (r) => r._field == "value")
            """
        try:
            
            tables= self.db_client.query_api().query(org="e5fa79d45d607722", query=query)
            # tables has to be parsed to extract the records and convert them into a clean JSON format for the response
            output = []
            for table in tables:
                for row in table.records:
                    output.append({
                        "time": row.get_time().isoformat(), 
                        "value": row.get_value(),           
                        "device": row.values.get("device"), 
                        "sensor": row.values.get("sensor_type")
                    })

            cherrypy.response.headers['Content-Type'] = 'application/json'
            return json.dumps(output).encode('utf-8')
            
        except Exception as e:
            cherrypy.response.status = 500
            return json.dumps({"status": "error", "msg": str(e)}).encode('utf-8')

class CatalogRoot: # empty class which contains all the endpoints
    pass      

if __name__ == "__main__":
    CATALOG_URL = "http://service-catalog:8080" 
    adaptor = InfluxDBAdaptor("InfluxAdaptor_001", CATALOG_URL)
    root = CatalogRoot()
    root.history = InfluxRESTService(adaptor.db_client) # history endpoint for querying historical data from InfluxDB


    conf = {
        '/': {
            'request.dispatch': cherrypy.dispatch.MethodDispatcher(),
            'tools.sessions.on': True
        }
    }
    cherrypy.tree.mount(root, '/', conf)
    cherrypy.config.update({'server.socket_host': '0.0.0.0'})
    cherrypy.config.update({'server.socket_port': 8081}) 

    adaptor.start()
    print("[RUN] InfluxDB Adaptor is running...")
    
    cherrypy.engine.start()
    cherrypy.engine.block()