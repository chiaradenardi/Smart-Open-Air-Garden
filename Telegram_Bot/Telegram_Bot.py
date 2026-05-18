import telebot
import paho.mqtt.client as mqtt
import requests
import json
import os
from typing import Optional
from dotenv import load_dotenv

load_dotenv()

TELEGRAM_TOKEN    = os.getenv("TELEGRAM_TOKEN")
bot               = telebot.TeleBot(TELEGRAM_TOKEN)

BROKER_IP         = os.getenv("BROKER_IP",       "message-broker")
CATALOG_REST_URL  = os.getenv("CATALOG_URL",      "http://service-catalog:8080")
STATISTICS_URL    = os.getenv("STATISTICS_URL",   "http://statistics-service:8082")
INFLUX_URL        = os.getenv("INFLUX_ADAPTOR_URL","http://influx-adaptor:8081")

# ── Garden selection state (in-RAM, per chat) ─────────────────────────────────
# chat_id (str) → gardenID (str)
chat_garden_map: dict = {}


# ── Helpers ───────────────────────────────────────────────────────────────────

def gid(chat_id) -> Optional[str]:
    """Return the active gardenID for this chat, or None."""
    return chat_garden_map.get(str(chat_id))


def active_garden(chat_id):
    """Return (gardenID, garden_dict) or (None, None)."""
    g = gid(chat_id)
    if not g:
        return None, None
    try:
        r = requests.get(f"{CATALOG_REST_URL}/gardens/{g}", timeout=5).json()
        if "error" in r:
            return None, None
        return g, r
    except Exception:
        return None, None


def need_garden(message) -> bool:
    """Send 'select a garden first' prompt. Returns True if OK, False if missing."""
    if gid(message.chat.id):
        return True
    markup = telebot.types.InlineKeyboardMarkup()
    markup.add(telebot.types.InlineKeyboardButton("🌿 Select Garden", callback_data="menu_gardens"))
    bot.send_message(message.chat.id,
                     "⚠️ No active garden selected. Please choose one first:",
                     reply_markup=markup)
    return False


def err(message, e):
    bot.send_message(message.chat.id, f"❌ Error: {e}")


# ── MQTT ──────────────────────────────────────────────────────────────────────

def on_connect(client, userdata, flags, rc):
    if rc == 0:
        print("[MQTT] Bot connected to broker")
        client.subscribe("garden/alerts/faults")
        client.subscribe("garden/+/+/pump")
    else:
        print(f"[MQTT] Error: {rc}")


def on_message(client, userdata, msg):
    try:
        raw   = msg.payload.decode('utf-8')
        topic = msg.topic

        if "pump" in topic:
            parts     = topic.split('/')   # garden/G_001/P1_R1/pump
            garden_id = parts[1] if len(parts) > 1 else "?"
            slot_id   = parts[2] if len(parts) > 2 else "?"
            try:
                data   = json.loads(raw)
                status = "ON ✅" if data[0].get("v") == 1 else "OFF ❌"
            except Exception:
                status = raw
            text = f"💧 *Pump Update*\nGarden: `{garden_id}` · Slot: `{slot_id}`\nStatus: *{status}*"

        elif "faults" in topic:
            try:
                d  = json.loads(raw)
                g  = d.get("garden_id", "?")
                sl = d.get("slot_id",   "?")
                text = (
                    f"🚨 *CRITICAL ALARM!*\n\n"
                    f"🌿 Garden: `{g}` · Slot: `{sl}`\n"
                    f"⚠️ Error: {d.get('error','')}\n"
                    f"💧 Moisture: {d.get('val_init','?')}% → {d.get('val_now','?')}%"
                )
            except Exception:
                text = f"🚨 *ALARM:*\n```\n{raw}\n```"
        else:
            text = f"ℹ️ {raw}"

        # Send to all registered users
        users = requests.get(f"{CATALOG_REST_URL}/users", timeout=5).json()
        for u in users:
            cid = u.get("telegramChatID")
            if cid and len(str(cid)) > 5:
                bot.send_message(cid, text, parse_mode="Markdown")
    except Exception as e:
        print(f"[BOT MQTT ERROR] {e}")


# ── /start ────────────────────────────────────────────────────────────────────

