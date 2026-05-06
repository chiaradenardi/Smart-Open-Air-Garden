
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
STATISTICS_URL = os.getenv('STATISTICS_URL', 'http://statistics-service:8082')

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
        print(f"[MQTT] Connection error: {rc}")

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
                pump_status = "ON ✅" if status == 1 else "OFF ❌"
                device = msg.topic.split("/")[1]
                testo = f"💧 *Pump Update*\nDevice: `{device}`\nStatus: *{pump_status}*"
            except:
                testo = f"💧 *Pump Update:*\n{payload_raw}"
        
        elif "faults" in msg.topic:
            try:
                # Spacchettiamo il JSON per evitare i problemi di formattazione
                fault_data = json.loads(payload_raw)
                device = fault_data.get("device", "Unknown")
                desc = fault_data.get("description", "Unknown fault")
                severity = fault_data.get("severity", "HIGH")
                
                testo = (
                    f"🚨 *CRITICAL ALARM!* 🚨\n\n"
                    f"📟 *Device:* `{device}`\n"
                    f"⚠️ *Severity:* {severity}\n"
                    f"📝 *Details:* {desc}"
                )
            except:
                # Safety fallback: if not JSON, wrap in a code block
                testo = f"🚨 *CRITICAL ALARM!*\n```text\n{payload_raw}\n```"
                
        else:
            testo = f"ℹ️ *System Notification:*\n{payload_raw}"

        # 2. Invio a tutti gli utenti registrati
        users = requests.get(f"{CATALOG_REST_URL}/users", timeout=5).json()
        for u in users:
            chat_id = u.get("telegramChatID")
            if chat_id and len(str(chat_id)) > 5:
                bot.send_message(chat_id, testo, parse_mode="Markdown")
                print(f"[BOT] Notification sent to {u['userName']}")

    except Exception as e:
        print(f"[BOT ERROR] Error in on_message: {e}")

# --- HANDLER TELEGRAM (Gestione Interazione User) ---

# --- MENU PRINCIPALE (DASHBOARD) ---

@bot.message_handler(commands=['start'])
def handle_start(message):
    global user_chat_id
    user_chat_id = message.chat.id  # Salviamo l'ID per le notifiche MQTT

    benvenuto = (
        "🌱 *Smart Open Air Garden - Control Panel* 🌱\n\n"
        "Welcome to your IoT ecosystem. From here you can monitor the sensors, "
        "manage irrigation and monitor your consumption.\n\n"
        "Use the buttons below to navigate the system."
    )
    
    # Creiamo la pulsantiera professionale
    markup = telebot.types.InlineKeyboardMarkup(row_width=2)
    
    # Riga 1: Gestione principale
    btn_coltura = telebot.types.InlineKeyboardButton("🌿 Crop Management", callback_data="menu_coltura")
    btn_dispositivi = telebot.types.InlineKeyboardButton("🖥️ Device Status", callback_data="menu_dispositivi")
    markup.add(btn_coltura, btn_dispositivi)
    
    # Riga 2: Dati e Impostazioni
    btn_prezzo = telebot.types.InlineKeyboardButton("💶 Water Price", callback_data="menu_prezzo")
    btn_soglie = telebot.types.InlineKeyboardButton("📊 Available Crops", callback_data="menu_soglie")
    markup.add(btn_prezzo, btn_soglie)
    
    # Riga 3: Live Status
    btn_status = telebot.types.InlineKeyboardButton("📈 Garden Live Status", callback_data="menu_status")
    markup.add(btn_status)
    
    # Riga 4: Admin e Posizione
    btn_admin = telebot.types.InlineKeyboardButton("🔧 Admin Management", callback_data="menu_admin")
    btn_posizione = telebot.types.InlineKeyboardButton("🌍 Set Weather Location", callback_data="menu_posizione")
    markup.add(btn_admin, btn_posizione)
    
    # Riga 4: Profilo utente (centrato, prende tutta la larghezza)
    btn_profilo = telebot.types.InlineKeyboardButton("👤 Link Profile (Receive Notifications)", callback_data="menu_profilo")
    markup.add(btn_profilo)
    
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
        handle_profilo(call.message)
    elif comando == "posizione":
        handle_menu_posizione(call.message)
    elif comando == "admin":
        handle_admin_panel(call.message)
    elif comando == "status":
        handle_status(call.message)

