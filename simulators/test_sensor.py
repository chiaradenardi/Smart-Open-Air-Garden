import time
import json
import random
from MyMQTT import *

class testSensor:
    def __init__(self, clientID,broker,port,topic_publish):
        self.topic_publish=topic_publish
        temp_value = round(random.uniform(20.0, 25.0), 2)
        timestamp = int(time.time())
        moisture_initial_value=80
        self.moisture_value= moisture_initial_value-round(random.uniform(0.5,2.0))
        self.senml_packet = [
            {"bn": "RPi_001/", "n": "temperature", "v": temp_value, "u": "Cel", "t": timestamp},
            {"n": "soil_moisture", "v": self.moisture_value, "u": "%RH", "t": timestamp}
        ]
        self.SensorClient=MyMQTT(clientID,broker,port,None)
    
    def startSim (self):
        self.SensorClient.start()
    
    def stopSim (self):
        self.SensorClient.stop()

    def publish(self):
        new_value = round(random.uniform(20.0, 25.0), 2)
        self.moisture_value= self.moisture_value-round(random.uniform(0.5,2.0))
        if self.moisture_value<=20.0:
            self.moisture_value=80.0
        new_timestamp = int(time.time())
        self.senml_packet[0]["v"] = new_value
        self.senml_packet[0]["t"] = new_timestamp
        self.senml_packet[1]["v"]= self.moisture_value
        self.senml_packet[1]["t"]= new_timestamp
        self.SensorClient.myPublish(self.topic_publish,self.senml_packet)
        print(f"[SIM] Inviato: {new_value}°C al secondo {new_timestamp}")



            
if __name__ == "__main__":
    broker = "test.mosquitto.org"
    port = 1883
    topic = "garden/RPi_001/telemetry"
    client="davidechila02"
    SimSens=testSensor(client,broker,port,topic)
    SimSens.startSim()
    try:
        while True:
            SimSens.publish()
            time.sleep(5) 
            
    except KeyboardInterrupt:
        SimSens.stopSim()

    
