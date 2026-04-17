import telebot
import paho.mqtt.client as mqtt
import requests
import json
import os
from dotenv import load_dotenv # Aggiungi questa libreria

# Questa funzione cerca un file chiamato ".env" nella cartella corrente e lo carica
load_dotenv()

# GLOBAL CONFIGURATION
# 1. Ottieni questo token scrivendo a @BotFather su Telegram
TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN") 
bot = telebot.TeleBot(TELEGRAM_TOKEN)

# IP del Message Broker e del microservizio che riceve la configurazione (es. Smart Irrigation Strategy)
# Read from environment variable set in docker-compose.yml
BROKER_IP = os.getenv("BROKER_IP", "message-broker")
STRATEGY_REST_URL = os.getenv('SLOTS_URL', 'http://service-catalog:8080/slots')
CATALOG_REST_URL = os.getenv('CATALOG_URL', 'http://service-catalog:8080')

# Variabile per salvare l'ID della chat dell'utente (per potergli inviare i messaggi MQTT)
user_chat_id = None 

# --- CALLBACK MQTT (Gestione Notifiche in Ingresso) ---
def on_connect(client, userdata, flags, rc):
    if rc == 0:
        print("[MQTT] Bot connesso al Broker!")
        # Il bot si iscrive ai topic degli allarmi e della pompa
        client.subscribe("garden/alerts/faults")
        client.subscribe("garden/+/pump")
        client.subscribe("garden/statistics/water-saved")
    else:
        print(f"[MQTT] Errore di connessione: {rc}")

def on_message(client, userdata, msg):
    try:
        payload_raw = msg.payload.decode('utf-8')
        print(f"\n[BOT] 📨 Ricevuto su: {msg.topic}")
        
        # 1. Decodifica e formattazione del messaggio
        if "pump" in msg.topic:
            try:
                # Decodifichiamo il SenML (es. [{"v": 1, ...}])
                data = json.loads(payload_raw)
                status = data[0].get("v") # Prende il valore 1 o 0
                stato_testo = "ACCESA ✅" if status == 1 else "SPENTA ❌"
                device = msg.topic.split("/")[1]
                testo = f"💧 *Aggiornamento Pompa*\nDispositivo: `{device}`\nStato: *{stato_testo}*"
            except:
                testo = f"💧 *Aggiornamento Pompa:*\n{payload_raw}"
        
        elif "faults" in msg.topic:
            try:
                # Spacchettiamo il JSON per evitare i problemi di formattazione
                fault_data = json.loads(payload_raw)
                device = fault_data.get("device", "Ignoto")
                desc = fault_data.get("description", "Guasto sconosciuto")
                severity = fault_data.get("severity", "ALTA")
                
                testo = (
                    f"🚨 *ALLARME CRITICO!* 🚨\n\n"
                    f"📟 *Dispositivo:* `{device}`\n"
                    f"⚠️ *Gravità:* {severity}\n"
                    f"📝 *Dettaglio:* {desc}"
                )
            except:
                # Fallback di sicurezza: se non è JSON, lo mettiamo in un blocco di codice sicuro
                testo = f"🚨 *ALLARME CRITICO!*\n```text\n{payload_raw}\n```"
                
        else:
            testo = f"ℹ️ *Notifica Sistema:*\n{payload_raw}"

        # 2. Invio a tutti gli utenti registrati
        users = requests.get(f"{CATALOG_REST_URL}/users", timeout=5).json()
        for u in users:
            chat_id = u.get("telegramChatID")
            if chat_id and len(str(chat_id)) > 5:
                bot.send_message(chat_id, testo, parse_mode="Markdown")
                print(f"[BOT] Notifica inviata a {u['userName']}")

    except Exception as e:
        print(f"[BOT ERROR] Errore in on_message: {e}")

# --- HANDLER TELEGRAM (Gestione Interazione Utente) ---

# --- MENU PRINCIPALE (DASHBOARD) ---