@bot.message_handler(commands=['status'])
def handle_status(message):
    try:
        # 1. Fetch current slots and their assigned crops + devices
        slots = requests.get(STRATEGY_REST_URL, timeout=5).json()
        strategies = requests.get(f"{CATALOG_REST_URL}/strategies", timeout=5).json()

        # 2. Fetch last soil_moisture readings from InfluxDB (last 10 min window)
        INFLUX_URL = os.getenv("INFLUX_ADAPTOR_URL", "http://influx-adaptor:8081")
        try:
            history = requests.get(
                f"{INFLUX_URL}/history",
                params={"sensor_type": "soil_moisture", "period": "10m"},
                timeout=5
            ).json()
            # Build a dict: device_id -> latest moisture value
            latest_moisture = {}
            for record in history:
                dev = record.get("device", "")
                # Strip trailing slash if present (e.g. "RPi_001/")
                dev = dev.rstrip("/")
                val = record.get("value")
                if dev and val is not None:
                    latest_moisture[dev] = val
        except:
            latest_moisture = {}

        testo = "📈 *Garden Live Status*\n\n"

        if not slots:
            testo += "⚠️ No active slots configured.\n"
        else:
            for s in slots:
                slot_id = s.get("slotID", "?")
                plant_id = s.get("plantID", "")
                device_id = s.get("deviceID", "—")
                plant_name = strategies.get(plant_id, {}).get("name", plant_id) if plant_id else "—"

                # Get last moisture for this device
                moisture_val = latest_moisture.get(device_id)
                if moisture_val is not None:
                    moisture_str = f"`{round(moisture_val, 1)}%`"
                else:
                    moisture_str = "`N/A`"

                testo += f"🌱 *{s.get('slotName', slot_id)}* (`{slot_id}`)\n"
                testo += f"  🖥️ Device: `{device_id}`\n"
                testo += f"  🌿 Crop: *{plant_name}*\n"
                testo += f"  💧 Last soil moisture: {moisture_str}\n\n"

        # 3. Fetch water savings from Statistics Service
        try:
            stats_res = requests.get(f"{STATISTICS_URL}/api/statistics?period=7d", timeout=5).json()
            stats = stats_res.get("statistics", {})
            testo += "💾 *Water Savings (last 7 days)*\n"
            testo += f"  💧 Litres saved: `{stats.get('liters_saved', 'N/A')} L`\n"
            testo += f"  📉 Savings: `{stats.get('savings_percentage', 'N/A')}%`\n"
            testo += f"  🔁 Pump activations: `{stats.get('pump_activations_smart', 'N/A')}`\n"
        except:
            testo += "ℹ️ _Water savings stats temporarily unavailable._\n"

        bot.send_message(message.chat.id, testo, parse_mode="Markdown")

    except Exception as e:
        bot.send_message(message.chat.id, f"❌ Error fetching garden status: {e}")

def handle_admin_panel(message):
    markup = telebot.types.InlineKeyboardMarkup(row_width=2)
    
    # Riga 1: Slot
    markup.add(
        telebot.types.InlineKeyboardButton("➕ Add Slot", callback_data="admin_add_slot"),
        telebot.types.InlineKeyboardButton("➖ Remove Slot", callback_data="admin_rem_slot")
    )
    # Riga 2: Device
    markup.add(
        telebot.types.InlineKeyboardButton("➕ Add Device", callback_data="admin_add_device"),
        telebot.types.InlineKeyboardButton("➖ Remove Device", callback_data="admin_rem_device")
    )
    # Riga 3: Piante
    markup.add(
        telebot.types.InlineKeyboardButton("➕ Add Crop", callback_data="admin_add_plant"),
        telebot.types.InlineKeyboardButton("➖ Remove Crop", callback_data="admin_rem_plant")
    )
    # Riga 4: Utenti
    markup.add(
        telebot.types.InlineKeyboardButton("➕ Add User", callback_data="admin_add_user"),
        telebot.types.InlineKeyboardButton("➖ Remove User", callback_data="admin_rem_user")
    )
    # Riga 5: Dimensioni e Giardino
    markup.add(
        telebot.types.InlineKeyboardButton("📐 Garden Size", callback_data="admin_dimensioni"),
        telebot.types.InlineKeyboardButton("🌱 Show Garden", callback_data="admin_giardino")
    )
    
    testo = "🔧 *Admin Panel*\n\nChoose the operation you wish to perform:"
    bot.send_message(message.chat.id, testo, reply_markup=markup, parse_mode="Markdown")

@bot.callback_query_handler(func=lambda call: call.data.startswith("admin_"))
def handle_admin_callbacks(call):
    bot.answer_callback_query(call.id)
    azione = call.data.replace("admin_", "")
    
    msg = call.message
    
    if azione == "add_slot":
        handle_add_slot(msg)
    elif azione == "rem_slot":
        handle_remove_slot(msg)
    elif azione == "add_device":
        handle_add_device(msg)
    elif azione == "rem_device":
        handle_remove_device(msg)
    elif azione == "add_plant":
        handle_add_plant(msg)
    elif azione == "rem_plant":
        handle_remove_plant(msg)
    elif azione == "add_user":
        handle_add_user(msg)
    elif azione == "rem_user":
        handle_remove_user(msg)
    elif azione == "dimensioni":
        handle_set_dimensions(msg)
    elif azione == "giardino":
        handle_show_garden(msg)

