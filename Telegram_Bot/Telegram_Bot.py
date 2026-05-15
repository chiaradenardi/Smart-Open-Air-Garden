
import telebot
import paho.mqtt.client as mqtt
import requests
import json
import os
from dotenv import load_dotenv # Add this library

# This function looks for a file named ".env" in the current folder and loads it
load_dotenv()

# GLOBAL CONFIGURATION
# 1. Get this token by writing to @BotFather on Telegram
TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN") 
bot = telebot.TeleBot(TELEGRAM_TOKEN)

# IP del Message Broker e del microservizio che riceve la configurazione (es. Smart Irrigation Strategy)
# Read from environment variable set in docker-compose.yml
BROKER_IP = os.getenv("BROKER_IP", "message-broker")
STRATEGY_REST_URL = os.getenv('SLOTS_URL', 'http://service-catalog:8080/slots')
CATALOG_REST_URL = os.getenv('CATALOG_URL', 'http://service-catalog:8080')
STATISTICS_URL = os.getenv('STATISTICS_URL', 'http://statistics-service:8082')

# Variable to save the user's chat ID (to send MQTT messages)
user_chat_id = None 

# --- MQTT CALLBACK (Incoming Notifications Management) ---
def on_connect(client, userdata, flags, rc):
    if rc == 0:
        print("[MQTT] Bot connesso al Broker!")
        # The bot subscribes to alarms and pump topics
        client.subscribe("garden/alerts/faults")
        client.subscribe("garden/+/pump")
    else:
        print(f"[MQTT] Connection error: {rc}")

def on_message(client, userdata, msg):
    try:
        payload_raw = msg.payload.decode('utf-8')
        print(f"\n[BOT] 📨 Ricevuto su: {msg.topic}")
        
        # 1. Message decoding and formatting
        if "pump" in msg.topic:
            try:
                # Decode SenML (e.g. [{"v": 1, ...}])
                data = json.loads(payload_raw)
                status = data[0].get("v") # Gets the value 1 or 0
                pump_status = "ON ✅" if status == 1 else "OFF ❌"
                device = msg.topic.split("/")[1]
                message_text = f"💧 *Pump Update*\nDevice: `{device}`\nStatus: *{pump_status}*"
            except:
                message_text = f"💧 *Pump Update:*\n{payload_raw}"
        
        elif "faults" in msg.topic:
            try:
                # Unpack the JSON to avoid formatting issues
                fault_data = json.loads(payload_raw)
                device = fault_data.get("device", "Unknown")
                desc = fault_data.get("description", "Unknown fault")
                severity = fault_data.get("severity", "HIGH")
                
                message_text = (
                    f"🚨 *CRITICAL ALARM!* 🚨\n\n"
                    f"📟 *Device:* `{device}`\n"
                    f"⚠️ *Severity:* {severity}\n"
                    f"📝 *Details:* {desc}"
                )
            except:
                # Safety fallback: if not JSON, wrap in a code block
                message_text = f"🚨 *CRITICAL ALARM!*\n```text\n{payload_raw}\n```"
                
        else:
            message_text = f"ℹ️ *System Notification:*\n{payload_raw}"

        # 2. Send to all registered users
        users = requests.get(f"{CATALOG_REST_URL}/users", timeout=5).json()
        for u in users:
            chat_id = u.get("telegramChatID")
            if chat_id and len(str(chat_id)) > 5:
                bot.send_message(chat_id, message_text, parse_mode="Markdown")
                print(f"[BOT] Notification sent to {u['userName']}")

    except Exception as e:
        print(f"[BOT ERROR] Error in on_message: {e}")

# --- TELEGRAM HANDLER (User Interaction Management) ---

# --- MAIN MENU (DASHBOARD) ---