@bot.message_handler(commands=['start'])
def handle_start(message):
    global user_chat_id
    user_chat_id = message.chat.id  # Salviamo l'ID per le notifiche MQTT

    
    benvenuto = (
        "🌱 *Smart Open Air Garden - Pannello di Controllo* 🌱\n\n"
        "Benvenuto nel tuo ecosistema IoT. Da qui puoi monitorare i sensori, "
        "gestire le irrigazioni e tenere sotto controllo i consumi.\n\n"
        "🗺️ *Mappa e Griglia:*\n"
        "📐 `/dimensionigiardino` | 🌱 `/giardino` \n\n"
        "🔧 *Gestione Avanzata (Admin):*\n"
        "➕ `/aggiungislot` | ➖ `/rimuovislot`\n"
        "➕ `/aggiungidevice` | ➖ `/rimuovidevice`\n"
        "➕ `/aggiungipianta` | ➖ `/rimuovipianta`\n"
        "➕ `/aggiungiutente` | ➖ `/rimuoviutente`"
    )
    
    # Creiamo la pulsantiera professionale
    markup = telebot.types.InlineKeyboardMarkup(row_width=2)
    
    # Riga 1: Gestione principale
    btn_coltura = telebot.types.InlineKeyboardButton("🌿 Gestione Colture", callback_data="menu_coltura")
    btn_dispositivi = telebot.types.InlineKeyboardButton("📟 Stato Dispositivi", callback_data="menu_dispositivi")
    markup.add(btn_coltura, btn_dispositivi)
    
    # Riga 2: Dati e Impostazioni
    btn_prezzo = telebot.types.InlineKeyboardButton("💶 Prezzo Acqua", callback_data="menu_prezzo")
    btn_soglie = telebot.types.InlineKeyboardButton("📊 Soglie Irrigazione", callback_data="menu_soglie")
    markup.add(btn_prezzo, btn_soglie)
    
    # Riga 3: Profilo utente (centrato, prende tutta la larghezza)
    btn_profilo = telebot.types.InlineKeyboardButton("👤 Collega Profilo (Ricevi Notifiche)", callback_data="menu_profilo")
    markup.add(btn_profilo)
    
    btn_posizione = telebot.types.InlineKeyboardButton("🌍 Imposta Posizione Meteo", callback_data="menu_posizione")
    markup.add(btn_posizione) # Aggiungiamo il bottone alla fine
    bot.reply_to(message, benvenuto, reply_markup=markup, parse_mode="Markdown")

# --- ROUTER DEL MENU ---
# Questa funzione "ascolta" i click sui bottoni del menu e richiama le funzioni che abbiamo già creato!
@bot.callback_query_handler(func=lambda call: call.data.startswith("menu_"))
def handle_main_menu(call):
    bot.answer_callback_query(call.id) # Rimuove il "caricamento" sul bottone
    
    comando = call.data.split("_")[1]
    
    # In base al bottone cliccato, deviamo il traffico alla funzione corretta
    # passando 'call.message' in modo che la funzione risponda nella chat giusta
    if comando == "coltura":
        handle_coltura(call.message)
    elif comando == "dispositivi":
        handle_dispositivi(call.message)
    elif comando == "prezzo":
        handle_prezzo(call.message)
    elif comando == "soglie":
        handle_soglie(call.message)
    elif comando == "profilo":
        handle_profilo(call.message) # Aggiungi questa riga
    elif comando == "posizione": # AGGIUNGI QUESTE DUE RIGHE
        handle_menu_posizione(call.message)

def handle_menu_posizione(message):
    # Creiamo la tastiera "Reply" (in basso) che ha i permessi per il GPS
    markup = telebot.types.ReplyKeyboardMarkup(resize_keyboard=True, one_time_keyboard=True)
    btn_pos = telebot.types.KeyboardButton("📍 Invia la mia posizione GPS", request_location=True)
    markup.add(btn_pos)
    
    testo = (
        "🌍 *Impostazione Posizione Meteo*\n\n"
        "Premi il pulsante qui sotto per inviare al sistema le tue coordinate GPS esatte.\n\n"
        "💡 _Se il giardino si trova in un'altra città, scrivi semplicemente il comando testuale:_\n"
        "`/citta NomeCitta,IT` (es. `/citta Torino,IT`)"
    )
    bot.send_message(message.chat.id, testo, reply_markup=markup, parse_mode="Markdown")
 

@bot.message_handler(commands=['coltura'])



def handle_coltura(message):
    try:
        # 1. Chiediamo al catalogo la lista AGGIORNATA degli slot
        slots = requests.get(STRATEGY_REST_URL, timeout=5).json()
        
        if not slots:
            bot.send_message(message.chat.id, "Non ci sono slot configurati al momento nel giardino.")
            return

        markup = telebot.types.InlineKeyboardMarkup()
        
        # 2. Creiamo un bottone dinamicamente per ogni slot trovato nel file JSON
        for s in slots:
            slot_id = s.get("slotID")
            slot_name = s.get("slotName", f"Zona {slot_id}")
            
            # Crea il bottone e aggiungilo alla tastiera
            btn = telebot.types.InlineKeyboardButton(f"🌱 {slot_name} ({slot_id})", callback_data=f"slot_{slot_id}")
            markup.add(btn)
        
        bot.send_message(message.chat.id, "Quale slot vuoi aggiornare?", reply_markup=markup)
        
    except Exception as e:
        bot.send_message(message.chat.id, f"❌ Errore nel contattare il Catalogo: {e}")

@bot.callback_query_handler(func=lambda call: call.data.startswith("slot_"))

@bot.callback_query_handler(func=lambda call: call.data.startswith("slot_"))
def handle_slot_selection(call):
    # INVECE di usare lo split che taglia le parole, "cancelliamo" solo la parola "slot_" 
    # Così se arriva "slot_P1_R1", rimane esattamente "P1_R1" intatto!
    selected_slot = call.data.replace("slot_", "")
    
    try:
        strategies = requests.get(f"{CATALOG_REST_URL}/strategies", timeout=5).json()
        
        markup = telebot.types.InlineKeyboardMarkup()
        for plant_id, info in strategies.items():
            btn = telebot.types.InlineKeyboardButton(f"🪴 {info['name']}", callback_data=f"plant_{plant_id}_{selected_slot}")
            markup.add(btn)
            
        bot.send_message(call.message.chat.id, f"Quale coltura per {selected_slot}?", reply_markup=markup)    
    
    except Exception as e:
        bot.send_message(call.message.chat.id, f"❌ Errore nel caricare le piante: {e}")