def handle_menu_posizione(message):
    # Create a Reply Keyboard (bottom bar) with native GPS permission button
    markup = telebot.types.ReplyKeyboardMarkup(resize_keyboard=True, one_time_keyboard=True)
    btn_pos = telebot.types.KeyboardButton("📍 Send my GPS location", request_location=True)
    markup.add(btn_pos)
    
    testo = (
        "🌍 *Weather Location Settings*\n\n"
        "Press the button below to send the system your exact GPS coordinates.\n\n"
        "💡 _If the garden is in another city, simply type the command:_\n"
        "`/city CityName,IT` (e.g. `/city Turin,IT`)"
    )
    bot.send_message(message.chat.id, testo, reply_markup=markup, parse_mode="Markdown")
 

@bot.message_handler(commands=['crop'])



def handle_coltura(message):
    try:
        # 1. Chiediamo al catalogo la lista AGGIORNATA degli slot
        slots = requests.get(STRATEGY_REST_URL, timeout=5).json()
        
        if not slots:
            bot.send_message(message.chat.id, "There are no slots configured in the garden at the moment.")
            return

        markup = telebot.types.InlineKeyboardMarkup()
        
        # 2. Creiamo un bottone dinamicamente per ogni slot trovato nel file JSON
        for s in slots:
            slot_id = s.get("slotID")
            slot_name = s.get("slotName", f"Zone {slot_id}")
            
            # Crea il bottone e aggiungilo alla tastiera
            btn = telebot.types.InlineKeyboardButton(f"🌱 {slot_name} ({slot_id})", callback_data=f"slot_{slot_id}")
            markup.add(btn)
        
        bot.send_message(message.chat.id, "Which slot do you want to update?", reply_markup=markup)
        
    except Exception as e:
        bot.send_message(message.chat.id, f"❌ Error contacting the Catalog: {e}")

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
            
        bot.send_message(call.message.chat.id, f"Which crop for slot {selected_slot}?", reply_markup=markup)    
    
    except Exception as e:
        bot.send_message(call.message.chat.id, f"❌ Error loading crops: {e}")


@bot.callback_query_handler(func=lambda call: call.data.startswith("plant_"))
def handle_crop_selection(call):
    # Esempio di cosa ci arriva: "plant_P3_P1_R1"
    stringa_dati = call.data.replace("plant_", "") # Diventa "P3_P1_R1"
    pezzi = stringa_dati.split("_")
    
    plant_id = pezzi[0] # Prende "P3"
    selected_slot = "_".join(pezzi[1:]) # Prende tutto il resto e lo riunisce (es. "P1_R1")
    
    bot.answer_callback_query(call.id, f"Updating the system...")
    
    try:
        payload = {
            "slotID": selected_slot,
            "plantID": plant_id
        }
        
        response = requests.put(STRATEGY_REST_URL, json=payload, timeout=5)
        response.raise_for_status()
        
        data_res = response.json()
        if "error" in data_res:
            bot.send_message(call.message.chat.id, f"❌ Database error: {data_res['error']}")
            return
        
        # --- Aggiorniamo la risposta finale ---
        slots_data = requests.get(STRATEGY_REST_URL, timeout=5).json()
        strategies_data = requests.get(f"{CATALOG_REST_URL}/strategies", timeout=5).json()
        
        dettaglio_slot = []
        for slot in slots_data:
            id_pianta = slot.get("plantID")
            nome_pianta = "unknown"
            if id_pianta in strategies_data:
                nome_pianta = strategies_data[id_pianta]["name"]
                
            dettaglio_slot.append(f"slot {slot.get('slotID')}: {nome_pianta}")
        
        testo_finale = f"✅ Configuration updated!\n\n{', '.join(dettaglio_slot).capitalize()}."
        bot.send_message(call.message.chat.id, testo_finale)
        
    except Exception as e:
        bot.send_message(call.message.chat.id, f"❌ Error: {e}")
    


# --- 5. AGGIUNGI E RIMUOVI SLOT ---

# COMANDO: AGGIUNGI SLOT (POST)
@bot.message_handler(commands=['addslot'])
def handle_add_slot(message):
    testo = (
        "🌱 *Add a new Slot* 🌱\n"
        "To cultivate a zone, type the grid coordinate, the Crop ID and the Device ID separated by commas:\n\n"
        "`Coordinate, Crop ID, Device ID`\n\n"
        "Example: *P1_R2, P3, RPi_003*\n"
        "_(Use /garden to see available coordinates)_"
    )
    msg = bot.send_message(message.chat.id, testo, parse_mode="Markdown")
    bot.register_next_step_handler(msg, process_add_slot)

