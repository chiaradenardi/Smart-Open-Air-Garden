import json
import paho.mqtt.client as PahoMQTT

class MyMQTT:
    """This class is a helper to connect to MQTT easily and send/receive messages."""
    def __init__(self, clientID, broker, port, notifier):
        """Sets up the MQTT client with its ID, broker address, and the class that will handle new messages."""
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
        """Prints a message when the connection is successful."""
        print(f'Connected to {self.broker} with result code {rc}')

    def myOnMessageReceived(self, paho_mqtt, userdata, msg):
        """Sends the incoming message to the notifier object so it can be read."""
        self.notifier.notify(msg.topic, msg.payload)

    def myPublish(self, topic, msg):
        """Converts the message to JSON and sends it to a specific topic."""
        self._paho_mqtt.publish(topic, json.dumps(msg), 2)

    def mySubscribe(self, topic):
        """Starts listening for messages on a specific topic."""
        self._paho_mqtt.subscribe(topic, 2)
        self._isSubscriber = True
        self._topic = topic
        print(f'subscribed to {topic}')

    def start(self):
        """Connects to the broker and starts the background loop to listen for messages."""
        self._paho_mqtt.connect(self.broker, self.port)
        self._paho_mqtt.loop_start()

    def unsubscribe(self):
        """Stops listening to the topic we subscribed to."""
        if (self._isSubscriber):
            self._paho_mqtt.unsubscribe(self._topic)

    def stop(self):
        """Stops everything: unsubscribes, stops the loop, and disconnects."""
        if (self._isSubscriber):
            self._paho_mqtt.unsubscribe(self._topic)

        self._paho_mqtt.loop_stop()
        self._paho_mqtt.disconnect()