@bot.callback_query_handler(func=lambda call: call.data.startswith("plant_"))
@bot.callback_query_handler(func=lambda call: call.data.startswith("plant_"))
def handle_crop_selection(call):
    # Esempio di cosa ci arriva: "plant_P3_P1_R1"
    stringa_dati = call.data.replace("plant_", "") # Diventa "P3_P1_R1"
    pezzi = stringa_dati.split("_")
    
    plant_id = pezzi[0] # Prende "P3"
    selected_slot = "_".join(pezzi[1:]) # Prende tutto il resto e lo riunisce (es. "P1_R1")
    
    bot.answer_callback_query(call.id, f"Sto aggiornando il sistema...")
    
    try:
        payload = {
            "slotID": selected_slot,
            "plantID": plant_id
        }
        
        response = requests.put(STRATEGY_REST_URL, json=payload, timeout=5)
        response.raise_for_status()
        
        data_res = response.json()
        if "error" in data_res:
            bot.send_message(call.message.chat.id, f"❌ Errore dal database: {data_res['error']}")
            return
        
        # --- Aggiorniamo la risposta finale ---
        slots_data = requests.get(STRATEGY_REST_URL, timeout=5).json()
        strategies_data = requests.get(f"{CATALOG_REST_URL}/strategies", timeout=5).json()
        
        dettaglio_slot = []
        for slot in slots_data:
            id_pianta = slot.get("plantID")
            nome_pianta = "sconosciuta"
            if id_pianta in strategies_data:
                nome_pianta = strategies_data[id_pianta]["name"]
                
            dettaglio_slot.append(f"nello slot {slot.get('slotID')} hai: {nome_pianta}")
        
        testo_finale = f"✅ Configurazione aggiornata!\n\n{', '.join(dettaglio_slot).capitalize()}."
        bot.send_message(call.message.chat.id, testo_finale)
        
    except Exception as e:
        bot.send_message(call.message.chat.id, f"❌ Errore: {e}")
    


# --- 5. AGGIUNGI E RIMUOVI SLOT ---

# COMANDO: AGGIUNGI SLOT (POST)
@bot.message_handler(commands=['aggiungislot'])
def handle_add_slot(message):
    testo = (
        "🌱 *Aggiungi un nuovo Slot* 🌱\n"
        "Per coltivare una zona, scrivimi la coordinata sulla griglia, l'ID della Pianta e l'ID del Dispositivo separati da virgola:\n\n"
        "`Coordinata, ID Pianta, ID Dispositivo`\n\n"
        "Esempio: *P1_R2, P3, RPi_003*\n"
        "_(Usa /giardino per vedere le coordinate libere)_"
    )
    msg = bot.send_message(message.chat.id, testo, parse_mode="Markdown")
    bot.register_next_step_handler(msg, process_add_slot)

def process_add_slot(message):
    try:
        parts = [x.strip() for x in message.text.split(',')]
        
        if len(parts) != 3:
            bot.send_message(message.chat.id, "❌ Errore di formato. Devi inserire 3 valori separati da virgola.\nEsempio: P1_R2, P3, RPi_003")
            return
            
        slot_id, plant_id, device_id = parts
        slot_id = slot_id.upper() # Forza il maiuscolo per evitare errori (es. p1_r2 diventa P1_R2)
        
        # Validazione della coordinata: deve iniziare con P e contenere _R
        if not slot_id.startswith("P") or "_R" not in slot_id:
            bot.send_message(message.chat.id, "❌ Errore: La coordinata dello slot deve essere nel formato Px_Ry (es. P1_R2). Riprova con /aggiungislot.")
            return
        
        # Chiediamo al catalogo la lista dei device esistenti
        devices_list = requests.get(f"{CATALOG_REST_URL}/devices", timeout=5).json()
        registered_device_ids = [d["deviceID"] for d in devices_list]
        
        if device_id not in registered_device_ids:
            bot.send_message(
                message.chat.id, 
                f"🛑 *Alt!* Il dispositivo `{device_id}` non esiste nel sistema.\n\n"
                f"Devi prima registrare l'hardware usando il comando /aggiungidevice.", 
                parse_mode="Markdown"
            )
            return
        
        # Creazione dello slot
        payload = {
            "slotID": slot_id,
            "plantID": plant_id,
            "deviceID": device_id,
            "slotName": f"Zona {slot_id}", 
            "status": "active"
        }
        
        response = requests.post(STRATEGY_REST_URL, json=payload, timeout=5)
        response.raise_for_status()
        
        data = response.json()
        if "error" in data:
            bot.send_message(message.chat.id, f"❌ Errore dal server: {data['error']}")
        else:
            # Stampiamo il successo e la griglia AGGIORNATA
            bot.send_message(
                message.chat.id, 
                f"✅ *Successo!* Il dispositivo `{device_id}` sta ora irrigando la zona `{slot_id}`.\n\nEcco il tuo giardino aggiornato:\n\n{genera_griglia_testo()}", 
                parse_mode="Markdown"
            )
            
    except Exception as e:
        bot.send_message(message.chat.id, f"❌ Errore di connessione: {e}")
