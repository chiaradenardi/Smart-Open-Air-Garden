
import telebot
import paho.mqtt.client as mqtt
import requests
import json
import os
from dotenv import load_dotenv

# Load environment variables
load_dotenv()


class MQTTHandler:
    """Handles MQTT connections and message processing."""
    
    def __init__(self, broker_ip):
        """Initialize MQTT handler."""
        self.broker_ip = broker_ip
        self.client = mqtt.Client()
        self.client.on_connect = self._on_connect
        self.client.on_message = self._on_message
        self.bot = None
        self.users_url = None
    
    def _on_connect(self, client, userdata, flags, rc):
        """MQTT connection callback."""
        if rc == 0:
            print("[MQTT] Bot connesso al Broker!")
            client.subscribe("garden/alerts/faults")
            client.subscribe("garden/+/pump")
        else:
            print(f"[MQTT] Connection error: {rc}")
    
    def _on_message(self, client, userdata, msg):
        """MQTT message callback - notifies users about alerts and updates."""
        try:
            payload_raw = msg.payload.decode('utf-8')
            print(f"\n[BOT] 📨 Ricevuto su: {msg.topic}")
            
            if "pump" in msg.topic:
                message_text = self._format_pump_message(payload_raw)
            elif "faults" in msg.topic:
                message_text = self._format_fault_message(payload_raw)
            else:
                message_text = f"ℹ️ *System Notification:*\n{payload_raw}"
            
            self._send_to_all_users(message_text)
        
        except Exception as e:
            print(f"[BOT ERROR] Error in on_message: {e}")
    
    def _format_pump_message(self, payload_raw):
        """Format pump status message."""
        try:
            data = json.loads(payload_raw)
            status = data[0].get("v")
            pump_status = "ON ✅" if status == 1 else "OFF ❌"
            device = payload_raw  # Original format
            return f"💧 *Pump Update*\nDevice: `{device}`\nStatus: *{pump_status}*"
        except:
            return f"💧 *Pump Update:*\n{payload_raw}"
    
    def _format_fault_message(self, payload_raw):
        """Format fault alert message."""
        try:
            fault_data = json.loads(payload_raw)
            device = fault_data.get("device", "Unknown")
            desc = fault_data.get("description", "Unknown fault")
            severity = fault_data.get("severity", "HIGH")
            
            return (
                f"🚨 *CRITICAL ALARM!* 🚨\n\n"
                f"📟 *Device:* `{device}`\n"
                f"⚠️ *Severity:* {severity}\n"
                f"📝 *Details:* {desc}"
            )
        except:
            return f"🚨 *CRITICAL ALARM!*\n```text\n{payload_raw}\n```"
    
    def _send_to_all_users(self, message_text):
        """Send message to all registered users."""
        try:
            users = requests.get(self.users_url, timeout=5).json()
            for u in users:
                chat_id = u.get("telegramChatID")
                if chat_id and len(str(chat_id)) > 5:
                    self.bot.send_message(chat_id, message_text, parse_mode="Markdown")
                    print(f"[BOT] Notification sent to {u['userName']}")
        except Exception as e:
            print(f"[BOT ERROR] Error sending to users: {e}")
    
    def connect(self):
        """Connect to MQTT broker."""
        self.client.connect(self.broker_ip, 1883, 60)
        self.client.loop_start()


