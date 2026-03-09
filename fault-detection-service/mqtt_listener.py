from service_catalog.MyMQTT import MyMQTT

class Notifier:
    def notify(self, topic, payload):
        print(f"Messaggio ricevuto su {topic}: {payload.decode('utf-8')}")

if __name__ == "__main__":
    broker = "127.0.0.1"  # Usa l'indirizzo IP del broker dal catalogo
    port = 1883  # Usa la porta del broker dal catalogo

    notifier = Notifier()
    client = MyMQTT("FaultDetectionClient", broker, port, notifier)

    client.start()
    print("Ciao, sto ascoltando!")

    try:
        while True:
            pass  # Mantieni il programma in esecuzione
    except KeyboardInterrupt:
        print("Interruzione ricevuta, arresto del client MQTT...")
        client.stop()