@bot.message_handler(commands=['start'])
def handle_start(message):
    global user_chat_id
    user_chat_id = message.chat.id  # Save ID for MQTT notifications

    welcome_message = (
        "🌱 *Smart Open Air Garden - Control Panel* 🌱\n\n"
        "Welcome to your IoT ecosystem. From here you can monitor the sensors, "
        "manage irrigation and monitor your consumption.\n\n"
        "Use the buttons below to navigate the system."
    )
    
    # Create the professional keyboard
    markup = telebot.types.InlineKeyboardMarkup(row_width=2)
    
    # Row 1: Main management
    btn_crop = telebot.types.InlineKeyboardButton("📊 Crop Management", callback_data="menu_crop")
    btn_devices = telebot.types.InlineKeyboardButton("🖥️ Device Status", callback_data="menu_devices")
    markup.add(btn_crop, btn_devices)
    
    # Row 2: Data and Settings
    btn_price = telebot.types.InlineKeyboardButton("💶 Water Price", callback_data="menu_price")
    btn_thresholds = telebot.types.InlineKeyboardButton("🌿 Available Crops", callback_data="menu_thresholds")
    markup.add(btn_price, btn_thresholds)
    
    # Row 3: Live Status
    btn_status = telebot.types.InlineKeyboardButton("📈 Garden Live Status", callback_data="menu_status")
    markup.add(btn_status)
    
    # Row 4: Admin and Location
    btn_admin = telebot.types.InlineKeyboardButton("🔧 Admin Management", callback_data="menu_admin")
    btn_location = telebot.types.InlineKeyboardButton("🌍 Set Weather Location", callback_data="menu_location")
    markup.add(btn_admin, btn_location)
    
    # Row 4: User Profile 
    btn_profile = telebot.types.InlineKeyboardButton("👤 Link Profile (Receive Notifications)", callback_data="menu_profile")
    markup.add(btn_profile)
    
    bot.reply_to(message, welcome_message, reply_markup=markup, parse_mode="Markdown")

# --- MENU ROUTER ---
# This function "listens" to button clicks and calls the functions
@bot.callback_query_handler(func=lambda call: call.data.startswith("menu_"))
def handle_main_menu(call):
    bot.answer_callback_query(call.id) # Remove "loading" on button
    
    command = call.data.split("_")[1]
    
    # Depending on the clicked button, route traffic to the correct function
    # passing 'call.message' so the function responds in the correct chat
    if command == "crop":
        handle_crop(call.message)
    elif command == "devices":
        handle_devices(call.message)
    elif command == "price":
        handle_price(call.message)
    elif command == "thresholds":
        handle_thresholds(call.message)
    elif command == "profile":
        handle_profile(call.message)
    elif command == "location":
        handle_menu_location(call.message)
    elif command == "admin":
        handle_admin_panel(call.message)
    elif command == "status":
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

        message_text = "📈 *Garden Live Status*\n\n"

        if not slots:
            message_text += "⚠️ No active slots configured.\n"
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

                message_text += f"🌱 *{s.get('slotName', slot_id)}* (`{slot_id}`)\n"
                message_text += f"  🖥️ Device: `{device_id}`\n"
                message_text += f"  🌿 Crop: *{plant_name}*\n"
                message_text += f"  💧 Last soil moisture: {moisture_str}\n\n"

        # 3. Fetch water savings from Statistics Service
        try:
            stats_res = requests.get(f"{STATISTICS_URL}/api/statistics?period=15m", timeout=5).json()
            stats = stats_res.get("statistics", {})
            message_text += "💾 *Water Savings (last 7 days)*\n"
            message_text += f"  💧 Litres saved: `{stats.get('liters_saved', 'N/A')} L`\n"
            message_text += f"  📉 Savings: `{stats.get('savings_percentage', 'N/A')}%`\n"
            message_text += f"  🔁 Pump activations: `{stats.get('pump_activations_smart', 'N/A')}`\n"
        except:
            message_text += "ℹ️ _Water savings stats temporarily unavailable._\n"

        bot.send_message(message.chat.id, message_text, parse_mode="Markdown")

    except Exception as e:
        bot.send_message(message.chat.id, f"❌ Error fetching garden status: {e}")

