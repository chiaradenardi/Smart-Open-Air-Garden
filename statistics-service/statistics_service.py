"""
Statistics & Analytics Service - Chiara
Calcola il risparmio idrico e ricostruisce lo storico della pompa.
Con MQTT integration per Telegram Bot.
"""

from flask import Flask, jsonify, request
import requests
import logging
from datetime import datetime, timedelta
import os
import paho.mqtt.client as mqtt
import json
import threading
from dotenv import load_dotenv

# Configurazione logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Carica le variabili d'ambiente
load_dotenv()

app = Flask(__name__)

# ==================== CONFIGURAZIONE ====================
INFLUX_ADAPTOR_URL = os.getenv("INFLUX_ADAPTOR_URL", "http://influx-adaptor:8081")
BROKER_IP = os.getenv("BROKER_IP", "message-broker")
BROKER_PORT = int(os.getenv("BROKER_PORT", 1883))

MINUTI_PER_ACCENSIONE = 5
LITRI_AL_MINUTO = 2
MINUTI_TIMER_FISSO_AL_GIORNO = 15

# ==================== MQTT CLIENT ====================
mqtt_client = mqtt.Client("statistics-service")

def on_mqtt_connect(client, userdata, flags, rc):
    if rc == 0:
        logger.info("✅ Connesso al Broker MQTT")
    else:
        logger.error(f"❌ Errore MQTT: {rc}")

def on_mqtt_disconnect(client, userdata, rc):
    if rc != 0:
        logger.warning(f"⚠️ Disconnessione MQTT inaspettata: {rc}")

mqtt_client.on_connect = on_mqtt_connect
mqtt_client.on_disconnect = on_mqtt_disconnect

# Connetti al broker in background
def connect_mqtt():
    try:
        mqtt_client.connect(BROKER_IP, BROKER_PORT, keepalive=60)
        mqtt_client.loop_start()
        logger.info(f"📡 MQTT: connessione a {BROKER_IP}:{BROKER_PORT}")
    except Exception as e:
        logger.warning(f"⚠️ MQTT non disponibile: {e}")

# ==================== UTILITY FUNCTIONS ====================

def get_pump_history(period: str = "7d") -> list:
    """Recupera lo storico della pompa da InfluxDB Adaptor via REST."""
    try:
        logger.info(f"📊 Recuperando storico pompa per il periodo: {period}")
        
        url = f"{INFLUX_ADAPTOR_URL}/history"
        params = {
            "sensor_type": "pump_status",
            "period": period
        }
        
        response = requests.get(url, params=params, timeout=5)
        response.raise_for_status()
        
        dati = response.json()
        logger.info(f"✅ Dati ricevuti: {len(dati)} record")
        return dati
        
    except requests.exceptions.RequestException as e:
        logger.warning(f"⚠️ InfluxDB Adaptor non disponibile: {e}")
        logger.warning("📌 Uso dati di test (fallback)")
        
        return [
            {"time": (datetime.now() - timedelta(days=i)).isoformat(), 
             "value": 1, "device": "RPi_001", "sensor": "pump_status"}
            for i in range(5)
        ]


def calculate_water_savings(pump_history: list) -> dict:
    """Calcola il risparmio idrico."""
    accensioni_smart = sum(1 for dato in pump_history if dato.get("value") == 1)
    
    minuti_smart_totali = accensioni_smart * MINUTI_PER_ACCENSIONE
    litri_smart = minuti_smart_totali * LITRI_AL_MINUTO
    
    giorni = 7
    minuti_timer_fisso_totali = MINUTI_TIMER_FISSO_AL_GIORNO * giorni
    litri_fissi = minuti_timer_fisso_totali * LITRI_AL_MINUTO
    
    litri_risparmiati = litri_fissi - litri_smart
    percentuale_risparmio = round((litri_risparmiati / litri_fissi) * 100, 1) if litri_fissi > 0 else 0
    
    return {
        "pump_activations_smart": accensioni_smart,
        "minutes_used_smart": minuti_smart_totali,
        "liters_used_smart": litri_smart,
        "minutes_fixed_timer": minuti_timer_fisso_totali,
        "liters_fixed_timer": litri_fissi,
        "liters_saved": litri_risparmiati,
        "savings_percentage": percentuale_risparmio
    }


