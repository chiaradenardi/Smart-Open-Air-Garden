#!/usr/bin/env python3
"""
Fault Detection Service - Smart Garden
========================================
Monitora la correlazione tra accensione della pompa e aumento dell'umidità.
Se la pompa è accesa per 5 minuti ma l'umidità non sale, invia un allarme.

Logica:
- Ascolta MQTT topic: garden/+/pump e garden/+/telemetry
- Quando pompa si accende: attiva timer e registra umidità iniziale
- Se tempo > 5 minuti E umidità non è aumentata: invia allarme
- Pubblica allarmi su: garden/alerts/faults (ascoltato da Telegram_Bot)

Trigger: Loop MQTT continuo + thread di verifica periodico
"""

import time
import json
import threading
import sys
import paho.mqtt.client as mqtt
from datetime import datetime

# ============ CONFIGURAZIONE ============
BROKER_IP = "message-broker"  # Nome del servizio in docker-compose
BROKER_PORT = 1883
CLIENT_ID = "FaultDetectionService"

# Topic MQTT
TOPIC_PUMP = "garden/+/pump"           # In ascolto: comandi pompa
TOPIC_TELEMETRY = "garden/+/telemetry" # In ascolto: dati sensori (umidità)
TOPIC_ALARMS = "garden/alerts/faults"  # In pubblicazione: allarmi

# Configurazione timeout
PUMP_TIMEOUT_SECONDS = 15  # tempo massimo per vedere aumento umidità
MOISTURE_INCREASE_THRESHOLD = 1.0  # Minimo aumento percentuale per considerare ok
PERIODIC_CHECK_INTERVAL = 60  # Controllo periodico ogni 60 secondi