@bot.message_handler(commands=['start'])
def handle_start(message):
    markup = telebot.types.InlineKeyboardMarkup(row_width=2)
    markup.add(
        telebot.types.InlineKeyboardButton("🌿 My Gardens",          callback_data="menu_gardens"),
        telebot.types.InlineKeyboardButton("📊 Crop Management",     callback_data="menu_crop"),
    )
    markup.add(
        telebot.types.InlineKeyboardButton("🖥️ Device Status",       callback_data="menu_devices"),
        telebot.types.InlineKeyboardButton("📈 Garden Live Status",  callback_data="menu_status"),
    )
    markup.add(
        telebot.types.InlineKeyboardButton("💶 Water Price",         callback_data="menu_price"),
        telebot.types.InlineKeyboardButton("🌿 Available Crops",     callback_data="menu_thresholds"),
    )
    markup.add(
        telebot.types.InlineKeyboardButton("🔧 Admin Panel",         callback_data="menu_admin"),
        telebot.types.InlineKeyboardButton("🌍 Set Location",        callback_data="menu_location"),
    )
    markup.add(
        telebot.types.InlineKeyboardButton("👤 Link Profile",        callback_data="menu_profile"),
    )
    bot.reply_to(message,
        "🌱 *Smart Open Air Garden* 🌱\n\nWelcome! Select a garden first, then use the menu.",
        reply_markup=markup, parse_mode="Markdown")


@bot.callback_query_handler(func=lambda c: c.data.startswith("menu_"))
def handle_main_menu(call):
    bot.answer_callback_query(call.id)
    cmd = call.data.split("_", 1)[1]
    dispatch = {
        "gardens":    handle_gardens,
        "crop":       handle_crop,
        "devices":    handle_devices,
        "status":     handle_status,
        "price":      handle_price,
        "thresholds": handle_thresholds,
        "profile":    handle_profile,
        "location":   handle_menu_location,
        "admin":      handle_admin_panel,
    }
    fn = dispatch.get(cmd)
    if fn:
        fn(call.message)


# ── Gardens management ────────────────────────────────────────────────────────

@bot.message_handler(commands=['gardens'])
def handle_gardens(message):
    try:
        gardens = requests.get(f"{CATALOG_REST_URL}/gardens", timeout=5).json()
        markup  = telebot.types.InlineKeyboardMarkup()
        active  = gid(message.chat.id)
        for g in gardens:
            label = f"{'✅ ' if g['gardenID'] == active else ''}🌿 {g['gardenName']} ({g['gardenID']})"
            markup.add(telebot.types.InlineKeyboardButton(label, callback_data=f"sel_garden_{g['gardenID']}"))
        markup.add(telebot.types.InlineKeyboardButton("➕ Create New Garden", callback_data="create_garden"))
        bot.send_message(message.chat.id, "🌿 *Your Gardens* — tap one to select it as active:",
                         reply_markup=markup, parse_mode="Markdown")
    except Exception as e:
        err(message, e)


@bot.callback_query_handler(func=lambda c: c.data.startswith("sel_garden_"))
def handle_select_garden(call):
    bot.answer_callback_query(call.id)
    garden_id = call.data.replace("sel_garden_", "")
    chat_id   = str(call.message.chat.id)
    try:
        g = requests.get(f"{CATALOG_REST_URL}/gardens/{garden_id}", timeout=5).json()
        if "error" in g:
            bot.send_message(call.message.chat.id, f"❌ Garden not found: {garden_id}")
            return
        chat_garden_map[chat_id] = garden_id
        slots_count  = len(g.get("slots", []))
        device       = g.get("device", {}).get("deviceID", "—")
        bot.send_message(call.message.chat.id,
            f"✅ *Active garden set!*\n\n"
            f"🌿 *{g['gardenName']}* (`{garden_id}`)\n"
            f"📡 Device: `{device}`\n"
            f"🌱 Slots: {slots_count}",
            parse_mode="Markdown")
    except Exception as e:
        err(call.message, e)


@bot.callback_query_handler(func=lambda c: c.data == "create_garden")
def handle_create_garden_start(call):
    bot.answer_callback_query(call.id)
    msg = bot.send_message(call.message.chat.id,
        "🌿 *Create New Garden*\n\nEnter the garden details separated by commas:\n"
        "`Garden ID, Garden Name`\n\nExample: *G_003, Rooftop Garden*",
        parse_mode="Markdown")
    bot.register_next_step_handler(msg, process_create_garden)


def process_create_garden(message):
    try:
        parts = [x.strip() for x in message.text.split(',')]
        if len(parts) != 2:
            bot.send_message(message.chat.id, "❌ Format: `Garden ID, Name`"); return
        garden_id, garden_name = parts
        payload = {"gardenID": garden_id, "gardenName": garden_name,
                   "grid": {"max_pumps": 4, "max_taps": 4}, "ownerIDs": []}
        r = requests.post(f"{CATALOG_REST_URL}/gardens", json=payload, timeout=5)
        r.raise_for_status()
        d = r.json()
        if "error" in d:
            bot.send_message(message.chat.id, f"❌ {d['error']}"); return
        chat_garden_map[str(message.chat.id)] = garden_id
        bot.send_message(message.chat.id,
            f"✅ Garden *{garden_name}* (`{garden_id}`) created and set as active!\n"
            f"Now use /adddevice to register the Raspberry Pi for this garden.",
            parse_mode="Markdown")
    except Exception as e:
        err(message, e)


