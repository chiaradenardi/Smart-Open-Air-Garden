import requests
import time
import random
import json
import paho.mqtt.client as mqtt

# --- CONFIGURAZIONI GLOBALI ---
CATALOG_URL = "http://<IP_DEL_CATALOG>:8080/device_config"
pump_state = "OFF"  # Variabile globale che simula lo stato del nostro attuatore fisico

# --- FUNZIONI DI SIMULAZIONE (Mock) ---
def simulate_sensors(current_moisture):
    """Simula i dati del sensore DHT11 e l'umidità del suolo."""
    temp = round(random.uniform(20.0, 24.0), 1)
    air_humidity = round(random.uniform(40.0, 50.0), 1)
    
    global pump_state
    if pump_state == "ON":
        new_moisture = 100.0  # La pompa innaffia, il terreno si satura
    else:
        new_moisture = max(0.0, current_moisture - 0.5)  # Si asciuga lentamente
        
    return temp, air_humidity, new_moisture

# --- FUNZIONI REST ---
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

# --- CALLBACK MQTT ---
def on_connect(client, userdata, flags, rc):
    """Callback eseguita quando il client si connette al broker."""
    if rc == 0:
        print("[MQTT] Connesso al Message Broker con successo!")
        # Non appena connesso, agisce da Subscriber iscrivendosi al topic dei comandi 
        client.subscribe(userdata['command_topic'])
        print(f"[MQTT] In ascolto dei comandi sul topic: {userdata['command_topic']}")
    else:
        print(f"[MQTT] Errore di connessione. Codice: {rc}")

def on_message(client, userdata, msg):
    """Callback eseguita quando arriva un messaggio su un topic a cui siamo iscritti."""
    global pump_state
    payload = msg.payload.decode('utf-8')
    print(f"\n[MQTT RICEVUTO] Topic: {msg.topic} | Messaggio: {payload}")
    
    # Logica di attuazione: analizza il comando e "accende/spegne" la pompa 
    if "ON" in payload.upper():
        pump_state = "ON"
        print(">>> [ATTUAZIONE FISICA SIMULATA] POMPA ACCESA! L'acqua scorre... <<<")
    elif "OFF" in payload.upper():
        pump_state = "OFF"
        print(">>> [ATTUAZIONE FISICA SIMULATA] POMPA SPENTA! <<<")

# --- FLUSSO PRINCIPALE ---
if __name__ == "__main__":
    # 1. Recupero configurazioni via REST dal Catalog [cite: 42]
    broker_config = None
    while not broker_config:
        broker_config = get_broker_config()
        if not broker_config:
            time.sleep(5)
            
    broker_ip = broker_config.get("broker_ip", "localhost")
    telemetry_topic = broker_config.get("telemetry_topic", "garden/sensors/telemetry")
    command_topic = broker_config.get("command_topic", "garden/actuators/pump")
    
    # 2. Inizializzazione Client MQTT
    client = mqtt.Client(userdata={'command_topic': command_topic})
    client.on_connect = on_connect
    client.on_message = on_message
    
    print(f"[SETUP] Tentativo di connessione al broker MQTT su {broker_ip}...")
    try:
        client.connect(broker_ip, 1883, 60)
    except Exception as e:
        print(f"[ERRORE MQTT] Connessione fallita: {e}")
        exit(1)
        
    # Avvia il loop MQTT in background per gestire ricezione messaggi e ping
    client.loop_start()
    
    # 3. Ciclo Principale: Lettura sensori e Pubblicazione
    soil_moisture = 60.0  # Umidità iniziale
    
    try:
        print("\n[RUN] Avvio ciclo di invio telemetria...")
        while True:
            # Legge i sensori simulati
            temp, air_hum, soil_moisture = simulate_sensors(soil_moisture)
            
            # Prepara il payload in formato JSON
            payload = {
                "temperature": temp,
                "air_humidity": air_hum,
                "soil_moisture": soil_moisture,
                "timestamp": time.time()
            }
            
            # Agisce da Publisher inviando la telemetria 
            client.publish(telemetry_topic, json.dumps(payload))
            print(f"[TELEMETRIA INVIATA] Temp: {temp}°C | Umidità Suolo: {soil_moisture}% | Stato Pompa: {pump_state}")
            
            time.sleep(5)  # Frequenza di campionamento
            
    except KeyboardInterrupt:
        print("\n[STOP] Connettore terminato dall'utente. Disconnessione in corso...")
        client.loop_stop()
        client.disconnect()