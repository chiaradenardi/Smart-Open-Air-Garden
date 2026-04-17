#!/usr/bin/env python3
"""
Script di Test: Integrazione Telegram Bot + Fault Detection Service
====================================================================
Testa il flusso completo:
1. Accende una pompa (pubblica su garden/RPi_test/pump)
2. Invia dati di umidità stagnanti (pubblica su garden/RPi_test/telemetry)
3. Attende che Fault Detection rilevi il guasto
4. Verifica che Telegram Bot riceva l'allarme su garden/alerts/faults
"""

import paho.mqtt.client as mqtt
import json
import time
import threading
from datetime import datetime

# ============ CONFIGURAZIONE ============
BROKER_IP = "localhost"  # Cambia in "message-broker" se in Docker
BROKER_PORT = 1883
TEST_DEVICE = "RPi_test"

# Topic di test
TOPIC_PUMP = f"garden/{TEST_DEVICE}/pump"
TOPIC_TELEMETRY = f"garden/{TEST_DEVICE}/telemetry"
TOPIC_ALARMS = "garden/alerts/faults"

# ============ VARIABILI GLOBALI ============
alarms_received = []

# ============ CALLBACK MQTT ============
def on_connect(client, userdata, flags, rc):
    """Connessione al broker"""
    if rc == 0:
        print(f"✅ [TEST] Connesso al broker {BROKER_IP}:{BROKER_PORT}")
        # Iscriviti agli allarmi per ricevere le notifiche
        client.subscribe(TOPIC_ALARMS)
        print(f"📡 In ascolto su: {TOPIC_ALARMS}")
    else:
        print(f"❌ Errore connessione: {rc}")

def on_message(client, userdata, msg):
    """Ricevi messaggi MQTT"""
    try:
        payload = msg.payload.decode('utf-8')
        print(f"\n🔔 [ALLARME RICEVUTO] Topic: {msg.topic}")
        print(f"   Payload: {payload}")
        alarms_received.append({
            'topic': msg.topic,
            'payload': payload,
            'time': datetime.now().isoformat()
        })
    except Exception as e:
        print(f"❌ Errore nel parsing messaggio: {e}")

def on_disconnect(client, userdata, rc):
    """Disconnessione"""
    if rc != 0:
        print(f"⚠️  Disconnessione inattesa: {rc}")
    else:
        print(f"✅ Disconnesso correttamente")

# ============ FUNZIONI DI TEST ============
def publish_message(client, topic, payload, delay=0):
    """Pubblica un messaggio MQTT"""
    if delay > 0:
        time.sleep(delay)
    client.publish(topic, json.dumps(payload), qos=1)
    print(f"📤 Pubblicato su {topic}")
    print(f"   Payload: {json.dumps(payload)}")