# COMANDO: RIMUOVI SLOT (DELETE)
@bot.message_handler(commands=['rimuovislot'])
def handle_remove_slot(message):
    try:
        # Chiediamo al catalogo quali slot esistono attualmente
        slots = requests.get(STRATEGY_REST_URL, timeout=5).json()
        
        if not slots:
            bot.send_message(message.chat.id, "Non ci sono slot nel giardino al momento!")
            return
            
        markup = telebot.types.InlineKeyboardMarkup()
        for s in slots:
            # Creiamo un bottone rosso per ogni slot trovato
            btn = telebot.types.InlineKeyboardButton(f"🗑️ Elimina {s.get('slotName', s['slotID'])}", callback_data=f"del_slot_{s['slotID']}")
            markup.add(btn)
            
        bot.send_message(message.chat.id, "⚠️ *Attenzione, operazione irreversibile!*\nQuale slot vuoi eliminare dal sistema?", reply_markup=markup, parse_mode="Markdown")
        
    except Exception as e:
        bot.send_message(message.chat.id, f"❌ Errore nel contattare il Catalogo: {e}")

@bot.callback_query_handler(func=lambda call: call.data.startswith("del_slot_"))
def process_del_slot(call):
    # Rimuoviamo l'animazione di caricamento sul bottone
    bot.answer_callback_query(call.id)
    
    # Estraiamo l'ID (es. S1, S2, S3)
    slot_id = call.data.split("_")[2]
    
    try:
        # Facciamo una DELETE passando l'ID direttamente nell'URL (come vuole il tuo endpoint)
        response = requests.delete(f"{STRATEGY_REST_URL}/{slot_id}", timeout=5)
        response.raise_for_status()
        
        data = response.json()
        if "error" in data:
            bot.send_message(call.message.chat.id, f"❌ Impossibile eliminare: {data['error']}")
        else:
            bot.send_message(call.message.chat.id, f"🗑️ Slot `{slot_id}` eliminato definitivamente dal sistema.", parse_mode="Markdown")
            
    except Exception as e:
        bot.send_message(call.message.chat.id, f"❌ Errore di connessione: {e}")

# --- AVVIO DEL SISTEMA ---
# --- GESTIONE PREZZO ACQUA ---
@bot.message_handler(commands=['price'])
def handle_prezzo(message):
    try:
        # 1. Chiediamo il prezzo attuale al catalogo
        response = requests.get(f"{CATALOG_REST_URL}/price", timeout=5)
        response.raise_for_status()
        prezzo_attuale = response.json()
        
        # 2. Creiamo il bottone per modificarlo
        markup = telebot.types.InlineKeyboardMarkup()
        btn_modifica = telebot.types.InlineKeyboardButton("✏️ Modifica Prezzo", callback_data="modifica_prezzo")
        markup.add(btn_modifica)
        
        bot.send_message(message.chat.id, f"💶 Il prezzo attuale dell'acqua è: *{prezzo_attuale} €/m³*", reply_markup=markup, parse_mode="Markdown")
    except Exception as e:
        bot.send_message(message.chat.id, f"❌ Errore nel contattare il Catalogo: {e}")

@bot.callback_query_handler(func=lambda call: call.data == "modifica_prezzo")
def handle_modifica_prezzo(call):
    bot.answer_callback_query(call.id) 
    msg = bot.send_message(call.message.chat.id, "Scrivi il nuovo prezzo dell'acqua (es. 2.5):")
    bot.register_next_step_handler(msg, salva_nuovo_prezzo)

def salva_nuovo_prezzo(message):
    try:
        nuovo_prezzo = float(message.text.replace(',', '.')) 
        payload = {"NewWaterPricePerM3": nuovo_prezzo}
        response = requests.put(f"{CATALOG_REST_URL}/price", json=payload, timeout=5)
        response.raise_for_status()
        bot.send_message(message.chat.id, f"✅ Prezzo aggiornato con successo a *{nuovo_prezzo} €/m³*!", parse_mode="Markdown")
    except ValueError:
        bot.send_message(message.chat.id, "❌ Errore: Inserisci un numero valido (es. 2.5). Riprova usando /prezzo.")
    except Exception as e:
        bot.send_message(message.chat.id, f"❌ Errore: {e}")

# --- GESTIONE DISPOSITIVI ---
@bot.message_handler(commands=['devices'])
def handle_dispositivi(message):
    try:
        # Chiediamo al Catalogo la lista di tutti i dispositivi
        devices = requests.get(f"{CATALOG_REST_URL}/devices", timeout=5).json()
        
        testo = "📟 *Stato Dispositivi IoT*\n\n"
        
        # Iteriamo su ogni dispositivo ricevuto dal JSON
        for d in devices:
            # Scegliamo il pallino verde o rosso in base allo status
            status_icon = "🟢" if d.get('status') == 'active' else "🔴"
            
            testo += f"{status_icon} *{d['deviceName']}* (`{d['deviceID']}`)\n"
            testo += f"  Sensori: {', '.join(d['sensors'])}\n"
            testo += f"  Attuatori: {', '.join(d['actuators'])}\n\n"
            
        bot.send_message(message.chat.id, testo, parse_mode="Markdown")
        
    except Exception as e:
        bot.send_message(message.chat.id, f"❌ Errore nel contattare il Catalogo: {e}")