def handle_admin_panel(message):
    markup = telebot.types.InlineKeyboardMarkup(row_width=2)
    
    # Row 1: Slot
    markup.add(
        telebot.types.InlineKeyboardButton("➕ Add Slot", callback_data="admin_add_slot"),
        telebot.types.InlineKeyboardButton("➖ Remove Slot", callback_data="admin_rem_slot")
    )
    # Row 2: Device
    markup.add(
        telebot.types.InlineKeyboardButton("➕ Add Device", callback_data="admin_add_device"),
        telebot.types.InlineKeyboardButton("➖ Remove Device", callback_data="admin_rem_device")
    )
    # Row 3: Crops
    markup.add(
        telebot.types.InlineKeyboardButton("➕ Add Crop", callback_data="admin_add_plant"),
        telebot.types.InlineKeyboardButton("➖ Remove Crop", callback_data="admin_rem_plant")
    )
    # Row 4: Users
    markup.add(
        telebot.types.InlineKeyboardButton("➕ Add User", callback_data="admin_add_user"),
        telebot.types.InlineKeyboardButton("➖ Remove User", callback_data="admin_rem_user")
    )
    # Row 5: Dimensions and Garden
    markup.add(
        telebot.types.InlineKeyboardButton("📐 Garden Size", callback_data="admin_dimensions"),
        telebot.types.InlineKeyboardButton("🌱 Show Garden", callback_data="admin_garden")
    )
    
    message_text = "🔧 *Admin Panel*\n\nChoose the operation you wish to perform:"
    bot.send_message(message.chat.id, message_text, reply_markup=markup, parse_mode="Markdown")

@bot.callback_query_handler(func=lambda call: call.data.startswith("admin_"))
def handle_admin_callbacks(call):
    bot.answer_callback_query(call.id)
    action_str = call.data.replace("admin_", "")
    
    msg = call.message
    
    if action_str == "add_slot":
        handle_add_slot(msg)
    elif action_str == "rem_slot":
        handle_remove_slot(msg)
    elif action_str == "add_device":
        handle_add_device(msg)
    elif action_str == "rem_device":
        handle_remove_device(msg)
    elif action_str == "add_plant":
        handle_add_plant(msg)
    elif action_str == "rem_plant":
        handle_remove_plant(msg)
    elif action_str == "add_user":
        handle_add_user(msg)
    elif action_str == "rem_user":
        handle_remove_user(msg)
    elif action_str == "dimensions":
        handle_set_dimensions(msg)
    elif action_str == "garden":
        handle_show_garden(msg)

def handle_menu_location(message):
    # Create a Reply Keyboard (bottom bar) with native GPS permission button
    markup = telebot.types.ReplyKeyboardMarkup(resize_keyboard=True, one_time_keyboard=True)
    btn_pos = telebot.types.KeyboardButton("📍 Send my GPS location", request_location=True)
    markup.add(btn_pos)
    
    message_text = (
        "🌍 *Weather Location Settings*\n\n"
        "Press the button below to send the system your exact GPS coordinates.\n\n"
        "💡 _If the garden is in another city, simply type the command:_\n"
        "`/city CityName,IT` (e.g. `/city Turin,IT`)"
    )
    bot.send_message(message.chat.id, message_text, reply_markup=markup, parse_mode="Markdown")
 

@bot.message_handler(commands=['crop'])



def handle_crop(message):
    try:
        # 1. Get the UPDATED list of slots from the catalog
        slots = requests.get(STRATEGY_REST_URL, timeout=5).json()
        
        if not slots:
            bot.send_message(message.chat.id, "There are no slots configured in the garden at the moment.")
            return

        markup = telebot.types.InlineKeyboardMarkup()
        
        # 2. Create a button dynamically for each slot found in the JSON file
        for s in slots:
            slot_id = s.get("slotID")
            slot_name = s.get("slotName", f"Zone {slot_id}")
            
            # Create the button and add it to the keyboard
            btn = telebot.types.InlineKeyboardButton(f"🌱 {slot_name} ({slot_id})", callback_data=f"slot_{slot_id}")
            markup.add(btn)
        
        bot.send_message(message.chat.id, "Which slot do you want to update?", reply_markup=markup)
        
    except Exception as e:
        bot.send_message(message.chat.id, f"❌ Error contacting the Catalog: {e}")

