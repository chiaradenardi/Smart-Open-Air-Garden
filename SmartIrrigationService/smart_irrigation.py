import time
import json
import requests
from MyMQTT import MyMQTT

class SmartIrrigation:
    def __init__(self, clientID, broker, port, catalog_url):
        self.client = MyMQTT(clientID, broker, port, self)
        self.catalog_url = catalog_url
        
        # Dizionario per gestire lo stato della pompa di ogni dispositivo separatamente
        # Esempio: {"RPi_001": True, "RPi_002": False}
        self.pumps_status = {} 
        
        # Dizionario per evitare di interrogare ripetutamente il meteo se abbiamo già deciso di non irrigare
        self.last_weather_check = {} 
        self.weather_cooldown = 900 # Cooldown di 15 minuti in secondi
        
        self.weather_adaptor_url = "http://weather-service-adaptor:8085"
        self.topic_sub = "garden/+/telemetry"

    def start(self):
        self.client.start()
        self.client.mySubscribe(self.topic_sub)
        print(f"--- Smart Irrigation multizona avviata ---")
        print(f"Catalogo: {self.catalog_url}")
        print(f"Meteo: {self.weather_adaptor_url}")

    def notify(self, topic, payload):
        try:
            if isinstance(payload, bytes):
                payload = payload.decode('utf-8')
            msg = json.loads(payload)
            
            # --- MODIFICA QUI: Estrazione umidità dal formato semplice ---
            # msg è un dizionario tipo {"soil_moisture": 60.0, ...}
            current_moisture = None
        
        # Se il messaggio è una lista (SenML)
            if isinstance(msg, list):
                for entry in msg:
                    if entry.get("n") == "soil_moisture":
                        current_moisture = entry.get("v")
                        break
        # Se il messaggio è un dizionario semplice (per compatibilità)
            elif isinstance(msg, dict):
                current_moisture = msg.get("soil_moisture")
            
            if current_moisture is None: 
                return

            # 2. Identificazione del dispositivo (es. RPi_001 o RPi_002)
            device_id = topic.split('/')[1]

            # Skip messages from generic/non-device topics (e.g. garden/sensors/telemetry)
            if not device_id.lower().startswith("rpi"):
                return

            # Initialise pump state for this device on first sight
            if device_id not in self.pumps_status:
                self.pumps_status[device_id] = False

            # 3. Fetch info from Catalog for the specific slot
            # Find which plant is associated with this device_id
            slots_res = requests.get(f"{self.catalog_url}/slots").json()
            
            plant_id = None
            slot_name = "Ignoto"
            for slot in slots_res:
                if slot.get("deviceID") == device_id:
                    plant_id = slot.get("plantID")
                    slot_name = slot.get("slotName", "Zona")
                    break
            
            if not plant_id:
                print(f"[!] {device_id} non associato a nessuna pianta nel catalogo.")
                return

            # Recupero soglia specifica per quella pianta
            strat_res = requests.get(f"{self.catalog_url}/strategies/{plant_id}").json()
            moisture_threshold = strat_res.get("min_moisture_threshold", 40.0)
            plant_name = strat_res.get("name", "Pianta")
            
            # Soglia di stop (20% sopra il minimo)
            target_moisture = moisture_threshold + 20.0

            print(f"[{slot_name} - {device_id}] {plant_name}: {current_moisture}% | Range: {moisture_threshold}%-{target_moisture}%")

            # 4. LOGICA DI CONTROLLO (Indipendente per ogni dispositivo)
            # A. Accensione
            if current_moisture < moisture_threshold:
                if not self.pumps_status[device_id]:
                    # Controlliamo se abbiamo già interrogato il meteo di recente per questo dispositivo
                    now = time.time()
                    last_check = self.last_weather_check.get(device_id, 0)
                    
                    if (now - last_check) < self.weather_cooldown:
                        # Abbiamo controllato da poco e avevamo visto che pioveva. 
                        # Usciamo per non intasarci di richieste meteo continue.
                        return
                    
                    print(f"[{device_id}] Umidità critica. Controllo meteo...")
                    self.last_weather_check[device_id] = now
                    
                    rain_6h = 0
                    try:
                        weather_res = requests.get(self.weather_adaptor_url, timeout=5).json()
                        rain_6h = weather_res.get("total_rain_accumulation_6h", 0)
                        # 2. TRUCCO STRESS TEST: Fingiamo che stia arrivando il diluvio universale! 🌧️
                        # (Così non dobbiamo aspettare che piova davvero a Torino/Modena)
                        #rain_6h = 50.0
                    except Exception as e:
                        print(f"  [!] Errore Meteo: {e}. Procedo con l'irrigazione di sicurezza.")

                    if rain_6h < 2.0:
                        print(f"[{device_id}] Azione: START Irrigazione (Pioggia prevista: {rain_6h}mm)")
                        command_payload = [{
                            "bn": f"{device_id}/",
                            "n": "pump_status",
                            "v": 1, # 1 = ON
                            "u": "on/off",
                            "t": int(time.time())
                        }]
                        self.client.myPublish(f"garden/{device_id}/pump", command_payload)
                        self.pumps_status[device_id] = True
                        
                    else:
                        print(f"[{device_id}] Azione: SKIP (Pioverà tra poco)")

            # B. Spegnimento
            elif current_moisture > target_moisture:
                if self.pumps_status[device_id]:
                    print(f"[{device_id}] Umidità ripristinata. Azione: STOP.")
                    command_payload = [{
                        "bn": f"{device_id}/",
                        "n": "pump_status",
                        "v": 0, # 0 = OFF
                        "u": "on/off",
                        "t": int(time.time())
                    }]
                    self.client.myPublish(f"garden/{device_id}/pump", command_payload)
                    self.pumps_status[device_id] = False
                    
                    # RESET COOLDOWN: Permettiamo di controllare di nuovo il meteo 
                    # al prossimo ciclo, essenziale soprattutto nei test veloci del simulatore!
                    self.last_weather_check[device_id] = 0
        except Exception as e:
            print(f"Errore notify per {topic}: {e}")

if __name__ == "__main__":
    print("Inizializzazione Brain...")
    # NOTA: catalog_url deve essere senza lo slash finale
    brain = SmartIrrigation("IrrigationBrain", "message-broker", 1883, "http://service-catalog:8080")
    brain.start()
    print("Sistema avviato e in ascolto!")
    while True:
        time.sleep(1)