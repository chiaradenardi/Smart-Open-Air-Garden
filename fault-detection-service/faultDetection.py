import paho.mqtt.client as mqtt
import json
import time

# --- CONFIGURAZIONE ---
# Se fai girare questo script fuori da Docker usa "localhost", se è dentro Docker usa il nome del servizio (es. "message-broker")
BROKER_IP = "localhost" 
BROKER_PORT = 1883

# Questa è la "memoria" del nostro guardiano. Si ricorderà lo stato di ogni pianta.
# Es: {"RPi_001/": {"pump_on": False, "start_time": 0, "start_moisture": 0.0, "alarmed": False}}
devices = {}

# --- FUNZIONE 1: COSA FARE QUANDO CI SI CONNETTE ---
def on_connect(client, userdata, flags, rc):
    print("Connesso al Broker MQTT con successo!")
    # Iscrizione ai topic definiti nel Contratto API
    client.subscribe("garden/+/telemetry")
    client.subscribe("garden/+/pump")
    print("In ascolto sui topic del giardino...")

# --- FUNZIONE 2: LA LOGICA (IL CUORE DEL PROGRAMMA) ---
def on_message(client, userdata, msg):
    topic = msg.topic
    
    try:
        # Decodifichiamo il messaggio JSON (SenML)
        payload = json.loads(msg.payload.decode('utf-8'))
    except:
        return # Se arriva un messaggio sporco non JSON, lo ignoriamo

    # Analizziamo la lista SenML ricevuta
    for item in payload:
        bn = item.get("bn", "unknown/") # Device ID (es. RPi_001/)
        nome_sensore = item.get("n", "")
        valore = item.get("v", 0)

        # Se è un device nuovo, gli creiamo la sua casella di memoria
        if bn not in devices:
            devices[bn] = {"pump_on": False, "start_time": 0, "start_moisture": None, "alarmed": False}

        # CASO A: E' ARRIVATO UN COMANDO DELLA POMPA
        if "pump" in topic and nome_sensore == "pump_status":
            if valore == 1: # La pompa si è ACCESA
                if not devices[bn]["pump_on"]:
                    devices[bn]["pump_on"] = True
                    devices[bn]["start_time"] = time.time() # Segniamo l'ora esatta
                    devices[bn]["alarmed"] = False          # Resettiamo l'allarme
                    print(f"[{bn}] Pompa ACCESA. Avvio il timer...")
            else: # La pompa si è SPENTA
                devices[bn]["pump_on"] = False
                devices[bn]["start_moisture"] = None
                print(f"[{bn}] Pompa SPENTA. Timer fermato.")

        # CASO B: E' ARRIVATO UN DATO DI UMIDITA'
        elif "telemetry" in topic and nome_sensore == "soil_moisture":
            current_moisture = valore

            # Se la pompa è attualmente accesa, facciamo i controlli di sicurezza!
            if devices[bn]["pump_on"]:
                
                # Salviamo l'umidità di partenza appena la pompa si è accesa
                if devices[bn]["start_moisture"] is None:
                    devices[bn]["start_moisture"] = current_moisture
                    print(f"[{bn}] Umidità iniziale registrata a: {current_moisture}%")

                # Calcoliamo quanti secondi sono passati da quando la pompa è ON
                tempo_trascorso = time.time() - devices[bn]["start_time"]

                # REGOLA DEL PROF: 5 minuti (300 secondi). 
                # SUGGERIMENTO: Per testarlo tu oggi, cambia 300 in 15 (secondi)!!
                LIMITE_SECONDI = 300 

                if tempo_trascorso > LIMITE_SECONDI and not devices[bn]["alarmed"]:
                    # Se l'umidità non è salita di almeno 1 punto percentuale rispetto all'inizio
                    if current_moisture <= devices[bn]["start_moisture"] + 1.0:
                        allarme_msg = f"ALLARME FAULT! Pompa {bn} accesa da troppo tempo senza incremento di umidità."
                        print(f"🚨 {allarme_msg}")
                        
                        # Invia l'allarme al Telegram Bot di Davide
                        client.publish("garden/alarms/fault", allarme_msg)
                        
                        # Segniamo che l'allarme è già suonato per non spammare Telegram ogni secondo
                        devices[bn]["alarmed"] = True 

# --- AVVIO DEL SERVIZIO ---
client = mqtt.Client()
client.on_connect = on_connect
client.on_message = on_message

try:
    # Si connette al broker e gira all'infinito in ascolto
    client.connect(BROKER_IP, BROKER_PORT, 60)
    client.loop_forever()
except KeyboardInterrupt:
    print("Servizio arrestato manualmente.")
except ConnectionRefusedError:
    print("ERRORE: Non riesco a connettermi al Broker. Mosquitto è acceso?")