class TelegramBot:
    """Main Telegram Bot class for Smart Open Air Garden management."""
    
    def __init__(self, token, broker_ip, catalog_url, influx_url, statistics_url):
        """Initialize the Telegram bot."""
        self.bot = telebot.TeleBot(token)
        self.broker_ip = broker_ip
        self.catalog_url = catalog_url
        self.influx_url = influx_url
        self.statistics_url = statistics_url
        self.slots_url = f"{catalog_url}/slots"
        self.user_chat_id = None
        
        # Initialize MQTT handler
        self.mqtt_handler = MQTTHandler(broker_ip)
        self.mqtt_handler.bot = self.bot
        self.mqtt_handler.users_url = f"{catalog_url}/users"
        
        # Register handlers
        self._register_handlers()
    
    def _register_handlers(self):
        """Register all bot message and callback handlers."""
        self.bot.message_handler(commands=['start'])(self.handle_start)
        self.bot.message_handler(commands=['crop'])(self.handle_crop)
        self.bot.message_handler(commands=['city'])(self.handle_city)
        self.bot.message_handler(content_types=['location'])(self.handle_received_location)
        
        self.bot.callback_query_handler(func=lambda call: call.data.startswith("menu_"))(self.handle_main_menu)
        self.bot.callback_query_handler(func=lambda call: call.data.startswith("admin_"))(self.handle_admin_callbacks)
        self.bot.callback_query_handler(func=lambda call: call.data.startswith("slot_"))(self.handle_slot_selection)
        self.bot.callback_query_handler(func=lambda call: call.data.startswith("plant_"))(self.handle_crop_selection)
        self.bot.callback_query_handler(func=lambda call: call.data.startswith("dim_"))(self.handle_dim_callback)
        
        # Register general text handlers for input processing
        self.bot.message_handler(func=lambda msg: True)(self.handle_generic_message)
    
    def handle_start(self, message):
        """Handle /start command - show main menu."""
        self.user_chat_id = message.chat.id
        
        welcome_message = (
            "🌱 *Smart Open Air Garden - Control Panel* 🌱\n\n"
            "Welcome to your IoT ecosystem. From here you can monitor the sensors, "
            "manage irrigation and monitor your consumption.\n\n"
            "Use the buttons below to navigate the system."
        )
        
        markup = telebot.types.InlineKeyboardMarkup(row_width=2)
        
        btn_crop = telebot.types.InlineKeyboardButton("📊 Crop Management", callback_data="menu_crop")
        btn_devices = telebot.types.InlineKeyboardButton("🖥️ Device Status", callback_data="menu_devices")
        markup.add(btn_crop, btn_devices)
        
        btn_price = telebot.types.InlineKeyboardButton("💶 Water Price", callback_data="menu_price")
        btn_thresholds = telebot.types.InlineKeyboardButton("🌿 Available Crops", callback_data="menu_thresholds")
        markup.add(btn_price, btn_thresholds)
        
        btn_status = telebot.types.InlineKeyboardButton("📈 Garden Live Status", callback_data="menu_status")
        markup.add(btn_status)
        
        btn_admin = telebot.types.InlineKeyboardButton("🔧 Admin Management", callback_data="menu_admin")
        btn_location = telebot.types.InlineKeyboardButton("🌍 Set Weather Location", callback_data="menu_location")
        markup.add(btn_admin, btn_location)
        
        btn_profile = telebot.types.InlineKeyboardButton("👤 Link Profile (Receive Notifications)", callback_data="menu_profile")
        markup.add(btn_profile)
        
        self.bot.reply_to(message, welcome_message, reply_markup=markup, parse_mode="Markdown")
    
    def handle_main_menu(self, call):
        """Route menu callbacks to appropriate handlers."""
        self.bot.answer_callback_query(call.id)
        
        command = call.data.split("_")[1]
        
        if command == "crop":
            self.handle_crop(call.message)
        elif command == "devices":
            self.handle_devices(call.message)
        elif command == "price":
            self.handle_price(call.message)
        elif command == "thresholds":
            self.handle_thresholds(call.message)
        elif command == "profile":
            self.handle_profile(call.message)
        elif command == "location":
            self.handle_menu_location(call.message)
        elif command == "admin":
            self.handle_admin_panel(call.message)
        elif command == "status":
            self.handle_status(call.message)
    
    def handle_status(self, message):
        """Display garden live status."""
        try:
            slots = requests.get(self.slots_url, timeout=5).json()
            strategies = requests.get(f"{self.catalog_url}/strategies", timeout=5).json()
            
            try:
                history = requests.get(
                    f"{self.influx_url}/history",
                    params={"sensor_type": "soil_moisture", "period": "10m"},
                    timeout=5
                ).json()
                latest_moisture = {}
                for record in history:
                    dev = record.get("device", "").rstrip("/")
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
                    
                    moisture_val = latest_moisture.get(device_id)
                    moisture_str = f"`{round(moisture_val, 1)}%`" if moisture_val is not None else "`N/A`"
                    
                    message_text += f"🌱 *{s.get('slotName', slot_id)}* (`{slot_id}`)\n"
                    message_text += f"  🖥️ Device: `{device_id}`\n"
                    message_text += f"  🌿 Crop: *{plant_name}*\n"
                    message_text += f"  💧 Last soil moisture: {moisture_str}\n\n"
            
            try:
                stats_res = requests.get(f"{self.statistics_url}/api/statistics?period=15m", timeout=5).json()
                stats = stats_res.get("statistics", {})
                message_text += "💾 *Water Savings (last 7 days)*\n"
                message_text += f"  💧 Litres saved: `{stats.get('liters_saved', 'N/A')} L`\n"
                message_text += f"  📉 Savings: `{stats.get('savings_percentage', 'N/A')}%`\n"
                message_text += f"  🔁 Pump activations: `{stats.get('pump_activations_smart', 'N/A')}`\n"
            except:
                message_text += "ℹ️ _Water savings stats temporarily unavailable._\n"
            
            self.bot.send_message(message.chat.id, message_text, parse_mode="Markdown")
        
        except Exception as e:
            self.bot.send_message(message.chat.id, f"❌ Error fetching garden status: {e}")
    
    def handle_admin_panel(self, message):
        """Display admin panel menu."""
        markup = telebot.types.InlineKeyboardMarkup(row_width=2)
        
        markup.add(
            telebot.types.InlineKeyboardButton("➕ Add Slot", callback_data="admin_add_slot"),
            telebot.types.InlineKeyboardButton("➖ Remove Slot", callback_data="admin_rem_slot")
        )
        markup.add(
            telebot.types.InlineKeyboardButton("➕ Add Device", callback_data="admin_add_device"),
            telebot.types.InlineKeyboardButton("➖ Remove Device", callback_data="admin_rem_device")
        )
        markup.add(
            telebot.types.InlineKeyboardButton("➕ Add Crop", callback_data="admin_add_plant"),
            telebot.types.InlineKeyboardButton("➖ Remove Crop", callback_data="admin_rem_plant")
        )
        markup.add(
            telebot.types.InlineKeyboardButton("➕ Add User", callback_data="admin_add_user"),
            telebot.types.InlineKeyboardButton("➖ Remove User", callback_data="admin_rem_user")
        )
        markup.add(
            telebot.types.InlineKeyboardButton("📐 Garden Size", callback_data="admin_dimensions"),
            telebot.types.InlineKeyboardButton("🌱 Show Garden", callback_data="admin_garden")
        )
        
        message_text = "🔧 *Admin Panel*\n\nChoose the operation you wish to perform:"
        self.bot.send_message(message.chat.id, message_text, reply_markup=markup, parse_mode="Markdown")
    
    def handle_admin_callbacks(self, call):
        """Route admin callbacks to appropriate handlers."""
        self.bot.answer_callback_query(call.id)
        action_str = call.data.replace("admin_", "")
        msg = call.message
        
        handlers = {
            "add_slot": self.handle_add_slot,
            "rem_slot": self.handle_remove_slot,
            "add_device": self.handle_add_device,
            "rem_device": self.handle_remove_device,
            "add_plant": self.handle_add_plant,
            "rem_plant": self.handle_remove_plant,
            "add_user": self.handle_add_user,
            "rem_user": self.handle_remove_user,
            "dimensions": self.handle_set_dimensions,
            "garden": self.handle_show_garden,
        }
        
        handler = handlers.get(action_str)
        if handler:
            handler(msg)
    
    def handle_menu_location(self, message):
        """Display weather location settings menu."""
        markup = telebot.types.ReplyKeyboardMarkup(resize_keyboard=True, one_time_keyboard=True)
        btn_pos = telebot.types.KeyboardButton("📍 Send my GPS location", request_location=True)
        markup.add(btn_pos)
        
        message_text = (
            "🌍 *Weather Location Settings*\n\n"
            "Press the button below to send the system your exact GPS coordinates.\n\n"
            "💡 _If the garden is in another city, simply type the command:_\n"
            "`/city CityName,IT` (e.g. `/city Turin,IT`)"
        )
        self.bot.send_message(message.chat.id, message_text, reply_markup=markup, parse_mode="Markdown")
    
    def handle_crop(self, message):
        """Handle crop management menu."""
        try:
            slots = requests.get(self.slots_url, timeout=5).json()
            
            if not slots:
                self.bot.send_message(message.chat.id, "There are no slots configured in the garden at the moment.")
                return
            
            markup = telebot.types.InlineKeyboardMarkup()
            
            for s in slots:
                slot_id = s.get("slotID")
                slot_name = s.get("slotName", f"Zone {slot_id}")
                btn = telebot.types.InlineKeyboardButton(f"🌱 {slot_name} ({slot_id})", callback_data=f"slot_{slot_id}")
                markup.add(btn)
            
            self.bot.send_message(message.chat.id, "Which slot do you want to update?", reply_markup=markup)
        
        except Exception as e:
            self.bot.send_message(message.chat.id, f"❌ Error contacting the Catalog: {e}")
    
    def handle_slot_selection(self, call):
        """Handle slot selection in crop management."""
        selected_slot = call.data.replace("slot_", "")
        
        try:
            strategies = requests.get(f"{self.catalog_url}/strategies", timeout=5).json()
            
            markup = telebot.types.InlineKeyboardMarkup()
            for plant_id, info in strategies.items():
                btn = telebot.types.InlineKeyboardButton(f"🪴 {info['name']}", callback_data=f"plant_{plant_id}_{selected_slot}")
                markup.add(btn)
            
            self.bot.send_message(call.message.chat.id, f"Which crop for slot {selected_slot}?", reply_markup=markup)
        
        except Exception as e:
            self.bot.send_message(call.message.chat.id, f"❌ Error loading crops: {e}")
    
    def handle_crop_selection(self, call):
        """Handle crop selection and association."""
        stringa_dati = call.data.replace("plant_", "")
        pezzi = stringa_dati.split("_")
        
        if len(pezzi) >= 2:
            plant_id = pezzi[0]
            slot_id = "_".join(pezzi[1:])
            
            try:
                payload = {"plantID": plant_id}
                r = requests.put(
                    f"{self.catalog_url}/slots/{slot_id}",
                    json=payload,
                    timeout=5
                )
                
                if r.status_code == 200:
                    self.bot.send_message(call.message.chat.id, f"✅ Slot {slot_id} updated successfully!")
                else:
                    self.bot.send_message(call.message.chat.id, f"❌ Error updating slot: {r.text}")
            
            except Exception as e:
                self.bot.send_message(call.message.chat.id, f"❌ Error: {e}")
    
    # Placeholder methods for admin operations
    def handle_add_slot(self, message):
        """Handle add slot operation."""
        self.bot.send_message(message.chat.id, "Add Slot functionality - To be implemented")
    
    def handle_remove_slot(self, message):
        """Handle remove slot operation."""
        self.bot.send_message(message.chat.id, "Remove Slot functionality - To be implemented")
    
    def handle_add_device(self, message):
        """Handle add device operation."""
        self.bot.send_message(message.chat.id, "Add Device functionality - To be implemented")
    
    def handle_remove_device(self, message):
        """Handle remove device operation."""
        self.bot.send_message(message.chat.id, "Remove Device functionality - To be implemented")
    
    def handle_add_plant(self, message):
        """Handle add plant/crop operation."""
        self.bot.send_message(message.chat.id, "Add Plant functionality - To be implemented")
    
    def handle_remove_plant(self, message):
        """Handle remove plant/crop operation."""
        self.bot.send_message(message.chat.id, "Remove Plant functionality - To be implemented")
    
    def handle_price(self, message):
        """Handle water price menu."""
        self.bot.send_message(message.chat.id, "Water Price management - To be implemented")
    
    def handle_devices(self, message):
        """Handle device status menu."""
        self.bot.send_message(message.chat.id, "Device Status - To be implemented")
    
    def handle_thresholds(self, message):
        """Handle available crops/thresholds menu."""
        self.bot.send_message(message.chat.id, "Available Crops - To be implemented")
    
    def handle_profile(self, message):
        """Handle user profile linking."""
        self.bot.send_message(message.chat.id, "Profile Management - To be implemented")
    
    def handle_add_user(self, message):
        """Handle add user operation."""
        self.bot.send_message(message.chat.id, "Add User functionality - To be implemented")
    
    def handle_remove_user(self, message):
        """Handle remove user operation."""
        self.bot.send_message(message.chat.id, "Remove User functionality - To be implemented")
    
    def handle_city(self, message):
        """Handle city command for location setting."""
        self.bot.send_message(message.chat.id, "City setting - To be implemented")
    
    def handle_received_location(self, message):
        """Handle received GPS location."""
        self.bot.send_message(message.chat.id, "Location received - To be implemented")
    
    def handle_set_dimensions(self, message):
        """Handle garden dimensions setting."""
        self.bot.send_message(message.chat.id, "Garden dimensions - To be implemented")
    
    def handle_dim_callback(self, call):
        """Handle garden dimension callbacks."""
        self.bot.answer_callback_query(call.id)
        self.bot.send_message(call.message.chat.id, "Dimension callback - To be implemented")
    
    def handle_show_garden(self, message):
        """Display garden visualization."""
        self.bot.send_message(message.chat.id, "Garden visualization - To be implemented")
    
    def handle_generic_message(self, message):
        """Handle generic messages."""
        pass
    
    def start_polling(self):
        """Start the bot polling."""
        print("🚀 Telegram Bot started - polling for updates")
        self.mqtt_handler.connect()
        self.bot.infinity_polling()
    
    def stop(self):
        """Stop the bot."""
        self.mqtt_handler.client.loop_stop()


def main():
    """Main entry point."""
    # Configuration from environment
    token = os.getenv("TELEGRAM_TOKEN")
    broker_ip = os.getenv("BROKER_IP", "message-broker")
    catalog_url = os.getenv('CATALOG_URL', 'http://service-catalog:8080')
    influx_url = os.getenv("INFLUX_ADAPTOR_URL", "http://influx-adaptor:8081")
    statistics_url = os.getenv('STATISTICS_URL', 'http://statistics-service:8082')
    
    # Create and start bot
    bot = TelegramBot(token, broker_ip, catalog_url, influx_url, statistics_url)
    bot.start_polling()


if __name__ == "__main__":
    main()