@bot.callback_query_handler(func=lambda call: call.data.startswith("slot_"))
def handle_slot_selection(call):

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
    # exemple of callback data : plant_P3_P1_R1
    stringa_dati = call.data.replace("plant_", "") 
    pezzi = stringa_dati.split("_")
    
    plant_id = pezzi[0] # takes "P3"
    selected_slot = "_".join(pezzi[1:]) # takes the rest of the string and joins them (eg. "P1_R1")
    
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
        
        # --- Update the final response ---
        slots_data = requests.get(STRATEGY_REST_URL, timeout=5).json()
        strategies_data = requests.get(f"{CATALOG_REST_URL}/strategies", timeout=5).json()
        
        dettaglio_slot = []
        for slot in slots_data:
            id_pianta = slot.get("plantID")
            crop_name = "unknown"
            if id_pianta in strategies_data:
                crop_name = strategies_data[id_pianta]["name"]
                
            dettaglio_slot.append(f"slot {slot.get('slotID')}: {crop_name}")
        
        testo_finale = f"✅ Configuration updated!\n\n{', '.join(dettaglio_slot).capitalize()}."
        bot.send_message(call.message.chat.id, testo_finale)
        
    except Exception as e:
        bot.send_message(call.message.chat.id, f"❌ Error: {e}")
    


# --- ADD AND REMOVE SLOTS ---

# ADD SLOT COMMAND (POST)
@bot.message_handler(commands=['addslot'])
def handle_add_slot(message):
    message_text = (
        "🌱 *Add a new Slot* 🌱\n"
        "To cultivate a zone, type the grid coordinate, the Crop ID and the Device ID separated by commas:\n\n"
        "`Coordinate, Crop ID, Device ID`\n\n"
        "Example: *P1_R2, P3, RPi_003*\n"
        "_(Use /garden to see available coordinates)_"
    )
    msg = bot.send_message(message.chat.id, message_text, parse_mode="Markdown")
    bot.register_next_step_handler(msg, process_add_slot)

def process_add_slot(message):
    try:
        parts = [x.strip() for x in message.text.split(',')]
        
        if len(parts) != 3:
            bot.send_message(message.chat.id, "❌ Format error. You must enter 3 comma-separated values.\nExample: P1_R2, P3, RPi_003")
            return
            
        slot_id, plant_id, device_id = parts
        slot_id = slot_id.upper() # Force uppercase to avoid errors (eg. p1_r2 becomes P1_R2)
        
        # Validation of the coordinate: must start with P and contain _R
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
        
        # Slot creation
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
                f"✅ *Success!* Device `{device_id}` is now irrigating zone `{slot_id}`.\n\nHere is your updated garden:\n\n{generate_text_grid()}", 
                parse_mode="Markdown"
            )
            
    except Exception as e:
        bot.send_message(message.chat.id, f"❌ Connection error: {e}")
# COMMAND: REMOVE SLOT (DELETE)
@bot.message_handler(commands=['removeslot'])
def handle_remove_slot(message):
    try:
        # Ask the catalog which slots currently exist
        slots = requests.get(STRATEGY_REST_URL, timeout=5).json()
        
        if not slots:
            bot.send_message(message.chat.id, "There are no slots in the garden at the moment!")
            return
            
        markup = telebot.types.InlineKeyboardMarkup()
        for s in slots:
            # Creating a red button for each slot found
            btn = telebot.types.InlineKeyboardButton(f"🗑️ Delete {s.get('slotName', s['slotID'])}", callback_data=f"del_slot_{s['slotID']}")
            markup.add(btn)
            
        bot.send_message(message.chat.id, "⚠️ *Warning, irreversible operation!*\nWhich slot do you want to delete from the system?", reply_markup=markup, parse_mode="Markdown")
        
    except Exception as e:
        bot.send_message(message.chat.id, f"❌ Error contacting the Catalog: {e}")

