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

# Variabile per salvare l'ID della chat dell'utente (per potergli inviare i messaggi MQTT)
user_chat_id = None 

# --- CALLBACK MQTT (Gestione Notifiche in Ingresso) ---
def on_connect(client, userdata, flags, rc):
    if rc == 0:
        print("[MQTT] Bot connesso al Broker!")
        # Il bot si iscrive ai topic degli allarmi e della pompa
        client.subscribe("garden/alerts/faults")
        client.subscribe("garden/actuators/pump")
    else:
        print(f"[MQTT] Errore di connessione: {rc}")

def on_message(client, userdata, msg):
    global user_chat_id
    payload = msg.payload.decode('utf-8')
    print(f"[MQTT RICEVUTO] {msg.topic}: {payload}")
    
    # Se un utente ha avviato il bot, inoltriamo il messaggio sul suo smartphone
    if user_chat_id:
        if "faults" in msg.topic:
            testo = f"🚨 *ALLARME CRITICO!* 🚨\n{payload}"
        else:
            testo = f"💧 *Aggiornamento Pompa:*\n{payload}"
            
        bot.send_message(user_chat_id, testo, parse_mode="Markdown")

# --- HANDLER TELEGRAM (Gestione Interazione Utente) ---

@bot.message_handler(commands=['start'])
def handle_start(message):
    global user_chat_id
    user_chat_id = message.chat.id  # Salviamo l'ID per le notifiche MQTT
    
    benvenuto = (
        "🌱 *Benvenuto nello Smart Open Air Garden!* 🌱\n\n"
        "Sono il tuo assistente virtuale. Ti invierò notifiche in tempo reale sullo stato della pompa e su eventuali anomalie.\n\n"
        "Usa il comando /coltura per configurare il tipo di pianta che stiamo gestendo."
    )
    bot.reply_to(message, benvenuto, parse_mode="Markdown")

@bot.message_handler(commands=['coltura'])
def handle_coltura(message):
    # Creiamo una tastiera (Inline Keyboard) per far scegliere la coltura
    # STEP 1: Chiedi quale slot aggiornare
    markup = telebot.types.InlineKeyboardMarkup()
    btn_s1 = telebot.types.InlineKeyboardButton("🌱 Orto Nord (S1)", callback_data="slot_S1")
    btn_s2 = telebot.types.InlineKeyboardButton("🌿 Balcone Sud (S2)", callback_data="slot_S2")
    markup.add(btn_s1)
    markup.add(btn_s2)
    
    bot.send_message(message.chat.id, "Quale slot vuoi aggiornare?", reply_markup=markup)

@bot.callback_query_handler(func=lambda call: call.data.startswith("slot_"))
def handle_slot_selection(call):
    # Estrai lo slot selezionato (S1, S2, ecc.)
    selected_slot = call.data.split("_")[1]
    
    # STEP 2: Chiedi quale pianta assegnare
    markup = telebot.types.InlineKeyboardMarkup()
    btn_pomodori = telebot.types.InlineKeyboardButton("🍅 Pomodori", callback_data=f"plant_pomodori_{selected_slot}")
    btn_basilico = telebot.types.InlineKeyboardButton("🌿 Basilico", callback_data=f"plant_basilico_{selected_slot}")
    markup.add(btn_pomodori, btn_basilico)
    
    bot.send_message(call.message.chat.id, f"Quale coltura per {selected_slot}?", reply_markup=markup)    

@bot.callback_query_handler(func=lambda call: call.data.startswith("plant_"))
def handle_crop_selection(call):
   # Estrai la pianta e lo slot selezionati
    parts = call.data.split("_")
    coltura_scelta = parts[1]      # "pomodori" o "basilico"
    selected_slot = parts[2]        # "S1", "S2", ecc. 
    
    # Mappiamo la scelta dell'utente con gli ID presenti nel tuo catalogManager.json
    plant_map = {"pomodori": "P1", "basilico": "P2"}
    plant_id = plant_map.get(coltura_scelta)
    
    bot.answer_callback_query(call.id, f"Hai scelto {coltura_scelta}!")
    
    try:
        # IMPORTANTE: Il catalogo usa PUT per aggiornare e vuole slotID e plantID
        payload = {
            "slotID": selected_slot,        # Usiamo lo slot selezionato
            "plantID": plant_id    # P1 o P2
        }
        # Cambiato da POST a PUT come richiesto dal tuo SlotsEndpoint.PUT
        response = requests.put(STRATEGY_REST_URL, json=payload, timeout=5)
        response.raise_for_status()
        
        bot.send_message(call.message.chat.id, f"✅ Configurazione aggiornata! {selected_slot} ora gestisce: {coltura_scelta}.")
    except Exception as e:
        bot.send_message(call.message.chat.id, f"❌ Errore: {e}")

# --- AVVIO DEL SISTEMA ---
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