# --- 6. AGGIUNGI E RIMUOVI DISPOSITIVI (DEVICES) ---

# COMANDO: AGGIUNGI DEVICE (POST)
@bot.message_handler(commands=['aggiungidevice'])
def handle_add_device(message):
    testo = (
        "📟 *Registra un nuovo Dispositivo IoT* 📟\n"
        "Scrivimi l'ID del dispositivo e il Nome, separati da una virgola:\n\n"
        "`ID Dispositivo, Nome Dispositivo`\n\n"
        "Esempio: *RPi_003, GardenGateway_003*"
    )
    msg = bot.send_message(message.chat.id, testo, parse_mode="Markdown")
    bot.register_next_step_handler(msg, process_add_device)

def process_add_device(message):
    try:
        parts = [x.strip() for x in message.text.split(',')]
        
        if len(parts) != 2:
            bot.send_message(message.chat.id, "❌ Errore di formato. Devi inserire 2 valori separati da virgola. Riprova con /aggiungidevice")
            return
            
        device_id, device_name = parts
        
        # Prepariamo un payload completo per il catalogo (aggiungendo i sensori standard di default)
        payload = {
            "deviceID": device_id,
            "deviceName": device_name,
            "status": "active",
            "sensors": ["SoilMoisture", "DHT11"],
            "actuators": ["MicroServoPump"],
            "config": {
                "clientID": f"Client_{device_id}",
                "telemetry_topic": f"garden/{device_id}/telemetry",
                "command_topic": f"garden/{device_id}/pump"
            }
        }
        
        response = requests.post(f"{CATALOG_REST_URL}/devices", json=payload, timeout=5)
        response.raise_for_status()
        
        data = response.json()
        if "error" in data:
            bot.send_message(message.chat.id, f"❌ Errore dal server: {data['error']}")
        else:
            bot.send_message(message.chat.id, f"✅ *Successo!* Il dispositivo `{device_id}` è stato registrato. Ora puoi assegnarlo a uno slot!", parse_mode="Markdown")
            
    except Exception as e:
        bot.send_message(message.chat.id, f"❌ Errore di connessione: {e}")

# COMANDO: RIMUOVI DEVICE (DELETE)
@bot.message_handler(commands=['rimuovidevice'])
def handle_remove_device(message):
    try:
        devices = requests.get(f"{CATALOG_REST_URL}/devices", timeout=5).json()
        
        if not devices:
            bot.send_message(message.chat.id, "Non ci sono dispositivi registrati!")
            return
            
        markup = telebot.types.InlineKeyboardMarkup()
        for d in devices:
            btn = telebot.types.InlineKeyboardButton(f"🗑️ Elimina {d['deviceID']}", callback_data=f"del_dev_{d['deviceID']}")
            markup.add(btn)
            
        bot.send_message(message.chat.id, "⚠️ *Attenzione!* Quale dispositivo vuoi scollegare dal sistema?", reply_markup=markup, parse_mode="Markdown")
        
    except Exception as e:
        bot.send_message(message.chat.id, f"❌ Errore nel contattare il Catalogo: {e}")

@bot.callback_query_handler(func=lambda call: call.data.startswith("del_dev_"))
def process_del_device(call):
    bot.answer_callback_query(call.id)
    device_id = call.data.split("_")[2]
    
    try:
        response = requests.delete(f"{CATALOG_REST_URL}/devices/{device_id}", timeout=5)
        response.raise_for_status()
        
        data = response.json()
        if "error" in data:
            bot.send_message(call.message.chat.id, f"❌ Impossibile eliminare: {data['error']}")
        else:
            bot.send_message(call.message.chat.id, f"🗑️ Dispositivo `{device_id}` rimosso dal database.", parse_mode="Markdown")
            
    except Exception as e:
        bot.send_message(call.message.chat.id, f"❌ Errore di connessione: {e}")
# --- 8. GESTIONE PIANTE / STRATEGIE ---

@bot.message_handler(commands=['aggiungipianta'])
def handle_add_plant(message):
    testo = (
        "🌿 *Aggiungi una nuova Pianta al Catalogo* 🌿\n"
        "Scrivimi i dati separati da virgola in questo formato:\n\n"
        "`ID Pianta, Nome, Soglia Umidità Minima`\n\n"
        "Esempio: *P3, Lattuga, 50.0*"
    )
    msg = bot.send_message(message.chat.id, testo, parse_mode="Markdown")
    bot.register_next_step_handler(msg, process_add_plant)