def process_add_slot(message):
    try:
        parts = [x.strip() for x in message.text.split(',')]
        
        if len(parts) != 3:
            bot.send_message(message.chat.id, "❌ Format error. You must enter 3 comma-separated values.\nExample: P1_R2, P3, RPi_003")
            return
            
        slot_id, plant_id, device_id = parts
        slot_id = slot_id.upper() # Forza il maiuscolo per evitare errori (es. p1_r2 diventa P1_R2)
        
        # Validazione della coordinata: deve iniziare con P e contenere _R
        if not slot_id.startswith("P") or "_R" not in slot_id:
            bot.send_message(message.chat.id, "❌ Error: Slot coordinate must be in Px_Ry format (e.g. P1_R2). Try again with /addslot.")
            return
        
        # Ask the catalog for the existing device list
        devices_list = requests.get(f"{CATALOG_REST_URL}/devices", timeout=5).json()
        registered_device_ids = [d["deviceID"] for d in devices_list]
        
        if device_id not in registered_device_ids:
            bot.send_message(
                message.chat.id, 
                f"🛑 *Stop!* Device `{device_id}` does not exist in the system.\n\n"
                f"You must first register the hardware using the /adddevice command.", 
                parse_mode="Markdown"
            )
            return
        
        # Creazione dello slot
        payload = {
            "slotID": slot_id,
            "plantID": plant_id,
            "deviceID": device_id,
            "slotName": f"Zone {slot_id}", 
            "status": "active"
        }
        
        response = requests.post(STRATEGY_REST_URL, json=payload, timeout=5)
        response.raise_for_status()
        
        data = response.json()
        if "error" in data:
            bot.send_message(message.chat.id, f"❌ Server error: {data['error']}")
        else:
            # Print success and the UPDATED garden grid
            bot.send_message(
                message.chat.id, 
                f"✅ *Success!* Device `{device_id}` is now irrigating zone `{slot_id}`.\n\nHere is your updated garden:\n\n{genera_griglia_testo()}", 
                parse_mode="Markdown"
            )
            
    except Exception as e:
        bot.send_message(message.chat.id, f"❌ Connection error: {e}")
# COMANDO: RIMUOVI SLOT (DELETE)
@bot.message_handler(commands=['removeslot'])
def handle_remove_slot(message):
    try:
        # Chiediamo al catalogo quali slot esistono attualmente
        slots = requests.get(STRATEGY_REST_URL, timeout=5).json()
        
        if not slots:
            bot.send_message(message.chat.id, "There are no slots in the garden at the moment!")
            return
            
        markup = telebot.types.InlineKeyboardMarkup()
        for s in slots:
            # Creiamo un bottone rosso per ogni slot trovato
            btn = telebot.types.InlineKeyboardButton(f"🗑️ Delete {s.get('slotName', s['slotID'])}", callback_data=f"del_slot_{s['slotID']}")
            markup.add(btn)
            
        bot.send_message(message.chat.id, "⚠️ *Warning, irreversible operation!*\nWhich slot do you want to delete from the system?", reply_markup=markup, parse_mode="Markdown")
        
    except Exception as e:
        bot.send_message(message.chat.id, f"❌ Error contacting the Catalog: {e}")

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
            bot.send_message(call.message.chat.id, f"❌ Unable to delete: {data['error']}")
        else:
            bot.send_message(call.message.chat.id, f"🗑️ Slot `{slot_id}` permanently deleted from the system.", parse_mode="Markdown")
            
    except Exception as e:
        bot.send_message(call.message.chat.id, f"❌ Connection error: {e}")

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
        btn_modifica = telebot.types.InlineKeyboardButton("✏️ Edit Price", callback_data="modifica_prezzo")
        markup.add(btn_modifica)
        
        bot.send_message(message.chat.id, f"💶 The current water price is: *{prezzo_attuale} €/m³*", reply_markup=markup, parse_mode="Markdown")
    except Exception as e:
        bot.send_message(message.chat.id, f"❌ Error contacting the Catalog: {e}")

@bot.callback_query_handler(func=lambda call: call.data == "modifica_prezzo")
def handle_modifica_prezzo(call):
    bot.answer_callback_query(call.id) 
    msg = bot.send_message(call.message.chat.id, "Enter the new water price (e.g. 2.5):")
    bot.register_next_step_handler(msg, salva_nuovo_prezzo)

def salva_nuovo_prezzo(message):
    try:
        nuovo_prezzo = float(message.text.replace(',', '.')) 
        payload = {"NewWaterPricePerM3": nuovo_prezzo}
        response = requests.put(f"{CATALOG_REST_URL}/price", json=payload, timeout=5)
        response.raise_for_status()
        bot.send_message(message.chat.id, f"✅ Price successfully updated to *{nuovo_prezzo} €/m³*!", parse_mode="Markdown")
    except ValueError:
        bot.send_message(message.chat.id, "❌ Error: Enter a valid number (e.g. 2.5). Try again using /price.")
    except Exception as e:
        bot.send_message(message.chat.id, f"❌ Error: {e}")

