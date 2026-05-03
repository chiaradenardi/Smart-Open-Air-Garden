import json
import paho.mqtt.client as PahoMQTT

class MyMQTT:
    def __init__(self, clientID, broker, port, notifier):
        self.broker = broker
        self.port = port
        self.notifier = notifier
        self.clientID = clientID
        self._topic = ""
        self._isSubscriber = False
        self._paho_mqtt = PahoMQTT.Client(clientID, True)
        self._paho_mqtt.on_connect = self.myOnConnect
        self._paho_mqtt.on_message = self.myOnMessageReceived

    def myOnConnect(self, paho_mqtt, userdata, flags, rc):
        print(f'Connected to {self.broker} with result code {rc}')

    def myOnMessageReceived(self, paho_mqtt, userdata, msg):
        self.notifier.notify(msg.topic, msg.payload)

    def myPublish(self, topic, msg):
        self._paho_mqtt.publish(topic, json.dumps(msg), 2)

    def mySubscribe(self, topic):
        self._paho_mqtt.subscribe(topic, 2)
        self._isSubscriber = True
        self._topic = topic
        print(f'subscribed to {topic}')

    def start(self):
        self._paho_mqtt.connect(self.broker, self.port)
        self._paho_mqtt.loop_start()

    def unsubscribe(self):
        if (self._isSubscriber):
            self._paho_mqtt.unsubscribe(self._topic)

    def stop(self):
        if (self._isSubscriber):
            self._paho_mqtt.unsubscribe(self._topic)

        self._paho_mqtt.loop_stop()
        self._paho_mqtt.disconnect()