def build_full_report(period: str = "7d") -> dict:
    """Costruisce il report completo."""
    pump_history = get_pump_history(period)
    statistics = calculate_water_savings(pump_history)
    
    return {
        "timestamp": datetime.now().isoformat(),
        "period": period,
        "status": "success",
        "statistics": statistics,
        "history_records": len(pump_history),
        "raw_data": pump_history[:10]
    }


def publish_to_mqtt(statistics: dict):
    """Pubblica le statistiche su MQTT per il Telegram Bot."""
    try:
        message = {
            "type": "water_statistics",
            "timestamp": datetime.now().isoformat(),
            "liters_saved": statistics["liters_saved"],
            "savings_percentage": statistics["savings_percentage"],
            "pump_activations": statistics["pump_activations_smart"]
        }
        
        mqtt_client.publish(
            "garden/statistics/water-saved",
            json.dumps(message),
            qos=1
        )
        
        logger.info(f"📤 Statistiche pubblicate su MQTT: {statistics['liters_saved']}L risparmiati")
        
    except Exception as e:
        logger.warning(f"⚠️ Errore nella pubblicazione MQTT: {e}")


# ==================== API REST ENDPOINTS ====================

@app.route('/api/water-saved', methods=['GET'])
def get_water_saved():
    """Endpoint principale - Restituisce il risparmio idrico."""
    period = request.args.get('period', '7d')
    
    logger.info(f"📈 Richiesta dashboard: calcolo risparmio per {period}")
    
    try:
        report = build_full_report(period)
        
        # 🔴 NUOVO: Pubblica su MQTT per Telegram
        publish_to_mqtt(report["statistics"])
        
        return jsonify(report), 200
    
    except Exception as e:
        logger.error(f"❌ Errore nel calcolo: {e}")
        return jsonify({
            "status": "error",
            "message": str(e)
        }), 500


@app.route('/api/pump-history', methods=['GET'])
def get_pump_history_endpoint():
    """Endpoint per recuperare lo storico grezzo della pompa."""
    period = request.args.get('period', '7d')
    
    try:
        history = get_pump_history(period)
        return jsonify({
            "status": "success",
            "period": period,
            "records": len(history),
            "data": history
        }), 200
    
    except Exception as e:
        logger.error(f"❌ Errore nel recupero storico: {e}")
        return jsonify({
            "status": "error",
            "message": str(e)
        }), 500


@app.route('/api/statistics', methods=['GET'])
def get_statistics():
    """Endpoint per recuperare solo le statistiche calcolate."""
    period = request.args.get('period', '7d')
    
    try:
        pump_history = get_pump_history(period)
        statistics = calculate_water_savings(pump_history)
        
        # 🔴 NUOVO: Pubblica su MQTT
        publish_to_mqtt(statistics)
        
        return jsonify({
            "status": "success",
            "timestamp": datetime.now().isoformat(),
            "period": period,
            "statistics": statistics
        }), 200
    
    except Exception as e:
        logger.error(f"❌ Errore nel calcolo statistiche: {e}")
        return jsonify({
            "status": "error",
            "message": str(e)
        }), 500


@app.route('/health', methods=['GET'])
def health_check():
    """Health check per verificare che il servizio sia attivo."""
    return jsonify({
        "service": "statistics-service",
        "status": "running",
        "timestamp": datetime.now().isoformat(),
        "mqtt_connected": mqtt_client.is_connected()
    }), 200


# ==================== MAIN ====================

if __name__ == '__main__':
    logger.info("🚀 Statistics Service avviato")
    logger.info(f"📡 InfluxDB Adaptor: {INFLUX_ADAPTOR_URL}")
    
    # Connetti a MQTT
    connect_mqtt()
    
    # Avvia Flask
    app.run(host='0.0.0.0', port=8082, debug=False)