# --- DEVICE MANAGEMENT ---
@bot.message_handler(commands=['devices'])
def handle_dispositivi(message):
    try:
        devices = requests.get(f"{CATALOG_REST_URL}/devices", timeout=5).json()
        slots = requests.get(STRATEGY_REST_URL, timeout=5).json()
        strategies = requests.get(f"{CATALOG_REST_URL}/strategies", timeout=5).json()

        # Build a lookup map: deviceID -> list of assigned slots
        dev_slots = {}
        for s in slots:
            d_id = s.get("deviceID")
            if d_id:
                dev_slots.setdefault(d_id, []).append(s)

        testo = "🖥️ *IoT Device Status*\n\n"
        for d in devices:
            d_id = d['deviceID']
            status_icon = "🟢" if d.get('status') == 'active' else "🔴"
            testo += f"{status_icon} 🖥️ *{d['deviceName']}* (`{d_id}`)\n"
            testo += f"  📡 Sensors: {', '.join(d.get('sensors', []))}\n"
            testo += f"  ⚙️ Actuators: {', '.join(d.get('actuators', []))}\n"

            # Show assigned slots with crop
            assigned = dev_slots.get(d_id, [])
            if assigned:
                for s in assigned:
                    p_id = s.get("plantID")
                    p_name = strategies.get(p_id, {}).get("name", "Unknown") if p_id else "—"
                    testo += f"  📍 Slot: `{s['slotID']}` · 🌿 Crop: *{p_name}*\n"
            else:
                testo += "  📍 Slot: `—` · 🌿 Crop: *No assignment*\n"
            testo += "\n"

        bot.send_message(message.chat.id, testo, parse_mode="Markdown")
    except Exception as e:
        bot.send_message(message.chat.id, f"❌ Error contacting the Catalog: {e}")

# --- 6. AGGIUNGI E RIMUOVI DISPOSITIVI (DEVICES) ---

# COMANDO: AGGIUNGI DEVICE (POST)
@bot.message_handler(commands=['adddevice'])
def handle_add_device(message):
    testo = (
        "📟 *Register a new IoT Device* 📟\n"
        "Type the device ID and Name, separated by a comma:\n\n"
        "`Device ID, Device Name`\n\n"
        "Example: *RPi_003, GardenGateway_003*"
    )
    msg = bot.send_message(message.chat.id, testo, parse_mode="Markdown")
    bot.register_next_step_handler(msg, process_add_device)

def process_add_device(message):
    try:
        parts = [x.strip() for x in message.text.split(',')]
        
        if len(parts) != 2:
            bot.send_message(message.chat.id, "❌ Format error. You must enter 2 comma-separated values. Try again with /adddevice")
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
            bot.send_message(message.chat.id, f"❌ Server error: {data['error']}")
        else:
            bot.send_message(message.chat.id, f"✅ *Success!* Device `{device_id}` has been registered. You can now assign it to a slot!", parse_mode="Markdown")
            
    except Exception as e:
        bot.send_message(message.chat.id, f"❌ Connection error: {e}")

# COMANDO: RIMUOVI DEVICE (DELETE)
@bot.message_handler(commands=['removedevice'])
def handle_remove_device(message):
    try:
        devices = requests.get(f"{CATALOG_REST_URL}/devices", timeout=5).json()
        
        if not devices:
            bot.send_message(message.chat.id, "No devices registered!")
            return
            
        markup = telebot.types.InlineKeyboardMarkup()
        for d in devices:
            btn = telebot.types.InlineKeyboardButton(f"🗑️ Delete {d['deviceID']}", callback_data=f"del_dev_{d['deviceID']}")
            markup.add(btn)
            
        bot.send_message(message.chat.id, "⚠️ *Warning!* Which device do you want to disconnect from the system?", reply_markup=markup, parse_mode="Markdown")
        
    except Exception as e:
        bot.send_message(message.chat.id, f"❌ Error contacting the Catalog: {e}")

@bot.callback_query_handler(func=lambda call: call.data.startswith("del_dev_"))
def process_del_device(call):
    bot.answer_callback_query(call.id)
    device_id = call.data.split("_")[2]
    
    try:
        response = requests.delete(f"{CATALOG_REST_URL}/devices/{device_id}", timeout=5)
        response.raise_for_status()
        
        data = response.json()
        if "error" in data:
            bot.send_message(call.message.chat.id, f"❌ Unable to delete: {data['error']}")
        else:
            bot.send_message(call.message.chat.id, f"🗑️ Device `{device_id}` removed from the database.", parse_mode="Markdown")
            
    except Exception as e:
        bot.send_message(call.message.chat.id, f"❌ Connection error: {e}")
# --- 8. GESTIONE PIANTE / STRATEGIE ---

@bot.message_handler(commands=['addplant'])
def handle_add_plant(message):
    testo = (
        "🌿 *Add a new Crop to the Catalog* 🌿\n"
        "Type the data separated by commas in this format:\n\n"
        "`Crop ID, Name, Minimum Moisture Threshold`\n\n"
        "Example: *P3, Lettuce, 50.0*"
    )
    msg = bot.send_message(message.chat.id, testo, parse_mode="Markdown")
    bot.register_next_step_handler(msg, process_add_plant)