# ============ CLASSE PRINCIPALE ============
class FaultDetection:
    def __init__(self, broker, port, client_id):
        """Inizializza il servizio di fault detection"""
        self.broker = broker
        self.port = port
        self.client_id = client_id
        self.devices = {}  # Stato di ogni dispositivo
        self.check_thread = None
        self.running = True
        
        # Crea il client MQTT
        self.mqtt_client = mqtt.Client(client_id)
        self.mqtt_client.on_connect = self._on_connect
        self.mqtt_client.on_message = self._on_message
        
        print(f"[INIT] Servizio Fault Detection inizializzato")
        print(f"       Broker: {broker}:{port}")
        print(f"       Timeout pompa: {PUMP_TIMEOUT_SECONDS} secondi")
        print(f"       Soglia umidità: +{MOISTURE_INCREASE_THRESHOLD}%")

    def _on_connect(self, client, userdata, flags, rc):
        """Callback di connessione MQTT"""
        if rc == 0:
            print("[MQTT] Connesso al Broker MQTT con successo!")
            # Iscrizione ai topic
            client.subscribe(TOPIC_PUMP)
            client.subscribe(TOPIC_TELEMETRY)
            print(f"[MQTT] Sottoscritto: {TOPIC_PUMP}, {TOPIC_TELEMETRY}")
        else:
            print(f"[MQTT] Errore di connessione: {rc}")

    def _on_message(self, client, userdata, msg):
        """Callback messaggi MQTT ricevuti"""
        try:
            if isinstance(msg.payload, bytes):
                payload = msg.payload.decode('utf-8')
            else:
                payload = msg.payload
            
            msg_data = json.loads(payload)
            timestamp = self._get_timestamp()
            
            # Estrae device_id dal topic (es. RPi_001 da garden/RPi_001/pump)
            parts = msg.topic.split("/")
            if len(parts) < 2:
                return
            device_id = parts[1]
            
            # Crea entry per device se non esiste
            if device_id not in self.devices:
                self.devices[device_id] = {
                    "pump_on": False,
                    "pump_start_time": None,
                    "pump_start_moisture": None,
                    "last_moisture": None,
                    "alarmed": False
                }
                print(f"[NEW_DEVICE] Registrato nuovo dispositivo: {device_id}")
            
            # ===== CASO A: MESSAGGIO DI PUMP =====
            if "pump" in msg.topic:
                self._handle_pump_message(device_id, msg_data, timestamp)
            
            # ===== CASO B: MESSAGGIO DI TELEMETRY (UMIDITÀ) =====
            elif "telemetry" in msg.topic:
                self._handle_telemetry_message(device_id, msg_data, timestamp)
                
        except Exception as e:
            print(f"[ERROR] Errore nel processing messaggio: {e}")
    
    def _handle_pump_message(self, device_id, msg, timestamp):
        """Elabora messaggio di pompa"""
        try:
            # Estrae stato della pompa (formato SenML: lista con v)
            pump_status = None
            if isinstance(msg, list):
                for entry in msg:
                    if entry.get("n") == "pump_status":
                        pump_status = entry.get("v")
                        break
            elif isinstance(msg, dict):
                pump_status = msg.get("pump_status")
            
            if pump_status is None:
                return
            
            # Conversione a booleano
            is_pump_on = int(pump_status) == 1
            device_info = self.devices[device_id]
            
            # ------- POMPA SI È ACCESA -------
            if is_pump_on and not device_info["pump_on"]:
                device_info["pump_on"] = True
                device_info["pump_start_time"] = time.time()
                device_info["pump_start_moisture"] = None  # Verrà registrata al prossimo telemetry
                device_info["alarmed"] = False
                print(f"[{timestamp}] ✅ POMPA ACCESA: {device_id}")
                print(f"           Timer di {PUMP_TIMEOUT_SECONDS}s attivato")
            
            # ------- POMPA SI È SPENTA -------
            elif not is_pump_on and device_info["pump_on"]:
                device_info["pump_on"] = False
                device_info["pump_start_time"] = None
                device_info["pump_start_moisture"] = None
                device_info["alarmed"] = False
                print(f"[{timestamp}] ❌ POMPA SPENTA: {device_id}")
                print(f"           Timer fermato")
                
        except Exception as e:
            print(f"[ERROR] Errore elaborazione pump message: {e}")
    
    def _handle_telemetry_message(self, device_id, msg, timestamp):
        """Elabora messaggio di telemetria (umidità)"""
        try:
            # Estrae valore umidità (formato SenML)
            moisture = None
            if isinstance(msg, list):
                for entry in msg:
                    if entry.get("n") == "soil_moisture":
                        moisture = entry.get("v")
                        break
            elif isinstance(msg, dict):
                moisture = msg.get("soil_moisture")
            
            if moisture is None:
                return
            
            device_info = self.devices[device_id]
            device_info["last_moisture"] = moisture
            
            # Se pompa è accesa, facciamo controlli
            if device_info["pump_on"]:
                # Registra umidità all'inizio (baseline)
                if device_info["pump_start_moisture"] is None:
                    device_info["pump_start_moisture"] = moisture
                    print(f"[{timestamp}] 💧 BASELINE UMIDITÀ: {device_id} = {moisture:.1f}%")
                    return
                
                # Calcola quanto tempo è passato
                elapsed = time.time() - device_info["pump_start_time"]
                
                # Calcola aumento di umidità
                moisture_increase = moisture - device_info["pump_start_moisture"]
                
                print(f"[{timestamp}] 📊 {device_id}: umidità={moisture:.1f}%, " +
                      f"aumento={moisture_increase:.1f}%, tempo={int(elapsed)}s")
                
                # --- CONTROLLO: Timeout raggiunto? ---
                if elapsed > PUMP_TIMEOUT_SECONDS and not device_info["alarmed"]:
                    # Se umidità NON è aumentata abbastanza
                    if moisture_increase <= MOISTURE_INCREASE_THRESHOLD:
                        self._raise_alarm(device_id, moisture, device_info["pump_start_moisture"])
                        device_info["alarmed"] = True
                
        except Exception as e:
            print(f"[ERROR] Errore elaborazione telemetry message: {e}")
    
    def _raise_alarm(self, device_id, current_moisture, start_moisture):
        """
        Invia allarme MQTT quando viene rilevato un guasto
        Formato: JSON con priority alta
        """
        try:
            alarm_message = {
                "device": device_id,
                "type": "pump_fault",
                "severity": "HIGH",
                "description": f"Pompa accesa per {PUMP_TIMEOUT_SECONDS}s ma umidità non aumenta",
                "current_moisture": round(current_moisture, 2),
                "initial_moisture": round(start_moisture, 2),
                "moisture_change": round(current_moisture - start_moisture, 2),
                "timestamp": self._get_timestamp_iso()
            }
            
            # Pubblica allarme su topic che Telegram_Bot ascolta
            self.mqtt_client.publish(TOPIC_ALARMS, json.dumps(alarm_message), qos=2)
            
            print(f"\n🚨 ALLARME FAULT RILEVATO!")
            print(f"   Device: {device_id}")
            print(f"   Motivo: Pompa accesa ma umidità non sale")
            print(f"   Umidità iniziale: {start_moisture:.1f}%")
            print(f"   Umidità attuale: {current_moisture:.1f}%")
            print(f"   Causa possibile: Tubo staccato o rottura pompa")
            print(f"   Allarme inviato a Telegram\n")
            
        except Exception as e:
            print(f"[ERROR] Errore nell'invio dell'allarme: {e}")
    
    def _periodic_check(self):
        """
        Thread di verifica periodica
        Controlla se ci sono timeout scaduti pendenti
        """
        print(f"[THREAD] Avviato thread di verifica periodica ({PERIODIC_CHECK_INTERVAL}s)")
        
        while self.running:
            try:
                time.sleep(PERIODIC_CHECK_INTERVAL)
                current_time = time.time()
                timestamp = self._get_timestamp()
                
                # Controlla ogni device
                for device_id, info in self.devices.items():
                    if (info["pump_on"] and 
                        info["pump_start_time"] is not None and
                        not info["alarmed"]):
                        
                        elapsed = current_time - info["pump_start_time"]
                        
                        # Se timeout raggiunto e umidità non è salita
                        if elapsed > PUMP_TIMEOUT_SECONDS and info["last_moisture"] is not None:
                            if info["pump_start_moisture"] is not None:
                                increase = info["last_moisture"] - info["pump_start_moisture"]
                                
                                if increase <= MOISTURE_INCREASE_THRESHOLD:
                                    self._raise_alarm(
                                        device_id, 
                                        info["last_moisture"],
                                        info["pump_start_moisture"]
                                    )
                                    info["alarmed"] = True
                
            except Exception as e:
                print(f"[ERROR] Errore nel thread di verifica: {e}")
    
    def start(self):
        """Avvia il servizio"""
        # Avvia thread di verifica periodica
        self.check_thread = threading.Thread(target=self._periodic_check, daemon=True)
        self.check_thread.start()
        
        # Connetti al broker MQTT
        self.mqtt_client.connect(self.broker, self.port, keepalive=60)
        
        print("[START] Servizio avviato - In ascolto su MQTT...")
        
        # Mantieni il loop in ascolto
        self.mqtt_client.loop_forever()

    def stop(self):
        """Arresta il servizio"""
        self.running = False
        self.mqtt_client.loop_stop()
        self.mqtt_client.disconnect()
        print("[STOP] Servizio arrestato")
    
    @staticmethod
    def _get_timestamp():
        """Ritorna timestamp leggibile"""
        return datetime.now().strftime("%H:%M:%S")
    
    @staticmethod
    def _get_timestamp_iso():
        """Ritorna timestamp ISO8601"""
        return datetime.now().isoformat()