@bot.message_handler(commands=['removegarden'])
def handle_remove_garden(message):
    try:
        gardens = requests.get(f"{CATALOG_REST_URL}/gardens", timeout=5).json()
        markup  = telebot.types.InlineKeyboardMarkup()
        for g in gardens:
            markup.add(telebot.types.InlineKeyboardButton(
                f"🗑️ {g['gardenName']} ({g['gardenID']})",
                callback_data=f"del_garden_{g['gardenID']}"))
        bot.send_message(message.chat.id, "⚠️ *Which garden do you want to delete?*",
                         reply_markup=markup, parse_mode="Markdown")
    except Exception as e:
        err(message, e)


@bot.callback_query_handler(func=lambda c: c.data.startswith("del_garden_"))
def process_del_garden(call):
    bot.answer_callback_query(call.id)
    garden_id = call.data.replace("del_garden_", "")
    try:
        r = requests.delete(f"{CATALOG_REST_URL}/gardens/{garden_id}", timeout=5)
        r.raise_for_status()
        d = r.json()
        if "error" in d:
            bot.send_message(call.message.chat.id, f"❌ {d['error']}"); return
        # Clear active garden if it was this one
        for cid, grd in list(chat_garden_map.items()):
            if grd == garden_id:
                del chat_garden_map[cid]
        bot.send_message(call.message.chat.id, f"🗑️ Garden `{garden_id}` deleted.", parse_mode="Markdown")
    except Exception as e:
        err(call.message, e)


# ── /status ───────────────────────────────────────────────────────────────────

@bot.message_handler(commands=['status'])
def handle_status(message):
    if not need_garden(message):
        return
    g_id, garden = active_garden(message.chat.id)
    try:
        strategies = requests.get(f"{CATALOG_REST_URL}/strategies", timeout=5).json()
        slots      = garden.get("slots", [])

        # Latest moisture from InfluxDB
        latest = {}
        try:
            hist = requests.get(f"{INFLUX_URL}/history",
                                params={"sensor_type": "soil_moisture", "period": "10m",
                                        "garden_id": g_id}, timeout=5).json()
            for rec in hist:
                sl = rec.get("slot_id", "")
                if sl and rec.get("value") is not None:
                    latest[sl] = rec["value"]
        except Exception:
            pass

        text = f"📈 *Live Status — {garden['gardenName']}*\n\n"
        if not slots:
            text += "⚠️ No slots configured.\n"
        else:
            for s in slots:
                s_id   = s.get("slotID", "?")
                p_id   = s.get("plantID", "")
                p_name = strategies.get(p_id, {}).get("name", p_id) if p_id else "—"
                m_val  = latest.get(s_id)
                m_str  = f"`{round(m_val,1)}%`" if m_val is not None else "`N/A`"
                text  += f"🌱 *{s.get('slotName', s_id)}* (`{s_id}`)\n"
                text  += f"  🌿 Crop: *{p_name}*  💧 Moisture: {m_str}\n\n"

        try:
            stats_r = requests.get(f"{STATISTICS_URL}/api/statistics?period=15m", timeout=5).json()
            stats   = stats_r.get("statistics", {})
            text   += "💾 *Water Savings (last 7d)*\n"
            text   += f"  💧 Saved: `{stats.get('liters_saved','N/A')} L`\n"
            text   += f"  📉 Savings: `{stats.get('savings_percentage','N/A')}%`\n"
            text   += f"  🔁 Activations: `{stats.get('pump_activations_smart','N/A')}`\n"
        except Exception:
            text += "_Water stats temporarily unavailable._\n"

        bot.send_message(message.chat.id, text, parse_mode="Markdown")
    except Exception as e:
        err(message, e)


# ── Crop management ───────────────────────────────────────────────────────────

@bot.message_handler(commands=['crop'])
def handle_crop(message):
    if not need_garden(message):
        return
    g_id, garden = active_garden(message.chat.id)
    slots = garden.get("slots", [])
    if not slots:
        bot.send_message(message.chat.id, "No slots configured in this garden."); return
    markup = telebot.types.InlineKeyboardMarkup()
    for s in slots:
        markup.add(telebot.types.InlineKeyboardButton(
            f"🌱 {s.get('slotName', s['slotID'])} ({s['slotID']})",
            callback_data=f"slot_{g_id}_{s['slotID']}"))
    bot.send_message(message.chat.id, "Which slot do you want to update?", reply_markup=markup)


