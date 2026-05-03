import time
import json
import threading
import sys
from datetime import datetime
from MyMQTT import MyMQTT  

# globals
BROKER_IP = "message-broker"
BROKER_PORT = 1883
SERVICE_ID = "FaultDetectionService"

PUMP_TOPIC = "garden/+/pump"
DATA_TOPIC = "garden/+/telemetry"
ALARM_TOPIC = "garden/alerts/faults"

CHECK_TIMEOUT = 20  # s
MOISTURE_MIN_GAP = 0.8  # %

class FaultDetection:
    def __init__(self):
        self.devices = {}
        self.client = MyMQTT(SERVICE_ID, BROKER_IP, BROKER_PORT, self)
        self.active = True

    def notify(self, topic, payload):
        try:
            data = json.loads(payload)
            t_parts = topic.split("/")
            if len(t_parts) < 2: return
            dev_id = t_parts[1]

            if dev_id not in self.devices:
                self.devices[dev_id] = {
                    "is_pumping": False,
                    "start_t": 0,
                    "start_moist": None,
                    "curr_moist": 0,
                    "is_alarmed": False
                }

            
            if "pump" in topic:
                self._process_pump(dev_id, data)
            elif "telemetry" in topic:
                self._process_data(dev_id, data)

        except Exception as e:
            print(f"[ERR] Parsing error on topic {topic}: {e}")

    def _process_pump(self, dev_id, msg):
        status = msg.get("pump_status")
        if status is None: return
        
        on = int(status) == 1
        dev = self.devices[dev_id]

        if on and not dev["is_pumping"]:
            dev["is_pumping"] = True
            dev["start_t"] = time.time()
            dev["start_moist"] = None
            dev["is_alarmed"] = False
            print(f"[{dev_id}] Pump started. Monitoring moisture...")
        
        elif not on and dev["is_pumping"]:
            dev["is_pumping"] = False
            print(f"[{dev_id}] Pump stopped. Monitor off.")

    def _process_data(self, dev_id, msg):
        moist = msg.get("soil_moisture")
        if moist is None: return
        
        dev = self.devices[dev_id]
        dev["curr_moist"] = moist

        if dev["is_pumping"]:
            # Set baseline if missing
            if dev["start_moist"] is None:
                dev["start_moist"] = moist
                print(f"[{dev_id}] Baseline set at {moist}%")
            
            # Check for faults
            elapsed = time.time() - dev["start_t"]
            diff = moist - dev["start_moist"]

            if elapsed > CHECK_TIMEOUT and not dev["is_alarmed"]:
                if diff < MOISTURE_MIN_GAP:
                    self._send_alert(dev_id, moist, dev["start_moist"])
                    dev["is_alarmed"] = True

    def _send_alert(self, dev_id, now, before):
        alert = {
            "target": dev_id,
            "error": "PUMP_FAILURE_OR_LEAK",
            "val_now": round(now, 2),
            "val_init": round(before, 2),
            "time_iso": datetime.now().isoformat()
        }
        self.client.myPublish(ALARM_TOPIC, alert)
        print(f"!!! ALERT SENT FOR {dev_id} !!!")

    def run(self):
        self.client.start()
        self.client.mySubscribe(PUMP_TOPIC)
        self.client.mySubscribe(DATA_TOPIC)
        print("Fault Detection Engine is running...")
        
        try:
            while self.active:
                time.sleep(1)
        except KeyboardInterrupt:
            self.client.stop()

if __name__ == "__main__":
    manager = FaultDetection()
    manager.run()