def process_add_plant(message):
    try:
        parts = [x.strip() for x in message.text.split(',')]
        
        if len(parts) != 3:
            bot.send_message(message.chat.id, "❌ Incorrect format. Enter 3 values: ID, Name, Threshold (e.g. P3, Lettuce, 50.0). Try again with /addplant")
            return
            
        plant_id, name, threshold_str = parts
        
        # Convertiamo la soglia in numero (per evitare che qualcuno scriva lettere)
        try:
            threshold = float(threshold_str)
        except ValueError:
            bot.send_message(message.chat.id, "❌ The threshold must be a number (e.g. 50.0). Try again.")
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
            bot.send_message(message.chat.id, f"❌ Server error: {data['error']}")
        else:
            bot.send_message(message.chat.id, f"✅ *Success!* {name} (`{plant_id}`) added with threshold {threshold}%.", parse_mode="Markdown")
            
    except Exception as e:
        bot.send_message(message.chat.id, f"❌ Connection error: {e}")

@bot.message_handler(commands=['removeplant'])
def handle_remove_plant(message):
    try:
        strategies = requests.get(f"{CATALOG_REST_URL}/strategies", timeout=5).json()
        
        if not strategies:
            bot.send_message(message.chat.id, "No crops in the catalog!")
            return
            
        markup = telebot.types.InlineKeyboardMarkup()
        for plant_id, info in strategies.items():
            btn = telebot.types.InlineKeyboardButton(f"🗑️ {info['name']}", callback_data=f"del_plant_{plant_id}")
            markup.add(btn)
            
        bot.send_message(message.chat.id, "⚠️ *Which crop do you want to delete from the catalog?*\n_Note: Make sure it is not currently used in any slot!_", reply_markup=markup, parse_mode="Markdown")
        
    except Exception as e:
        bot.send_message(message.chat.id, f"❌ Error contacting the Catalog: {e}")

@bot.callback_query_handler(func=lambda call: call.data.startswith("del_plant_"))
def process_del_plant(call):
    bot.answer_callback_query(call.id)
    plant_id = call.data.split("_")[2]
    
    try:
        response = requests.delete(f"{CATALOG_REST_URL}/strategies/{plant_id}", timeout=5)
        response.raise_for_status()
        
        data = response.json()
        if "error" in data:
            bot.send_message(call.message.chat.id, f"❌ Unable to delete: {data['error']}")
        else:
            bot.send_message(call.message.chat.id, f"🗑️ Crop `{plant_id}` removed from the catalog.", parse_mode="Markdown")
            
    except Exception as e:
        bot.send_message(call.message.chat.id, f"❌ Connection error: {e}")

# --- VISUALIZZAZIONE SOGLIE STRATEGIE ---
@bot.message_handler(commands=['thresholds'])
def handle_soglie(message):
    try:
        # Retrieve strategies from catalog
        strategies = requests.get(f"{CATALOG_REST_URL}/strategies", timeout=5).json()
        
        testo = "📊 *Available Crops & Irrigation Thresholds*\n\n"
        
        # Iterate over the strategies dictionary
        for plant_id, info in strategies.items():
            testo += f"🌿 *{info['name']}* (`{plant_id}`)\n"
            testo += f"  💧 Pump activates below: {info['min_moisture_threshold']}%\n\n"
            
        bot.send_message(message.chat.id, testo, parse_mode="Markdown")
        
    except Exception as e:
        bot.send_message(message.chat.id, f"❌ Error contacting the Catalog: {e}")

# --- GESTIONE PROFILO E CHAT ID ---
@bot.message_handler(commands=['profile'])
def handle_profilo(message):
    try:
        # Recuperiamo la lista utenti dal catalogo
        users = requests.get(f"{CATALOG_REST_URL}/users", timeout=5).json()
        
        testo = (
            f"👤 *Your Telegram Chat ID:* `{message.chat.id}`\n\n"
            "To receive emergency notifications on this phone, "
            "select your profile from the list below:"
        )
        
        markup = telebot.types.InlineKeyboardMarkup()
        for u in users:
            # Creiamo un bottone per ogni utente presente nel file JSON
            btn = telebot.types.InlineKeyboardButton(f"🙋‍♂️ I am {u['userName']}", callback_data=f"link_user_{u['userID']}")
            markup.add(btn)
            
        bot.send_message(message.chat.id, testo, reply_markup=markup, parse_mode="Markdown")
        
    except Exception as e:
        bot.send_message(message.chat.id, f"❌ Error contacting the Catalog: {e}")
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
        
        bot.send_message(call.message.chat.id, f"✅ Linking successful!\nThe profile *{user_id}* is now associated with this phone. You will receive all garden alarms here.", parse_mode="Markdown")
        
    except Exception as e:
        bot.send_message(call.message.chat.id, f"❌ Error during linking: {e}")

# --- 9. GESTIONE UTENTI (ADMIN) ---

@bot.message_handler(commands=['adduser'])
def handle_add_user(message):
    testo = "👤 *Add a new User* 👤\nType the data in this format:\n`User ID, Name`\nExample: *U_003, Luigi*"
    msg = bot.send_message(message.chat.id, testo, parse_mode="Markdown")
    bot.register_next_step_handler(msg, process_add_user)