@bot.callback_query_handler(func=lambda c: c.data.startswith("slot_"))
def handle_slot_selection(call):
    bot.answer_callback_query(call.id)
    # slot_{gardenID}_{slotID}  — slotID may contain underscores
    parts     = call.data.split("_", 2)   # ['slot', gardenID, slotID]
    garden_id = parts[1]
    slot_id   = parts[2]
    try:
        strategies = requests.get(f"{CATALOG_REST_URL}/strategies", timeout=5).json()
        markup = telebot.types.InlineKeyboardMarkup()
        for p_id, info in strategies.items():
            markup.add(telebot.types.InlineKeyboardButton(
                f"🪴 {info['name']}",
                callback_data=f"plant_{garden_id}_{slot_id}_{p_id}"))
        bot.send_message(call.message.chat.id,
                         f"Which crop for slot `{slot_id}`?",
                         reply_markup=markup, parse_mode="Markdown")
    except Exception as e:
        err(call.message, e)


@bot.callback_query_handler(func=lambda c: c.data.startswith("plant_"))
def handle_crop_selection(call):
    # plant_{gardenID}_{slotID}_{plantID}
    parts     = call.data.split("_", 3)
    garden_id = parts[1]
    slot_id   = parts[2]
    plant_id  = parts[3]
    bot.answer_callback_query(call.id, "Updating...")
    try:
        r = requests.put(
            f"{CATALOG_REST_URL}/gardens/{garden_id}/slots/{slot_id}",
            json={"plantID": plant_id}, timeout=5)
        r.raise_for_status()
        strategies = requests.get(f"{CATALOG_REST_URL}/strategies", timeout=5).json()
        name = strategies.get(plant_id, {}).get("name", plant_id)
        bot.send_message(call.message.chat.id,
                         f"✅ Slot `{slot_id}` → *{name}* updated!", parse_mode="Markdown")
    except Exception as e:
        err(call.message, e)


# ── Slots ─────────────────────────────────────────────────────────────────────

@bot.message_handler(commands=['addslot'])
def handle_add_slot(message):
    if not need_garden(message):
        return
    g_id, garden = active_garden(message.chat.id)
    msg = bot.send_message(message.chat.id,
        f"🌱 *Add Slot to {garden['gardenName']}*\n\n"
        "Enter slot coordinate and Crop ID:\n`Coordinate, Crop ID`\n\n"
        "Example: *P2_R1, P3*\n_(Use /garden to see available coordinates)_",
        parse_mode="Markdown")
    bot.register_next_step_handler(msg, lambda m: process_add_slot(m, g_id))


def process_add_slot(message, garden_id):
    try:
        parts = [x.strip() for x in message.text.split(',')]
        if len(parts) != 2:
            bot.send_message(message.chat.id, "❌ Format: `Coordinate, Crop ID`"); return
        slot_id, plant_id = parts
        slot_id = slot_id.upper()
        if not slot_id.startswith("P") or "_R" not in slot_id:
            bot.send_message(message.chat.id, "❌ Slot must be Px_Ry format (e.g. P1_R2)"); return
        payload = {"slotID": slot_id, "plantID": plant_id,
                   "slotName": f"Zone {slot_id}", "status": "active"}
        r = requests.post(f"{CATALOG_REST_URL}/gardens/{garden_id}/slots",
                          json=payload, timeout=5)
        r.raise_for_status()
        d = r.json()
        if "error" in d:
            bot.send_message(message.chat.id, f"❌ {d['error']}"); return
        bot.send_message(message.chat.id,
            f"✅ Slot `{slot_id}` added!\n\n{generate_text_grid(garden_id)}",
            parse_mode="Markdown")
    except Exception as e:
        err(message, e)


@bot.message_handler(commands=['removeslot'])
def handle_remove_slot(message):
    if not need_garden(message):
        return
    g_id, garden = active_garden(message.chat.id)
    slots = garden.get("slots", [])
    if not slots:
        bot.send_message(message.chat.id, "No slots to remove!"); return
    markup = telebot.types.InlineKeyboardMarkup()
    for s in slots:
        markup.add(telebot.types.InlineKeyboardButton(
            f"🗑️ {s.get('slotName', s['slotID'])}",
            callback_data=f"del_slot_{g_id}_{s['slotID']}"))
    bot.send_message(message.chat.id,
                     "⚠️ *Which slot do you want to delete?*",
                     reply_markup=markup, parse_mode="Markdown")


@bot.callback_query_handler(func=lambda c: c.data.startswith("del_slot_"))
def process_del_slot(call):
    bot.answer_callback_query(call.id)
    # del_slot_{gardenID}_{slotID}
    parts     = call.data.split("_", 3)
    garden_id = parts[2]
    slot_id   = parts[3]
    try:
        r = requests.delete(
            f"{CATALOG_REST_URL}/gardens/{garden_id}/slots/{slot_id}", timeout=5)
        r.raise_for_status()
        d = r.json()
        if "error" in d:
            bot.send_message(call.message.chat.id, f"❌ {d['error']}"); return
        bot.send_message(call.message.chat.id,
                         f"🗑️ Slot `{slot_id}` removed.", parse_mode="Markdown")
    except Exception as e:
        err(call.message, e)