@bot.callback_query_handler(func=lambda call: call.data.startswith("del_slot_"))
def process_del_slot(call):
    # Remove the loading animation on the button
    bot.answer_callback_query(call.id)
    
    # Extract the ID
    slot_id = call.data.split("_")[2]
    
    try:
        # Making a DELETE by passing the ID directly in the URL 
        response = requests.delete(f"{STRATEGY_REST_URL}/{slot_id}", timeout=5)
        response.raise_for_status()
        
        data = response.json()
        if "error" in data:
            bot.send_message(call.message.chat.id, f"❌ Unable to delete: {data['error']}")
        else:
            bot.send_message(call.message.chat.id, f"🗑️ Slot `{slot_id}` permanently deleted from the system.", parse_mode="Markdown")
            
    except Exception as e:
        bot.send_message(call.message.chat.id, f"❌ Connection error: {e}")

# ---   SYSTEM STARTUP ---
# --- WATER PRICE MANAGEMENT ---
@bot.message_handler(commands=['price'])
def handle_price(message):
    try:
        # 1. Ask the catalog for the current price
        response = requests.get(f"{CATALOG_REST_URL}/price", timeout=5)
        response.raise_for_status()
        prezzo_attuale = response.json()
        
        # 2. Create the button to edit it
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
        new_price = float(message.text.replace(',', '.')) 
        payload = {"NewWaterPricePerM3": new_price}
        response = requests.put(f"{CATALOG_REST_URL}/price", json=payload, timeout=5)
        response.raise_for_status()
        bot.send_message(message.chat.id, f"✅ Price successfully updated to *{new_price} €/m³*!", parse_mode="Markdown")
    except ValueError:
        bot.send_message(message.chat.id, "❌ Error: Enter a valid number (e.g. 2.5). Try again using /price.")
    except Exception as e:
        bot.send_message(message.chat.id, f"❌ Error: {e}")

# --- DEVICE MANAGEMENT ---
@bot.message_handler(commands=['devices'])
def handle_devices(message):
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

        message_text = "🖥️ *IoT Device Status*\n\n"
        for d in devices:
            d_id = d['deviceID']
            status_icon = "🟢" if d.get('status') == 'active' else "🔴"
            message_text += f"{status_icon} 🖥️ *{d['deviceName']}* (`{d_id}`)\n"
            message_text += f"  📡 Sensors: {', '.join(d.get('sensors', []))}\n"
            message_text += f"  ⚙️ Actuators: {', '.join(d.get('actuators', []))}\n"

            # Show assigned slots with crop
            assigned = dev_slots.get(d_id, [])
            if assigned:
                for s in assigned:
                    p_id = s.get("plantID")
                    p_name = strategies.get(p_id, {}).get("name", "Unknown") if p_id else "—"
                    message_text += f"  📍 Slot: `{s['slotID']}` · 🌿 Crop: *{p_name}*\n"
            else:
                message_text += "  📍 Slot: `—` · 🌿 Crop: *No assignment*\n"
            message_text += "\n"

        bot.send_message(message.chat.id, message_text, parse_mode="Markdown")
    except Exception as e:
        bot.send_message(message.chat.id, f"❌ Error contacting the Catalog: {e}")

# ---ADD AND REMOVE DEVICES ---

# ADD DEVICE COMMAND (POST)
@bot.message_handler(commands=['adddevice'])
def handle_add_device(message):
    message_text = (
        "📟 *Register a new IoT Device* 📟\n"
        "Type the device ID and Name, separated by a comma:\n\n"
        "`Device ID, Device Name`\n\n"
        "Example: *RPi_003, GardenGateway_003*"
    )
    msg = bot.send_message(message.chat.id, message_text, parse_mode="Markdown")
    bot.register_next_step_handler(msg, process_add_device)

def process_add_device(message):
    try:
        parts = [x.strip() for x in message.text.split(',')]
        
        if len(parts) != 2:
            bot.send_message(message.chat.id, "❌ Format error. You must enter 2 comma-separated values. Try again with /adddevice")
            return
            
        device_id, device_name = parts
        
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

# COMMAND: REMOVE DEVICE (DELETE)
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
# --- ADD PLANTS / STRATEGIES ---