def test_fault_detection(client):
    """Esegue il test completo"""
    
    print("\n" + "="*70)
    print("🚀 INIZIO TEST: Integrazione Telegram Bot + Fault Detection")
    print("="*70)
    
    try:
        # ===== STEP 1: ACCENDI LA POMPA =====
        print("\n[STEP 1] Accensione pompa in corso...")
        pump_on = [{"n": "pump_status", "v": 1}]
        publish_message(client, TOPIC_PUMP, pump_on, delay=1)
        print("⏱️  Attesa registrazione baseline umidità...")
        time.sleep(2)
        
        # ===== STEP 2: INVIA DATI INIZIALI DI UMIDITÀ =====
        print("\n[STEP 2] Invio baseline umidità (50%)...")
        telemetry_1 = [{"n": "soil_moisture", "v": 50.0}]
        publish_message(client, TOPIC_TELEMETRY, telemetry_1)
        time.sleep(2)
        
        # ===== STEP 3: ATTENDI POMPA TIMEOUT (15 secondi) =====
        print("\n[STEP 3] Invio dati telemetry senza aumento umidità...")
        print("⏱️  Fault Detection attenderà 15 secondi prima di attivare allarme...")
        
        for i in range(3):
            time.sleep(5)
            # Invia umidità ancora a 50% (nessun aumento!)
            telemetry_update = [{"n": "soil_moisture", "v": 50.0}]
            publish_message(client, TOPIC_TELEMETRY, telemetry_update)
            print(f"   [{i+1}/3] Umidità stabile a 50%")
        
        # ===== STEP 4: ATTENDI ALLARMI =====
        print("\n[STEP 4] Attesa allarme dal Fault Detection Service...")
        print(f"⏱️  Attendendo {5} secondi...")
        
        time.sleep(5)
        
        # ===== RESULT =====
        print("\n" + "="*70)
        print("📊 RISULTATI DEL TEST")
        print("="*70)
        
        if len(alarms_received) > 0:
            print(f"✅ SUCCESSO! Allarmi ricevuti: {len(alarms_received)}")
            for i, alarm in enumerate(alarms_received, 1):
                print(f"\n   [{i}] Time: {alarm['time']}")
                print(f"       Topic: {alarm['topic']}")
                print(f"       Payload: {alarm['payload']}")
        else:
            print("❌ NESSUN ALLARME RICEVUTO!")
            print("\n   Possibili cause:")
            print("   1. Fault Detection Service non sta girando")
            print("   2. Il broker MQTT non è raggiungibile")
            print("   3. Configurazione TIMEOUT non corretta")
            print("\n   Azioni da fare:")
            print("   - Verifica che i container Docker siano in esecuzione")
            print("   - Controlla i log del Fault Detection Service")
            print("   - Verifica che PUMP_TIMEOUT_SECONDS < 15 nel config")
        
        # ===== CLEANUP =====
        print("\n[CLEANUP] Spegnimento della pompa...")
        pump_off = [{"n": "pump_status", "v": 0}]
        publish_message(client, TOPIC_PUMP, pump_off)
        time.sleep(1)
        
    except Exception as e:
        print(f"❌ ERRORE durante il test: {e}")
        import traceback
        traceback.print_exc()

# ============ MAIN ============
if __name__ == "__main__":
    # Crea client MQTT - Compatibile con entrambe le versioni di paho-mqtt
    try:
        # Prova con la nuova API (versione > 1.6)
        global_client = mqtt.Client(callback_api_version=mqtt.CallbackAPIVersion.VERSION1, client_id="TestClient")
    except AttributeError:
        # Se fallisce, usa l'API vecchia
        global_client = mqtt.Client(client_id="TestClient")
    
    global_client.on_connect = on_connect
    global_client.on_message = on_message
    global_client.on_disconnect = on_disconnect
    
    try:
        # Connetti al broker
        print(f"🔗 Connessione al broker MQTT in corso ({BROKER_IP}:{BROKER_PORT})...")
        global_client.connect(BROKER_IP, BROKER_PORT, keepalive=60)
        
        # Avvia il loop MQTT in background
        global_client.loop_start()
        time.sleep(1)  # Attendi connessione
        
        # Esegui il test
        test_fault_detection(global_client)
        
        # Attendi e poi disconnetti
        time.sleep(2)
        global_client.loop_stop()
        global_client.disconnect()
        
        print("\n✅ Test completato!")
        
    except ConnectionRefusedError:
        print(f"❌ Impossibile connettersi a {BROKER_IP}:{BROKER_PORT}")
        print("\n   Soluzioni:")
        print("   1. Avvia Docker compose: docker-compose up -d")
        print("   2. Se usi WSL/Docker Desktop, verifica che sia attivo")
        print("   3. Se vuoi testare localmente, installa Mosquitto")
    except KeyboardInterrupt:
        print("\n⚠️  Test interrotto dall'utente")
        global_client.loop_stop()
        global_client.disconnect()
    except Exception as e:
        print(f"❌ Errore critico: {e}")
        import traceback
        traceback.print_exc()