def process_add_user(message):
    try:
        parts = [x.strip() for x in message.text.split(',')]
        if len(parts) != 2:
            bot.send_message(message.chat.id, "❌ Incorrect format. Try again with /adduser")
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
            bot.send_message(message.chat.id, f"❌ Error: {response.json()['error']}")
        else:
            bot.send_message(message.chat.id, f"✅ *Success!* User {user_name} created.\nThe person can now start the bot from their phone and use the 'Link Profile (Receive Notifications)' button.", parse_mode="Markdown")
    except Exception as e:
        bot.send_message(message.chat.id, f"❌ Error: {e}")

@bot.message_handler(commands=['removeuser'])
def handle_remove_user(message):
    try:
        users = requests.get(f"{CATALOG_REST_URL}/users", timeout=5).json()
        if not users:
            bot.send_message(message.chat.id, "No users in the system!")
            return
            
        markup = telebot.types.InlineKeyboardMarkup()
        for u in users:
            markup.add(telebot.types.InlineKeyboardButton(f"🗑️ Delete {u['userName']}", callback_data=f"del_user_{u['userID']}"))
            
        bot.send_message(message.chat.id, "⚠️ *Which user do you want to delete?*", reply_markup=markup, parse_mode="Markdown")
    except Exception as e:
        bot.send_message(message.chat.id, f"❌ Error: {e}")

@bot.callback_query_handler(func=lambda call: call.data.startswith("del_user_"))
def process_del_user(call):
    bot.answer_callback_query(call.id)
    user_id = call.data.split("_")[2]
    try:
        response = requests.delete(f"{CATALOG_REST_URL}/users/{user_id}", timeout=5)
        response.raise_for_status()
        
        if "error" in response.json():
            bot.send_message(call.message.chat.id, f"❌ Error: {response.json()['error']}")
        else:
            bot.send_message(call.message.chat.id, f"🗑️ User `{user_id}` removed from the database.", parse_mode="Markdown")
    except Exception as e:
        bot.send_message(call.message.chat.id, f"❌ Error: {e}")

# --- 10. GESTIONE POSIZIONE METEO ---

# OPZIONE A: Posizione Testuale (es. /citta Torino,IT)
@bot.message_handler(commands=['city'])
def handle_citta(message):
    msg = bot.send_message(message.chat.id, "🌍 *Set Weather City*\nEnter the city name (e.g. `Turin,IT`) or coordinates (e.g. `45.07,7.68`):", parse_mode="Markdown")
    bot.register_next_step_handler(msg, process_citta)

def process_citta(message):
    nuova_posizione = message.text.strip()
    try:
        requests.put(f"{CATALOG_REST_URL}/location", json={"location": nuova_posizione}, timeout=5).raise_for_status()
        bot.send_message(message.chat.id, f"✅ Weather location updated to: *{nuova_posizione}*", parse_mode="Markdown")
    except Exception as e:
        bot.send_message(message.chat.id, f"❌ Error updating location: {e}")

# OPZIONE B: Posizione GPS con il tasto speciale di Telegram
@bot.message_handler(commands=['location'])
def handle_gps_location(message):
    # Creiamo una tastiera "Reply" (quelle in basso) con un bottone speciale nativo di Telegram
    markup = telebot.types.ReplyKeyboardMarkup(resize_keyboard=True, one_time_keyboard=True)
    btn_pos = telebot.types.KeyboardButton("📍 Send my GPS location", request_location=True)
    markup.add(btn_pos)
    
    bot.send_message(message.chat.id, "Press the button below to send your exact GPS coordinates for the Weather service:", reply_markup=markup)

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
            f"✅ GPS Location received and saved!\nCoordinates: `{nuova_posizione}`\nThe irrigation system will now check the weather for this zone.", 
            parse_mode="Markdown", 
            reply_markup=telebot.types.ReplyKeyboardRemove()
        )
    except Exception as e:
        bot.send_message(message.chat.id, f"❌ Error updating location: {e}")

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
        legenda = "\n_Legend:_  🌱 `Occupied`  |  🟫 `Empty`"
        
        # NOTA: Niente più backtick (```), inviamo direttamente il testo formattato!
        return griglia_str + legenda
        
    except Exception as e:
        return f"Error loading grid: {e}"


# COMANDO: IMPOSTA DIMENSIONI GIARDINO
@bot.message_handler(commands=['gardensize'])
def handle_set_dimensions(message):
    testo = (
        "📐 *Set Garden Dimensions*\n"
        "Type the number of Rows (Pumps) and the number of Taps (Plants) per row, "
        "separated by a comma.\n\n"
        "Example: *3, 4* (3 Rows, 4 Plants each)"
    )
    msg = bot.send_message(message.chat.id, testo, parse_mode="Markdown")
    bot.register_next_step_handler(msg, process_set_dimensions)