# ── Water price ───────────────────────────────────────────────────────────────

@bot.message_handler(commands=['price'])
def handle_price(message):
    try:
        price  = requests.get(f"{CATALOG_REST_URL}/price", timeout=5).json()
        markup = telebot.types.InlineKeyboardMarkup()
        markup.add(telebot.types.InlineKeyboardButton("✏️ Edit Price", callback_data="edit_price"))
        bot.send_message(message.chat.id,
                         f"💶 Current water price: *{price} €/m³*",
                         reply_markup=markup, parse_mode="Markdown")
    except Exception as e:
        err(message, e)


@bot.callback_query_handler(func=lambda c: c.data == "edit_price")
def handle_edit_price(call):
    bot.answer_callback_query(call.id)
    msg = bot.send_message(call.message.chat.id, "Enter the new water price (e.g. 2.5):")
    bot.register_next_step_handler(msg, save_new_price)


def save_new_price(message):
    try:
        price = float(message.text.replace(',', '.'))
        requests.put(f"{CATALOG_REST_URL}/price",
                     json={"NewWaterPricePerM3": price}, timeout=5).raise_for_status()
        bot.send_message(message.chat.id,
                         f"✅ Price updated to *{price} €/m³*!", parse_mode="Markdown")
    except ValueError:
        bot.send_message(message.chat.id, "❌ Invalid number.")
    except Exception as e:
        err(message, e)


# ── Devices ───────────────────────────────────────────────────────────────────

@bot.message_handler(commands=['devices'])
def handle_devices(message):
    if not need_garden(message):
        return
    g_id, garden = active_garden(message.chat.id)
    device     = garden.get("device", {})
    strategies = requests.get(f"{CATALOG_REST_URL}/strategies", timeout=5).json()
    slots      = garden.get("slots", [])
    status_icon = "🟢" if device.get("status") == "active" else "🔴"
    text = (
        f"🖥️ *IoT Device — {garden['gardenName']}*\n\n"
        f"{status_icon} *{device.get('deviceName','—')}* (`{device.get('deviceID','—')}`)\n"
        f"📡 Sensors: {', '.join(device.get('sensors',[]))}\n"
        f"⚙️ Actuators: {', '.join(device.get('actuators',[]))}\n\n*Slots managed:*\n"
    )
    for s in slots:
        p_name = strategies.get(s.get("plantID",""), {}).get("name", "—")
        text += f"  🌱 `{s['slotID']}` · {p_name}\n"
    bot.send_message(message.chat.id, text, parse_mode="Markdown")


@bot.message_handler(commands=['adddevice'])
def handle_add_device(message):
    if not need_garden(message):
        return
    g_id, garden = active_garden(message.chat.id)
    msg = bot.send_message(message.chat.id,
        f"📟 *Register RPi for {garden['gardenName']}*\n\n"
        "Enter: `Device ID, Device Name`\nExample: *RPi_001, GardenGateway_001*",
        parse_mode="Markdown")
    bot.register_next_step_handler(msg, lambda m: process_add_device(m, g_id))


def process_add_device(message, garden_id):
    try:
        parts = [x.strip() for x in message.text.split(',')]
        if len(parts) != 2:
            bot.send_message(message.chat.id, "❌ Format: `Device ID, Device Name`"); return
        device_id, device_name = parts
        payload = {
            "deviceID": device_id, "deviceName": device_name, "status": "active",
            "sensors": ["SoilMoisture", "DHT11"], "actuators": ["MicroServoPump"],
            "config": {"clientID": f"Client_{device_id}"}
        }
        requests.put(f"{CATALOG_REST_URL}/gardens/{garden_id}/device",
                     json=payload, timeout=5).raise_for_status()
        bot.send_message(message.chat.id,
                         f"✅ Device `{device_id}` registered for garden `{garden_id}`!",
                         parse_mode="Markdown")
    except Exception as e:
        err(message, e)


@bot.message_handler(commands=['removedevice'])
def handle_remove_device(message):
    if not need_garden(message):
        return
    g_id, garden = active_garden(message.chat.id)
    device = garden.get("device", {})
    if not device.get("deviceID"):
        bot.send_message(message.chat.id, "No device registered for this garden."); return
    markup = telebot.types.InlineKeyboardMarkup()
    markup.add(telebot.types.InlineKeyboardButton(
        f"🗑️ Remove {device.get('deviceID','device')}", callback_data=f"del_dev_{g_id}"))
    bot.send_message(message.chat.id, "⚠️ *Remove device from garden?*",
                     reply_markup=markup, parse_mode="Markdown")