@bot.message_handler(commands=['addplant'])
def handle_add_plant(message):
    message_text = (
        "🌿 *Add a new Crop to the Catalog* 🌿\n"
        "Type the data separated by commas in this format:\n\n"
        "`Crop ID, Name, Minimum Moisture Threshold`\n\n"
        "Example: *P3, Lettuce, 50.0*"
    )
    msg = bot.send_message(message.chat.id, message_text, parse_mode="Markdown")
    bot.register_next_step_handler(msg, process_add_plant)

def process_add_plant(message):
    try:
        parts = [x.strip() for x in message.text.split(',')]
        
        if len(parts) != 3:
            bot.send_message(message.chat.id, "❌ Incorrect format. Enter 3 values: ID, Name, Threshold (e.g. P3, Lettuce, 50.0). Try again with /addplant")
            return
            
        plant_id, name, threshold_str = parts
        
        # Convert the threshold to a number 
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

# --- DISPLAY STRATEGY THRESHOLDS ---
@bot.message_handler(commands=['thresholds'])
def handle_thresholds(message):
    try:
        # Retrieve strategies from catalog
        strategies = requests.get(f"{CATALOG_REST_URL}/strategies", timeout=5).json()
        
        message_text = "📊 *Available Crops & Irrigation Thresholds*\n\n"
        
        # Iterate over the strategies dictionary
        for plant_id, info in strategies.items():
            message_text += f"🌿 *{info['name']}* (`{plant_id}`)\n"
            message_text += f"  💧 Pump activates below: {info['min_moisture_threshold']}%\n\n"
            
        bot.send_message(message.chat.id, message_text, parse_mode="Markdown")
        
    except Exception as e:
        bot.send_message(message.chat.id, f"❌ Error contacting the Catalog: {e}")

# --- MANAGE PROFILE AND CHAT ID ---
@bot.message_handler(commands=['profile'])
def handle_profile(message):
    try:
        # Retrieve user list from catalog
        users = requests.get(f"{CATALOG_REST_URL}/users", timeout=5).json()
        
        message_text = (
            f"👤 *Your Telegram Chat ID:* `{message.chat.id}`\n\n"
            "To receive emergency notifications on this phone, "
            "select your profile from the list below:"
        )
        
        markup = telebot.types.InlineKeyboardMarkup()
        for u in users:
            # Create a button for each user present in the JSON file
            btn = telebot.types.InlineKeyboardButton(f"🙋‍♂️ I am {u['userName']}", callback_data=f"link_user_{u['userID']}")
            markup.add(btn)
            
        bot.send_message(message.chat.id, message_text, reply_markup=markup, parse_mode="Markdown")
        
    except Exception as e:
        bot.send_message(message.chat.id, f"❌ Error contacting the Catalog: {e}")
@bot.callback_query_handler(func=lambda call: call.data.startswith("link_user_"))
def handle_link_user(call):
    # Extract user ID and current Chat ID
    user_id = call.data.replace("link_user_", "")
    chat_id = call.message.chat.id
    
    bot.answer_callback_query(call.id) 
    
    try:
        # Prepare payload for users PUT
        payload = {
            "userID": user_id,
            "telegramChatID": str(chat_id)
        }
        
        response = requests.put(f"{CATALOG_REST_URL}/users", json=payload, timeout=5)
        response.raise_for_status()
        
        bot.send_message(call.message.chat.id, f"✅ Linking successful!\nThe profile *{user_id}* is now associated with this phone. You will receive all garden alarms here.", parse_mode="Markdown")
        
    except Exception as e:
        bot.send_message(call.message.chat.id, f"❌ Error during linking: {e}")

# --- USERS MANAGEMENT ---

@bot.message_handler(commands=['adduser'])
def handle_add_user(message):
    message_text = "👤 *Add a new User* 👤\nType the data in this format:\n`User ID, Name`\nExample: *U_003, Luigi*"
    msg = bot.send_message(message.chat.id, message_text, parse_mode="Markdown")
    bot.register_next_step_handler(msg, process_add_user)