def process_add_plant(message):
    try:
        parts = [x.strip() for x in message.text.split(',')]
        
        if len(parts) != 3:
            bot.send_message(message.chat.id, "❌ Formato errato. Inserisci 3 valori: ID, Nome, Soglia (es. P3, Lattuga, 50.0). Riprova con /aggiungipianta")
            return
            
        plant_id, name, threshold_str = parts
        
        # Convertiamo la soglia in numero (per evitare che qualcuno scriva lettere)
        try:
            threshold = float(threshold_str)
        except ValueError:
            bot.send_message(message.chat.id, "❌ La soglia deve essere un numero (es. 50.0). Riprova.")
            return

        payload = {
            "plantID": plant_id,
            "name": name,
            "min_moisture_threshold": threshold
        }
        
        response = requests.post(f"{CATALOG_REST_URL}/strategies", json=payload, timeout=5)
        response.raise_for_status()
        
        data = response.json()
        if "error" in data:
            bot.send_message(message.chat.id, f"❌ Errore dal server: {data['error']}")
        else:
            bot.send_message(message.chat.id, f"✅ *Successo!* {name} (`{plant_id}`) aggiunta con soglia {threshold}%.", parse_mode="Markdown")
            
    except Exception as e:
        bot.send_message(message.chat.id, f"❌ Errore di connessione: {e}")

@bot.message_handler(commands=['rimuovipianta'])
def handle_remove_plant(message):
    try:
        strategies = requests.get(f"{CATALOG_REST_URL}/strategies", timeout=5).json()
        
        if not strategies:
            bot.send_message(message.chat.id, "Nessuna pianta nel catalogo!")
            return
            
        markup = telebot.types.InlineKeyboardMarkup()
        for plant_id, info in strategies.items():
            btn = telebot.types.InlineKeyboardButton(f"🗑️ {info['name']}", callback_data=f"del_plant_{plant_id}")
            markup.add(btn)
            
        bot.send_message(message.chat.id, "⚠️ *Quale pianta vuoi eliminare dal catalogo?*\n_Nota: Assicurati che non sia attualmente usata in nessuno slot!_", reply_markup=markup, parse_mode="Markdown")
        
    except Exception as e:
        bot.send_message(message.chat.id, f"❌ Errore nel contattare il Catalogo: {e}")

@bot.callback_query_handler(func=lambda call: call.data.startswith("del_plant_"))
def process_del_plant(call):
    bot.answer_callback_query(call.id)
    plant_id = call.data.split("_")[2]
    
    try:
        response = requests.delete(f"{CATALOG_REST_URL}/strategies/{plant_id}", timeout=5)
        response.raise_for_status()
        
        data = response.json()
        if "error" in data:
            bot.send_message(call.message.chat.id, f"❌ Impossibile eliminare: {data['error']}")
        else:
            bot.send_message(call.message.chat.id, f"🗑️ Pianta `{plant_id}` rimossa dal catalogo.", parse_mode="Markdown")
            
    except Exception as e:
        bot.send_message(call.message.chat.id, f"❌ Errore di connessione: {e}")

# --- VISUALIZZAZIONE SOGLIE STRATEGIE ---
@bot.message_handler(commands=['soglie'])
def handle_soglie(message):
    try:
        # Recuperiamo le strategie dal catalogo
        strategies = requests.get(f"{CATALOG_REST_URL}/strategies", timeout=5).json()
        
        testo = "📊 *Strategie di Irrigazione Attive*\n\n"
        
        # Iteriamo sul dizionario delle strategie
        for plant_id, info in strategies.items():
            testo += f"🌿 *{info['name']}* (`{plant_id}`)\n"
            testo += f"  💧 La pompa si attiva sotto: {info['min_moisture_threshold']}%\n\n"
            
        bot.send_message(message.chat.id, testo, parse_mode="Markdown")
        
    except Exception as e:
        bot.send_message(message.chat.id, f"❌ Errore nel contattare il Catalogo: {e}")

# --- GESTIONE PROFILO E CHAT ID ---
@bot.message_handler(commands=['profilo'])
def handle_profilo(message):
    try:
        # Recuperiamo la lista utenti dal catalogo
        users = requests.get(f"{CATALOG_REST_URL}/users", timeout=5).json()
        
        testo = (
            f"👤 *Il tuo Chat ID Telegram:* `{message.chat.id}`\n\n"
            "Per ricevere le notifiche di emergenza su questo telefono, "
            "seleziona il tuo profilo dalla lista qui sotto:"
        )
        
        markup = telebot.types.InlineKeyboardMarkup()
        for u in users:
            # Creiamo un bottone per ogni utente presente nel file JSON
            btn = telebot.types.InlineKeyboardButton(f"🙋‍♂️ Sono {u['userName']}", callback_data=f"link_user_{u['userID']}")
            markup.add(btn)
            
        bot.send_message(message.chat.id, testo, reply_markup=markup, parse_mode="Markdown")
        
    except Exception as e:
        bot.send_message(message.chat.id, f"❌ Errore nel contattare il Catalogo: {e}")