@bot.callback_query_handler(func=lambda c: c.data.startswith("del_dev_"))
def process_del_device(call):
    bot.answer_callback_query(call.id)
    garden_id = call.data.replace("del_dev_", "")
    try:
        requests.put(f"{CATALOG_REST_URL}/gardens/{garden_id}/device",
                     json={}, timeout=5).raise_for_status()
        bot.send_message(call.message.chat.id,
                         f"🗑️ Device removed from `{garden_id}`.", parse_mode="Markdown")
    except Exception as e:
        err(call.message, e)


# ── Crops / Strategies ────────────────────────────────────────────────────────

@bot.message_handler(commands=['thresholds'])
def handle_thresholds(message):
    try:
        strats = requests.get(f"{CATALOG_REST_URL}/strategies", timeout=5).json()
        text   = "📊 *Available Crops & Thresholds*\n\n"
        for p_id, info in strats.items():
            text += f"🌿 *{info['name']}* (`{p_id}`) — pump below {info['min_moisture_threshold']}%\n"
        bot.send_message(message.chat.id, text, parse_mode="Markdown")
    except Exception as e:
        err(message, e)


@bot.message_handler(commands=['addplant'])
def handle_add_plant(message):
    msg = bot.send_message(message.chat.id,
        "🌿 *Add Crop*\nFormat: `Crop ID, Name, Min Moisture %`\nExample: *P3, Lettuce, 50.0*",
        parse_mode="Markdown")
    bot.register_next_step_handler(msg, process_add_plant)


def process_add_plant(message):
    try:
        parts = [x.strip() for x in message.text.split(',')]
        if len(parts) != 3:
            bot.send_message(message.chat.id, "❌ Need 3 values."); return
        plant_id, name, thr_str = parts
        r = requests.post(f"{CATALOG_REST_URL}/strategies",
                          json={"plantID": plant_id, "name": name,
                                "min_moisture_threshold": float(thr_str)}, timeout=5)
        d = r.json()
        if "error" in d:
            bot.send_message(message.chat.id, f"❌ {d['error']}"); return
        bot.send_message(message.chat.id,
                         f"✅ *{name}* (`{plant_id}`) added.", parse_mode="Markdown")
    except Exception as e:
        err(message, e)


@bot.message_handler(commands=['removeplant'])
def handle_remove_plant(message):
    try:
        strats = requests.get(f"{CATALOG_REST_URL}/strategies", timeout=5).json()
        markup = telebot.types.InlineKeyboardMarkup()
        for p_id, info in strats.items():
            markup.add(telebot.types.InlineKeyboardButton(
                f"🗑️ {info['name']}", callback_data=f"del_plant_{p_id}"))
        bot.send_message(message.chat.id, "⚠️ *Which crop to delete?*",
                         reply_markup=markup, parse_mode="Markdown")
    except Exception as e:
        err(message, e)


@bot.callback_query_handler(func=lambda c: c.data.startswith("del_plant_"))
def process_del_plant(call):
    bot.answer_callback_query(call.id)
    plant_id = call.data.replace("del_plant_", "")
    try:
        r = requests.delete(f"{CATALOG_REST_URL}/strategies/{plant_id}", timeout=5)
        d = r.json()
        if "error" in d:
            bot.send_message(call.message.chat.id, f"❌ {d['error']}"); return
        bot.send_message(call.message.chat.id, f"🗑️ Crop `{plant_id}` removed.", parse_mode="Markdown")
    except Exception as e:
        err(call.message, e)


# ── Users / Profile ───────────────────────────────────────────────────────────

@bot.message_handler(commands=['profile'])
def handle_profile(message):
    try:
        users  = requests.get(f"{CATALOG_REST_URL}/users", timeout=5).json()
        markup = telebot.types.InlineKeyboardMarkup()
        for u in users:
            markup.add(telebot.types.InlineKeyboardButton(
                f"🙋 I am {u['userName']}", callback_data=f"link_user_{u['userID']}"))
        bot.send_message(message.chat.id,
            f"👤 *Your Chat ID:* `{message.chat.id}`\n\nLink profile to receive alerts:",
            reply_markup=markup, parse_mode="Markdown")
    except Exception as e:
        err(message, e)


@bot.callback_query_handler(func=lambda c: c.data.startswith("link_user_"))
def handle_link_user(call):
    bot.answer_callback_query(call.id)
    user_id = call.data.replace("link_user_", "")
    try:
        requests.put(f"{CATALOG_REST_URL}/users",
                     json={"userID": user_id, "telegramChatID": str(call.message.chat.id)},
                     timeout=5).raise_for_status()
        bot.send_message(call.message.chat.id,
                         f"✅ Profile `{user_id}` linked! You will receive alerts here.",
                         parse_mode="Markdown")
    except Exception as e:
        err(call.message, e)


