import time
import json
import sys
from datetime import datetime
from MyMQTT import MyMQTT

BROKER_IP   = "message-broker"
BROKER_PORT = 1883
SERVICE_ID  = "FaultDetectionService"

PUMP_TOPIC  = "garden/+/+/pump"
DATA_TOPIC  = "garden/+/+/telemetry"
ALARM_TOPIC = "garden/alerts/faults"

CHECK_TIMEOUT    = 20
MOISTURE_MIN_GAP = 0.8


class FaultDetection:
    def __init__(self):
        self.devices = {}
        self.client  = MyMQTT(SERVICE_ID, BROKER_IP, BROKER_PORT, self)
        self.active  = True

    def _key(self, topic):
        parts = topic.split('/')
        if len(parts) < 4:
            return None
        return f"{parts[1]}/{parts[2]}"

    def notify(self, topic, payload):
        try:
            data = json.loads(payload)
            key  = self._key(topic)
            if not key:
                return
            if key not in self.devices:
                self.devices[key] = {
                    "is_pumping": False, "start_t": 0,
                    "start_moist": None, "curr_moist": 0, "is_alarmed": False
                }
            if "pump" in topic:
                self._process_pump(key, data)
            elif "telemetry" in topic:
                self._process_data(key, data)
        except Exception as e:
            print(f"[ERR] {topic}: {e}")

    def _process_pump(self, key, msg):
        status = None
        if isinstance(msg, list):
            for e in msg:
                if e.get("n") == "pump_status":
                    status = e.get("v"); break
        elif isinstance(msg, dict):
            status = msg.get("pump_status")
        if status is None:
            return
        dev = self.devices[key]
        if int(status) == 1 and not dev["is_pumping"]:
            dev.update({"is_pumping": True, "start_t": time.time(), "start_moist": None, "is_alarmed": False})
            print(f"[{key}] Pump started.")
        elif int(status) == 0 and dev["is_pumping"]:
            dev["is_pumping"] = False
            print(f"[{key}] Pump stopped.")

    def _process_data(self, key, msg):
        moist = None
        if isinstance(msg, list):
            for e in msg:
                if e.get("n") == "soil_moisture":
                    moist = e.get("v"); break
        elif isinstance(msg, dict):
            moist = msg.get("soil_moisture")
        if moist is None:
            return
        dev = self.devices[key]
        dev["curr_moist"] = moist
        if dev["is_pumping"]:
            if dev["start_moist"] is None:
                dev["start_moist"] = moist
                print(f"[{key}] Baseline: {moist}%")
            elapsed = time.time() - dev["start_t"]
            if elapsed > CHECK_TIMEOUT and not dev["is_alarmed"]:
                if (moist - dev["start_moist"]) < MOISTURE_MIN_GAP:
                    self._send_alert(key, moist, dev["start_moist"])
                    dev["is_alarmed"] = True

    def _send_alert(self, key, now, before):
        parts = key.split('/')
        alert = {
            "garden_id": parts[0] if len(parts) > 0 else "unknown",
            "slot_id":   parts[1] if len(parts) > 1 else "unknown",
            "error":     "PUMP_FAILURE_OR_LEAK",
            "val_now":   round(now, 2),
            "val_init":  round(before, 2),
            "time_iso":  datetime.now().isoformat()
        }
        self.client.myPublish(ALARM_TOPIC, alert)
        print(f"!!! ALERT FOR {key} !!!")

    def run(self):
        self.client.start()
        self.client.mySubscribe(PUMP_TOPIC)
        self.client.mySubscribe(DATA_TOPIC)
        print("Fault Detection Engine running...")
        try:
            while self.active:
                time.sleep(1)
        except KeyboardInterrupt:
            self.client.stop()


if __name__ == "__main__":
    FaultDetection().run()