@bot.callback_query_handler(func=lambda call: call.data.startswith("link_user_"))
def handle_link_user(call):
    # Estraiamo l'ID utente (es. U_001) e il Chat ID attuale
    user_id = call.data.replace("link_user_", "")
    chat_id = call.message.chat.id
    
    bot.answer_callback_query(call.id) 
    
    try:
        # Prepariamo il payload per la PUT degli utenti
        payload = {
            "userID": user_id,
            "telegramChatID": str(chat_id)
        }
        
        response = requests.put(f"{CATALOG_REST_URL}/users", json=payload, timeout=5)
        response.raise_for_status()
        
        bot.send_message(call.message.chat.id, f"✅ Collegamento riuscito!\nIl profilo *{user_id}* è ora associato a questo telefono. Riceverai qui tutti gli allarmi del giardino.", parse_mode="Markdown")
        
    except Exception as e:
        bot.send_message(call.message.chat.id, f"❌ Errore durante il collegamento: {e}")

# --- 9. GESTIONE UTENTI (ADMIN) ---

@bot.message_handler(commands=['aggiungiutente'])
def handle_add_user(message):
    testo = "👤 *Aggiungi un nuovo Utente* 👤\nScrivimi i dati in questo formato:\n`ID Utente, Nome`\nEsempio: *U_003, Luigi*"
    msg = bot.send_message(message.chat.id, testo, parse_mode="Markdown")
    bot.register_next_step_handler(msg, process_add_user)

def process_add_user(message):
    try:
        parts = [x.strip() for x in message.text.split(',')]
        if len(parts) != 2:
            bot.send_message(message.chat.id, "❌ Formato errato. Riprova con /aggiungiutente")
            return
            
        user_id, user_name = parts
        
        # Inizializziamo il telegramChatID vuoto. L'utente lo riempirà poi usando /profilo
        payload = {
            "userID": user_id,
            "userName": user_name,
            "telegramChatID": "" 
        }

        response = requests.post(f"{CATALOG_REST_URL}/users", json=payload, timeout=5)
        response.raise_for_status()
        
        if "error" in response.json():
            bot.send_message(message.chat.id, f"❌ Errore: {response.json()['error']}")
        else:
            bot.send_message(message.chat.id, f"✅ *Successo!* Utente {user_name} creato.\nOra la persona può avviare il bot dal suo telefono e usare il pulsante 'Collega Profilo'.", parse_mode="Markdown")
    except Exception as e:
        bot.send_message(message.chat.id, f"❌ Errore: {e}")

@bot.message_handler(commands=['rimuoviutente'])
def handle_remove_user(message):
    try:
        users = requests.get(f"{CATALOG_REST_URL}/users", timeout=5).json()
        if not users:
            bot.send_message(message.chat.id, "Nessun utente nel sistema!")
            return
            
        markup = telebot.types.InlineKeyboardMarkup()
        for u in users:
            markup.add(telebot.types.InlineKeyboardButton(f"🗑️ Elimina {u['userName']}", callback_data=f"del_user_{u['userID']}"))
            
        bot.send_message(message.chat.id, "⚠️ *Quale utente vuoi eliminare?*", reply_markup=markup, parse_mode="Markdown")
    except Exception as e:
        bot.send_message(message.chat.id, f"❌ Errore: {e}")

@bot.callback_query_handler(func=lambda call: call.data.startswith("del_user_"))
def process_del_user(call):
    bot.answer_callback_query(call.id)
    user_id = call.data.split("_")[2]
    try:
        response = requests.delete(f"{CATALOG_REST_URL}/users/{user_id}", timeout=5)
        response.raise_for_status()
        
        if "error" in response.json():
            bot.send_message(call.message.chat.id, f"❌ Errore: {response.json()['error']}")
        else:
            bot.send_message(call.message.chat.id, f"🗑️ Utente `{user_id}` rimosso dal database.", parse_mode="Markdown")
    except Exception as e:
        bot.send_message(call.message.chat.id, f"❌ Errore: {e}")

# --- 10. GESTIONE POSIZIONE METEO ---

# OPZIONE A: Posizione Testuale (es. /citta Torino,IT)
@bot.message_handler(commands=['citta'])
def handle_citta(message):
    msg = bot.send_message(message.chat.id, "🌍 *Imposta Città Meteo*\nScrivi il nome della città (es. `Torino,IT`) o le coordinate (es. `45.07,7.68`):", parse_mode="Markdown")
    bot.register_next_step_handler(msg, process_citta)

def process_citta(message):
    nuova_posizione = message.text.strip()
    try:
        requests.put(f"{CATALOG_REST_URL}/location", json={"location": nuova_posizione}, timeout=5).raise_for_status()
        bot.send_message(message.chat.id, f"✅ Posizione meteo aggiornata a: *{nuova_posizione}*", parse_mode="Markdown")
    except Exception as e:
        bot.send_message(message.chat.id, f"❌ Errore aggiornamento posizione: {e}")

# OPZIONE B: Posizione GPS con il tasto speciale di Telegram
@bot.message_handler(commands=['posizione'])
def handle_gps_location(message):
    # Creiamo una tastiera "Reply" (quelle in basso) con un bottone speciale nativo di Telegram
    markup = telebot.types.ReplyKeyboardMarkup(resize_keyboard=True, one_time_keyboard=True)
    btn_pos = telebot.types.KeyboardButton("📍 Invia la mia posizione GPS", request_location=True)
    markup.add(btn_pos)
    
    bot.send_message(message.chat.id, "Premi il pulsante qui sotto per inviare le tue coordinate GPS esatte per il servizio Meteo:", reply_markup=markup)