@bot.message_handler(commands=['adduser'])
def handle_add_user(message):
    msg = bot.send_message(message.chat.id,
        "👤 *Add User*\nFormat: `User ID, Name`\nExample: *U_004, Anna*",
        parse_mode="Markdown")
    bot.register_next_step_handler(msg, process_add_user)


def process_add_user(message):
    try:
        parts = [x.strip() for x in message.text.split(',')]
        if len(parts) != 2:
            bot.send_message(message.chat.id, "❌ Format: `User ID, Name`"); return
        user_id, name = parts
        r = requests.post(f"{CATALOG_REST_URL}/users",
                          json={"userID": user_id, "userName": name, "telegramChatID": ""},
                          timeout=5)
        d = r.json()
        if "error" in d:
            bot.send_message(message.chat.id, f"❌ {d['error']}"); return
        bot.send_message(message.chat.id, f"✅ User *{name}* created.", parse_mode="Markdown")
    except Exception as e:
        err(message, e)


@bot.message_handler(commands=['removeuser'])
def handle_remove_user(message):
    try:
        users  = requests.get(f"{CATALOG_REST_URL}/users", timeout=5).json()
        markup = telebot.types.InlineKeyboardMarkup()
        for u in users:
            markup.add(telebot.types.InlineKeyboardButton(
                f"🗑️ {u['userName']}", callback_data=f"del_user_{u['userID']}"))
        bot.send_message(message.chat.id, "⚠️ *Which user to delete?*",
                         reply_markup=markup, parse_mode="Markdown")
    except Exception as e:
        err(message, e)


@bot.callback_query_handler(func=lambda c: c.data.startswith("del_user_"))
def process_del_user(call):
    bot.answer_callback_query(call.id)
    user_id = call.data.replace("del_user_", "")
    try:
        r = requests.delete(f"{CATALOG_REST_URL}/users/{user_id}", timeout=5)
        d = r.json()
        if "error" in d:
            bot.send_message(call.message.chat.id, f"❌ {d['error']}"); return
        bot.send_message(call.message.chat.id, f"🗑️ User `{user_id}` removed.", parse_mode="Markdown")
    except Exception as e:
        err(call.message, e)


# ── Weather location ──────────────────────────────────────────────────────────

def handle_menu_location(message):
    markup = telebot.types.ReplyKeyboardMarkup(resize_keyboard=True, one_time_keyboard=True)
    markup.add(telebot.types.KeyboardButton("📍 Send GPS location", request_location=True))
    bot.send_message(message.chat.id,
        "🌍 *Weather Location*\nPress to send GPS, or type `/city CityName,IT`",
        reply_markup=markup, parse_mode="Markdown")


@bot.message_handler(commands=['city'])
def handle_city(message):
    msg = bot.send_message(message.chat.id,
        "🌍 Enter city (e.g. `Turin,IT`) or coordinates (`45.07,7.68`):",
        parse_mode="Markdown")
    bot.register_next_step_handler(msg, process_city)


def process_city(message):
    try:
        loc = message.text.strip()
        requests.put(f"{CATALOG_REST_URL}/location",
                     json={"location": loc}, timeout=5).raise_for_status()
        bot.send_message(message.chat.id, f"✅ Location set to *{loc}*", parse_mode="Markdown")
    except Exception as e:
        err(message, e)


@bot.message_handler(content_types=['location'])
def handle_gps(message):
    loc = f"{message.location.latitude},{message.location.longitude}"
    try:
        requests.put(f"{CATALOG_REST_URL}/location",
                     json={"location": loc}, timeout=5).raise_for_status()
        bot.send_message(message.chat.id, f"✅ GPS saved: `{loc}`", parse_mode="Markdown",
                         reply_markup=telebot.types.ReplyKeyboardRemove())
    except Exception as e:
        err(message, e)


# ── Garden grid ───────────────────────────────────────────────────────────────

def generate_text_grid(garden_id):
    try:
        garden = requests.get(f"{CATALOG_REST_URL}/gardens/{garden_id}", timeout=5).json()
        grid   = garden.get("grid", {"max_pumps": 4, "max_taps": 4})
        slots  = garden.get("slots", [])
        max_p  = grid.get("max_pumps", 4)
        max_t  = grid.get("max_taps",  4)
        occupied = {s["slotID"] for s in slots if s.get("status") == "active"}
        header = "      " + "".join(f"R{r}  " for r in range(1, max_t+1)) + "\n"
        rows   = "".join(
            f"*P{p}* " + "".join("🌱  " if f"P{p}_R{r}" in occupied else "🟫  "
                                  for r in range(1, max_t+1)) + "\n"
            for p in range(1, max_p+1)
        )
        return header + rows + "\n_Legend:_ 🌱 `Occupied`  |  🟫 `Empty`"
    except Exception as e:
        return f"Grid error: {e}"