# ============ MAIN ============
if __name__ == "__main__":
    try:
        print("=" * 60)
        print("FAULT DETECTION SERVICE - Smart Garden")
        print("=" * 60)
        
        fault_detector = FaultDetection(BROKER_IP, BROKER_PORT, CLIENT_ID)
        fault_detector.start()
    
    except KeyboardInterrupt:
        print("\n[INTERRUPT] Arresto del servizio...")
        fault_detector.stop()
        sys.exit(0)
    
    except ConnectionRefusedError:
        print("[ERROR] Impossibile connettersi al broker MQTT")
        print("        Verificare che Mosquitto sia in esecuzione")
        sys.exit(1)
    
    except Exception as e:
        print(f"[ERROR] Errore non previsto: {e}")
        sys.exit(1)
            
        # ===== CASO A: MESSAGGIO DI PUMP =====
        if "pump" in topic:
            self._handle_pump_message(device_id, msg, timestamp)
        
        # ===== CASO B: MESSAGGIO DI TELEMETRY (UMIDITÀ) =====
        elif "telemetry" in topic:
            self._handle_telemetry_message(device_id, msg, timestamp)
            
    except Exception as e:
        print(f"[ERROR] Errore nel processing messaggio: {e}")

    def _handle_pump_message(self, device_id, msg, timestamp):
        """Elabora messaggio di pompa"""
        try:
            # Estrae stato della pompa (formato SenML: lista con v)
            pump_status = None
            if isinstance(msg, list):
                for entry in msg:
                    if entry.get("n") == "pump_status":
                        pump_status = entry.get("v")
                        break
            elif isinstance(msg, dict):
                pump_status = msg.get("pump_status")
            
            if pump_status is None:
                return
            
            # Conversione a booleano
            is_pump_on = int(pump_status) == 1
            device_info = self.devices[device_id]
            
            # ------- POMPA SI È ACCESA -------
            if is_pump_on and not device_info["pump_on"]:
                device_info["pump_on"] = True
                device_info["pump_start_time"] = time.time()
                device_info["pump_start_moisture"] = None  # Verrà registrata al prossimo telemetry
                device_info["alarmed"] = False
                print(f"[{timestamp}] ✅ POMPA ACCESA: {device_id}")
                print(f"           Timer di {PUMP_TIMEOUT_SECONDS}s attivato")
            
            # ------- POMPA SI È SPENTA -------
            elif not is_pump_on and device_info["pump_on"]:
                device_info["pump_on"] = False
                device_info["pump_start_time"] = None
                device_info["pump_start_moisture"] = None
                device_info["alarmed"] = False
                print(f"[{timestamp}] ❌ POMPA SPENTA: {device_id}")
                print(f"           Timer fermato")
                
        except Exception as e:
            print(f"[ERROR] Errore elaborazione pump message: {e}")
    
    def _handle_telemetry_message(self, device_id, msg, timestamp):
        """Elabora messaggio di telemetria (umidità)"""
        try:
            # Estrae valore umidità (formato SenML)
            moisture = None
            if isinstance(msg, list):
                for entry in msg:
                    if entry.get("n") == "soil_moisture":
                        moisture = entry.get("v")
                        break
            elif isinstance(msg, dict):
                moisture = msg.get("soil_moisture")
            
            if moisture is None:
                return
            
            device_info = self.devices[device_id]
            device_info["last_moisture"] = moisture
            
            # Se pompa è accesa, facciamo controlli
            if device_info["pump_on"]:
                # Registra umidità all'inizio (baseline)
                if device_info["pump_start_moisture"] is None:
                    device_info["pump_start_moisture"] = moisture
                    print(f"[{timestamp}] 💧 BASELINE UMIDITÀ: {device_id} = {moisture:.1f}%")
                    return
                
                # Calcola quanto tempo è passato
                elapsed = time.time() - device_info["pump_start_time"]
                
                # Calcola aumento di umidità
                moisture_increase = moisture - device_info["pump_start_moisture"]
                
                print(f"[{timestamp}] 📊 {device_id}: umidità={moisture:.1f}%, " +
                      f"aumento={moisture_increase:.1f}%, tempo={int(elapsed)}s")
                
                # --- CONTROLLO: Timeout raggiunto? ---
                if elapsed > PUMP_TIMEOUT_SECONDS and not device_info["alarmed"]:
                    # Se umidità NON è aumentata abbastanza
                    if moisture_increase <= MOISTURE_INCREASE_THRESHOLD:
                        self._raise_alarm(device_id, moisture, device_info["pump_start_moisture"])
                        device_info["alarmed"] = True
                
        except Exception as e:
            print(f"[ERROR] Errore elaborazione telemetry message: {e}")
    
    def _raise_alarm(self, device_id, current_moisture, start_moisture):
        """
        Invia allarme MQTT quando viene rilevato un guasto
        Formato: SenML con priority alta
        """
        try:
            alarm_message = {
                "device": device_id,
                "type": "pump_fault",
                "severity": "HIGH",
                "description": f"Pompa accesa per {PUMP_TIMEOUT_SECONDS}s ma umidità non aumenta",
                "current_moisture": round(current_moisture, 2),
                "initial_moisture": round(start_moisture, 2),
                "moisture_change": round(current_moisture - start_moisture, 2),
                "timestamp": self._get_timestamp_iso()
            }
            
            # Pubblica allarme su topic che Telegram_Bot ascolta
            self.client.myPublish(TOPIC_ALARMS, alarm_message)
            
            print(f"\n🚨 ALLARME FAULT RILEVATO!")
            print(f"   Device: {device_id}")
            print(f"   Motivo: Pompa accesa ma umidità non sale")
            print(f"   Umidità iniziale: {start_moisture:.1f}%")
            print(f"   Umidità attuale: {current_moisture:.1f}%")
            print(f"   Causa possibile: Tubo staccato o rottura pompa")
            print(f"   Allarme inviato a Telegram\n")
            
        except Exception as e:
            print(f"[ERROR] Errore nell'invio dell'allarme: {e}")
    
    def _periodic_check(self):
        """
        Thread di verifica periodica
        Controlla se ci sono timeout scaduti pendenti
        """
        print(f"[THREAD] Avviato thread di verifica periodica ({PERIODIC_CHECK_INTERVAL}s)")
        
        while self.running:
            try:
                time.sleep(PERIODIC_CHECK_INTERVAL)
                current_time = time.time()
                timestamp = self._get_timestamp()
                
                # Controlla ogni device
                for device_id, info in self.devices.items():
                    if (info["pump_on"] and 
                        info["pump_start_time"] is not None and
                        not info["alarmed"]):
                        
                        elapsed = current_time - info["pump_start_time"]
                        
                        # Se timeout raggiunto e umidità non è salita
                        if elapsed > PUMP_TIMEOUT_SECONDS and info["last_moisture"] is not None:
                            if info["pump_start_moisture"] is not None:
                                increase = info["last_moisture"] - info["pump_start_moisture"]
                                
                                if increase <= MOISTURE_INCREASE_THRESHOLD:
                                    self._raise_alarm(
                                        device_id, 
                                        info["last_moisture"],
                                        info["pump_start_moisture"]
                                    )
                                    info["alarmed"] = True
                
            except Exception as e:
                print(f"[ERROR] Errore nel thread di verifica: {e}")
    
    @staticmethod
    def _get_timestamp():
        """Ritorna timestamp leggibile"""
        return datetime.now().strftime("%H:%M:%S")
    
    @staticmethod
    def _get_timestamp_iso():
        """Ritorna timestamp ISO8601"""
        return datetime.now().isoformat()


# ============ MAIN ============
if __name__ == "__main__":
    try:
        print("=" * 60)
        print("FAULT DETECTION SERVICE - Smart Garden")
        print("=" * 60)
        
        fault_detector = FaultDetection(BROKER_IP, BROKER_PORT, CLIENT_ID)
        fault_detector.start()
        
        # Mantieni il servizio in esecuzione
        while True:
            time.sleep(1)
    
    except KeyboardInterrupt:
        print("\n[INTERRUPT] Arresto del servizio...")
        fault_detector.stop()
        sys.exit(0)
    
    except ConnectionRefusedError:
        print("[ERROR] Impossibile connettersi al broker MQTT")
        print("        Verificare che Mosquitto sia in esecuzione")
        sys.exit(1)
    
    except Exception as e:
        print(f"[ERROR] Errore non previsto: {e}")
        sys.exit(1)