# Questo handler scatta in automatico quando l'utente preme il bottone GPS
@bot.message_handler(content_types=['location'])
def handle_received_location(message):
    lat = message.location.latitude
    lon = message.location.longitude
    nuova_posizione = f"{lat},{lon}"
    
    try:
        requests.put(f"{CATALOG_REST_URL}/location", json={"location": nuova_posizione}, timeout=5).raise_for_status()
        # Rimuoviamo la tastiera speciale e diamo conferma
        bot.send_message(
            message.chat.id, 
            f"✅ Posizione GPS ricevuta e salvata!\nCoordinate: `{nuova_posizione}`\nL'irrigazione ora controllerà il meteo per questa zona.", 
            parse_mode="Markdown", 
            reply_markup=telebot.types.ReplyKeyboardRemove()
        )
    except Exception as e:
        bot.send_message(message.chat.id, f"❌ Errore aggiornamento posizione: {e}")

# --- GESTIONE VISIVA DEL GIARDINO (GRIGLIA) ---


def genera_griglia_testo():
    """Genera la griglia visiva usando le Emoji di Telegram"""
    try:
        grid_data = requests.get(f"{CATALOG_REST_URL}/grid", timeout=5).json()
        slots_data = requests.get(STRATEGY_REST_URL, timeout=5).json()
        
        max_pumps = grid_data.get("max_pumps", 3)
        max_taps = grid_data.get("max_taps", 3)
        
        slot_occupati = [s.get("slotID") for s in slots_data if s.get("status") == "active"]

        # Costruiamo l'intestazione superiore (R1, R2, ecc.)
        griglia_str = "      " # Spazio iniziale per allineare
        for r in range(1, max_taps + 1):
            griglia_str += f"R{r}  "
        griglia_str += "\n"

        # Disegniamo la terra e le piante
        for p in range(1, max_pumps + 1):
            riga = f"*P{p}* " # Mettiamo P1, P2 in grassetto
            for r in range(1, max_taps + 1):
                coordinata = f"P{p}_R{r}"
                
                if coordinata in slot_occupati:
                    riga += "🌱  " # Piantina (Occupato)
                else:
                    riga += "🟫  " # Terra (Libero)
                    
            griglia_str += riga + "\n"

        # Aggiungiamo una piccola legenda in fondo
        legenda = "\n_Legenda:_  🌱 `Occupato`  |  🟫 `Libero`"
        
        # NOTA: Niente più backtick (```), inviamo direttamente il testo formattato!
        return griglia_str + legenda
        
    except Exception as e:
        return f"Errore caricamento griglia: {e}"


# COMANDO: IMPOSTA DIMENSIONI GIARDINO
@bot.message_handler(commands=['dimensionigiardino'])
def handle_set_dimensions(message):
    testo = (
        "📐 *Imposta le dimensioni del Giardino*\n"
        "Scrivi il numero di Filoni (Pompe) e il numero di Rubinetti (Piante) per filone, "
        "separati da una virgola.\n\n"
        "Esempio: *3, 4* (3 Filoni, 4 Piante ciascuno)"
    )
    msg = bot.send_message(message.chat.id, testo, parse_mode="Markdown")
    bot.register_next_step_handler(msg, process_set_dimensions)

def process_set_dimensions(message):
    try:
        parts = [int(x.strip()) for x in message.text.split(',')]
        if len(parts) != 2:
            raise ValueError()
        
        # Invia le nuove dimensioni al Catalogo
        payload = {"max_pumps": parts[0], "max_taps": parts[1]}
        requests.put(f"{CATALOG_REST_URL}/grid", json=payload, timeout=5).raise_for_status()
        
        bot.send_message(
            message.chat.id, 
            f"✅ Dimensioni aggiornate!\nEcco il tuo nuovo giardino:\n{genera_griglia_testo()}", 
            parse_mode="Markdown" 
        )
    except ValueError:
        bot.send_message(message.chat.id, "❌ Formato non valido. Usa solo numeri (es. 3, 4).")
    except Exception as e:
        bot.send_message(message.chat.id, f"❌ Errore aggiornamento DB: {e}")

# COMANDO: VISUALIZZA GIARDINO
@bot.message_handler(commands=['giardino'])
def handle_show_garden(message):
    bot.send_message(
        message.chat.id, 
        f"🌱 *Mappa del tuo Giardino:*\n{genera_griglia_testo()}", 
        parse_mode="Markdown"
    )




if __name__ == "__main__":
    # 1. Setup MQTT in background
    mqtt_client = mqtt.Client()
    mqtt_client.on_connect = on_connect
    mqtt_client.on_message = on_message
    
    try:
        mqtt_client.connect(BROKER_IP, 1883, 60)
        mqtt_client.loop_start() # Avvia MQTT in un thread separato
    except Exception as e:
        print(f"⚠️ Attenzione: Impossibile connettersi al broker MQTT. Il bot si avvierà lo stesso. ({e})")
        
    # 2. Avvio Bot Telegram in primo piano
    print("[BOT] Bot Telegram in ascolto...")
    bot.infinity_polling()