@bot.message_handler(commands=['garden'])
def handle_show_garden(message):
    if not need_garden(message):
        return
    g_id, garden = active_garden(message.chat.id)
    bot.send_message(message.chat.id,
        f"🌱 *{garden['gardenName']} — Map:*\n{generate_text_grid(g_id)}",
        parse_mode="Markdown")


@bot.message_handler(commands=['gardensize'])
def handle_set_dimensions(message):
    if not need_garden(message):
        return
    msg = bot.send_message(message.chat.id,
        "📐 *Set Garden Dimensions*\nFormat: `Rows, Taps`\nExample: *3, 4*",
        parse_mode="Markdown")
    bot.register_next_step_handler(msg, process_set_dimensions)


def process_set_dimensions(message):
    if not need_garden(message):
        return
    g_id, _ = active_garden(message.chat.id)
    try:
        parts = [int(x.strip()) for x in message.text.split(',')]
        if len(parts) != 2:
            raise ValueError()
        requests.put(f"{CATALOG_REST_URL}/gardens/{g_id}/grid",
                     json={"max_pumps": parts[0], "max_taps": parts[1]},
                     timeout=5).raise_for_status()
        bot.send_message(message.chat.id,
            f"✅ Dimensions updated!\n{generate_text_grid(g_id)}", parse_mode="Markdown")
    except ValueError:
        bot.send_message(message.chat.id, "❌ Invalid format. Use: `3, 4`")
    except Exception as e:
        err(message, e)


# ── Admin panel ───────────────────────────────────────────────────────────────

def handle_admin_panel(message):
    markup = telebot.types.InlineKeyboardMarkup(row_width=2)
    markup.add(
        telebot.types.InlineKeyboardButton("➕ Add Garden",    callback_data="create_garden"),
        telebot.types.InlineKeyboardButton("➖ Remove Garden", callback_data="menu_removegarden"),
    )
    markup.add(
        telebot.types.InlineKeyboardButton("➕ Add Slot",      callback_data="admin_add_slot"),
        telebot.types.InlineKeyboardButton("➖ Remove Slot",   callback_data="admin_rem_slot"),
    )
    markup.add(
        telebot.types.InlineKeyboardButton("➕ Add Device",    callback_data="admin_add_device"),
        telebot.types.InlineKeyboardButton("➖ Remove Device", callback_data="admin_rem_device"),
    )
    markup.add(
        telebot.types.InlineKeyboardButton("➕ Add Crop",      callback_data="admin_add_plant"),
        telebot.types.InlineKeyboardButton("➖ Remove Crop",   callback_data="admin_rem_plant"),
    )
    markup.add(
        telebot.types.InlineKeyboardButton("➕ Add User",      callback_data="admin_add_user"),
        telebot.types.InlineKeyboardButton("➖ Remove User",   callback_data="admin_rem_user"),
    )
    markup.add(
        telebot.types.InlineKeyboardButton("📐 Garden Size",  callback_data="admin_dimensions"),
        telebot.types.InlineKeyboardButton("🌱 Show Garden",  callback_data="admin_garden"),
    )
    bot.send_message(message.chat.id, "🔧 *Admin Panel*", reply_markup=markup, parse_mode="Markdown")


@bot.callback_query_handler(func=lambda c: c.data.startswith("admin_"))
def handle_admin_callbacks(call):
    bot.answer_callback_query(call.id)
    action = call.data.replace("admin_", "")
    dispatch = {
        "add_slot":   handle_add_slot,  "rem_slot":   handle_remove_slot,
        "add_device": handle_add_device,"rem_device":  handle_remove_device,
        "add_plant":  handle_add_plant, "rem_plant":   handle_remove_plant,
        "add_user":   handle_add_user,  "rem_user":    handle_remove_user,
        "dimensions": handle_set_dimensions, "garden": handle_show_garden,
    }
    fn = dispatch.get(action)
    if fn:
        fn(call.message)


@bot.callback_query_handler(func=lambda c: c.data == "menu_removegarden")
def cb_remove_garden(call):
    bot.answer_callback_query(call.id)
    handle_remove_garden(call.message)


# ── Main ──────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    mqtt_client = mqtt.Client()
    mqtt_client.on_connect = on_connect
    mqtt_client.on_message = on_message
    try:
        mqtt_client.connect(BROKER_IP, 1883, 60)
        mqtt_client.loop_start()
    except Exception as e:
        print(f"⚠️ MQTT unavailable, bot starts anyway. ({e})")
    print("[BOT] Telegram Bot listening...")
    bot.infinity_polling()