def process_add_user(message):
    try:
        parts = [x.strip() for x in message.text.split(',')]
        if len(parts) != 2:
            bot.send_message(message.chat.id, "❌ Incorrect format. Try again with /adduser")
            return
            
        user_id, user_name = parts
        
        # Initialize the empty telegramChatID. The user will fill it in later using /profile
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

# --- WEATHER LOCATION MANAGEMENT ---

# OPTION A: Text Location (e.g. /city Turin,IT)
@bot.message_handler(commands=['city'])
def handle_city(message):
    msg = bot.send_message(message.chat.id, "🌍 *Set Weather City*\nEnter the city name (e.g. `Turin,IT`) or coordinates (e.g. `45.07,7.68`):", parse_mode="Markdown")
    bot.register_next_step_handler(msg, process_city)

def process_city(message):
    new_location = message.text.strip()
    try:
        requests.put(f"{CATALOG_REST_URL}/location", json={"location": new_location}, timeout=5).raise_for_status()
        bot.send_message(message.chat.id, f"✅ Weather location updated to: *{new_location}*", parse_mode="Markdown")
    except Exception as e:
        bot.send_message(message.chat.id, f"❌ Error updating location: {e}")

# OPTION B: GPS Location with special Telegram button
@bot.message_handler(commands=['location'])
def handle_gps_location(message):
    # Create a Reply Keyboard (bottom bar) with native Telegram button
    markup = telebot.types.ReplyKeyboardMarkup(resize_keyboard=True, one_time_keyboard=True)
    btn_pos = telebot.types.KeyboardButton("📍 Send my GPS location", request_location=True)
    markup.add(btn_pos)
    
    bot.send_message(message.chat.id, "Press the button below to send your exact GPS coordinates for the Weather service:", reply_markup=markup)

# This handler triggers automatically when the user presses the GPS button
@bot.message_handler(content_types=['location'])
def handle_received_location(message):
    lat = message.location.latitude
    lon = message.location.longitude
    new_location = f"{lat},{lon}"
    
    try:
        requests.put(f"{CATALOG_REST_URL}/location", json={"location": new_location}, timeout=5).raise_for_status()
        # Remove special keyboard and confirm
        bot.send_message(
            message.chat.id, 
            f"✅ GPS Location received and saved!\nCoordinates: `{new_location}`\nThe irrigation system will now check the weather for this zone.", 
            parse_mode="Markdown", 
            reply_markup=telebot.types.ReplyKeyboardRemove()
        )
    except Exception as e:
        bot.send_message(message.chat.id, f"❌ Error updating location: {e}")

# --- VISUAL GARDEN MANAGEMENT (GRID) ---


def generate_text_grid():
    """Generates the visual grid using Telegram Emojis"""
    try:
        grid_data = requests.get(f"{CATALOG_REST_URL}/grid", timeout=5).json()
        slots_data = requests.get(STRATEGY_REST_URL, timeout=5).json()
        
        max_pumps = grid_data.get("max_pumps", 3)
        max_taps = grid_data.get("max_taps", 3)
        
        occupied_slots = [s.get("slotID") for s in slots_data if s.get("status") == "active"]

        # Build the top header (R1, R2, etc.)
        grid_str = "      " # Initial space to align
        for r in range(1, max_taps + 1):
            grid_str += f"R{r}  "
        grid_str += "\n"

        # Draw dirt and plants
        for p in range(1, max_pumps + 1):
            row_str = f"*P{p}* " # Put P1, P2 in bold
            for r in range(1, max_taps + 1):
                coordinate = f"P{p}_R{r}"
                
                if coordinate in occupied_slots:
                    row_str += "🌱  " # Crop (Occupied)
                else:
                    row_str += "🟫  " # Dirt (Empty)
                    
            grid_str += row_str + "\n"

        # Add a small legend at the bottom
        legend = "\n_Legend:_  🌱 `Occupied`  |  🟫 `Empty`"
        
        # NOTE: No more backticks (```), send the formatted message_text directly!
        return grid_str + legend
        
    except Exception as e:
        return f"Error loading grid: {e}"