def process_set_dimensions(message):
    try:
        parts = [int(x.strip()) for x in message.text.split(',')]
        if len(parts) != 2:
            raise ValueError()
            
        new_max_pumps = parts[0]
        new_max_taps = parts[1]
        
        # Recupera tutti gli slot correnti per verificare i conflitti
        try:
            slots_res = requests.get(f"{CATALOG_REST_URL}/slots", timeout=5).json()
        except:
            slots_res = []
            
        out_of_bounds = []
        for slot in slots_res:
            slot_id = slot.get("slotID", "")
            # slot_id è tipo P1_R2.
            try:
                p_str, r_str = slot_id.split('_')
                p_num = int(p_str[1:])
                r_num = int(r_str[1:])
                if p_num > new_max_pumps or r_num > new_max_taps:
                    out_of_bounds.append(slot_id)
            except:
                pass
                
        if len(out_of_bounds) > 0:
            # Ci sono conflitti
            testo_conflitti = (
                "⚠️ *Warning!*\n"
                f"You want to reduce dimensions to {new_max_pumps} rows and {new_max_taps} taps, "
                "but there are plants configured in slots that will be deleted:\n"
                f"`{', '.join(out_of_bounds)}`\n\n"
                "Do you want to proceed and permanently delete these configurations?"
            )
            markup = telebot.types.InlineKeyboardMarkup()
            # Salviamo le nuove dimensioni nella callback data. (Max 64 bytes per callback_data)
            btn_si = telebot.types.InlineKeyboardButton("✅ Confirm and Remove", callback_data=f"dim_ok_{new_max_pumps}_{new_max_taps}")
            btn_no = telebot.types.InlineKeyboardButton("❌ Cancel", callback_data="dim_no")
            markup.row(btn_si, btn_no)
            
            bot.send_message(message.chat.id, testo_conflitti, parse_mode="Markdown", reply_markup=markup)
            return

        # Se non ci sono conflitti, aggiorna subito
        payload = {"max_pumps": new_max_pumps, "max_taps": new_max_taps}
        requests.put(f"{CATALOG_REST_URL}/grid", json=payload, timeout=5).raise_for_status()
        
        bot.send_message(
            message.chat.id, 
            f"✅ Dimensions updated!\nHere is your new garden:\n{genera_griglia_testo()}", 
            parse_mode="Markdown" 
        )
    except ValueError:
        bot.send_message(message.chat.id, "❌ Invalid format. Use only numbers (e.g., 3, 4).")
    except Exception as e:
        bot.send_message(message.chat.id, f"❌ DB update error: {e}")

@bot.callback_query_handler(func=lambda call: call.data.startswith("dim_"))
def handle_dim_callback(call):
    bot.answer_callback_query(call.id)
    bot.edit_message_reply_markup(call.message.chat.id, call.message.message_id, reply_markup=None)
    
    if call.data == "dim_no":
        bot.send_message(call.message.chat.id, "❌ *Operation cancelled*. The garden dimensions have not been changed.", parse_mode="Markdown")
        return
        
    if call.data.startswith("dim_ok_"):
        parts = call.data.split('_')
        new_max_pumps = int(parts[2])
        new_max_taps = int(parts[3])
        
        try:
            # 1. Recupera gli slot ed elimina quelli fuori range
            slots_res = requests.get(f"{CATALOG_REST_URL}/slots", timeout=5).json()
            deleted_count = 0
            for slot in slots_res:
                slot_id = slot.get("slotID", "")
                try:
                    p_str, r_str = slot_id.split('_')
                    p_num = int(p_str[1:])
                    r_num = int(r_str[1:])
                    if p_num > new_max_pumps or r_num > new_max_taps:
                        requests.delete(f"{CATALOG_REST_URL}/slots/{slot_id}", timeout=5)
                        deleted_count += 1
                except:
                    pass
            
            # 2. Aggiorna la grid
            payload = {"max_pumps": new_max_pumps, "max_taps": new_max_taps}
            requests.put(f"{CATALOG_REST_URL}/grid", json=payload, timeout=5).raise_for_status()
            
            bot.send_message(
                call.message.chat.id, 
                f"✅ Dimensions updated and {deleted_count} slots removed!\nHere is your new garden:\n{genera_griglia_testo()}", 
                parse_mode="Markdown" 
            )
        except Exception as e:
            bot.send_message(call.message.chat.id, f"❌ Update error: {e}")

# COMANDO: VISUALIZZA GIARDINO
@bot.message_handler(commands=['garden'])
def handle_show_garden(message):
    bot.send_message(
        message.chat.id, 
        f"🌱 *Map of your Garden:*\n{genera_griglia_testo()}", 
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
        print(f"⚠️ Warning: Unable to connect to MQTT broker. The bot will start anyway. ({e})")
        
    # 2. Avvio Bot Telegram in primo piano
    print("[BOT] Telegram Bot listening...")
    bot.infinity_polling()