# COMMAND: SET GARDEN DIMENSIONS
@bot.message_handler(commands=['gardensize'])
def handle_set_dimensions(message):
    message_text = (
        "📐 *Set Garden Dimensions*\n"
        "Type the number of Rows (Pumps) and the number of Taps (Plants) per row, "
        "separated by a comma.\n\n"
        "Example: *3, 4* (3 Rows, 4 Plants each)"
    )
    msg = bot.send_message(message.chat.id, message_text, parse_mode="Markdown")
    bot.register_next_step_handler(msg, process_set_dimensions)

def process_set_dimensions(message):
    try:
        parts = [int(x.strip()) for x in message.text.split(',')]
        if len(parts) != 2:
            raise ValueError()
            
        new_max_pumps = parts[0]
        new_max_taps = parts[1]
        
        # Fetch all current slots to check for conflicts
        try:
            slots_res = requests.get(f"{CATALOG_REST_URL}/slots", timeout=5).json()
        except:
            slots_res = []
            
        out_of_bounds = []
        for slot in slots_res:
            slot_id = slot.get("slotID", "")
            # slot_id is like P1_R2.
            try:
                p_str, r_str = slot_id.split('_')
                p_num = int(p_str[1:])
                r_num = int(r_str[1:])
                if p_num > new_max_pumps or r_num > new_max_taps:
                    out_of_bounds.append(slot_id)
            except:
                pass
                
        if len(out_of_bounds) > 0:
            # There are conflicts
            conflict_text = (
                "⚠️ *Warning!*\n"
                f"You want to reduce dimensions to {new_max_pumps} rows and {new_max_taps} taps, "
                "but there are plants configured in slots that will be deleted:\n"
                f"`{', '.join(out_of_bounds)}`\n\n"
                "Do you want to proceed and permanently delete these configurations?"
            )
            markup = telebot.types.InlineKeyboardMarkup()
            # Save the new dimensions in the callback data. (Max 64 bytes per callback_data)
            btn_yes = telebot.types.InlineKeyboardButton("✅ Confirm and Remove", callback_data=f"dim_ok_{new_max_pumps}_{new_max_taps}")
            btn_no = telebot.types.InlineKeyboardButton("❌ Cancel", callback_data="dim_no")
            markup.row(btn_yes, btn_no)
            
            bot.send_message(message.chat.id, conflict_text, parse_mode="Markdown", reply_markup=markup)
            return

        # If no conflicts, update immediately
        payload = {"max_pumps": new_max_pumps, "max_taps": new_max_taps}
        requests.put(f"{CATALOG_REST_URL}/grid", json=payload, timeout=5).raise_for_status()
        
        bot.send_message(
            message.chat.id, 
            f"✅ Dimensions updated!\nHere is your new garden:\n{generate_text_grid()}", 
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
            # 1. Fetch slots and delete those out of range
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
            
            # 2. Update grid
            payload = {"max_pumps": new_max_pumps, "max_taps": new_max_taps}
            requests.put(f"{CATALOG_REST_URL}/grid", json=payload, timeout=5).raise_for_status()
            
            bot.send_message(
                call.message.chat.id, 
                f"✅ Dimensions updated and {deleted_count} slots removed!\nHere is your new garden:\n{generate_text_grid()}", 
                parse_mode="Markdown" 
            )
        except Exception as e:
            bot.send_message(call.message.chat.id, f"❌ Update error: {e}")

# COMMAND: SHOW GARDEN
@bot.message_handler(commands=['garden'])
def handle_show_garden(message):
    bot.send_message(
        message.chat.id, 
        f"🌱 *Map of your Garden:*\n{generate_text_grid()}", 
        parse_mode="Markdown"
    )




if __name__ == "__main__":
    mqtt_client = mqtt.Client()
    mqtt_client.on_connect = on_connect
    mqtt_client.on_message = on_message
    try:
        mqtt_client.connect(BROKER_IP, 1883, 60)
        mqtt_client.loop_start()
    except Exception as e:
        print(f"⚠️ Warning: Unable to connect to MQTT broker. The bot will start anyway. ({e})") 
    print("[BOT] Telegram Bot listening...")
    bot.infinity_polling()