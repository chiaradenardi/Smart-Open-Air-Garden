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

# Configuration logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Load environment variables
load_dotenv()

app = Flask(__name__)

# ==================== CONFIGURATION ====================
INFLUX_ADAPTOR_URL = os.getenv("INFLUX_ADAPTOR_URL", "http://influx-adaptor:8081")
BROKER_IP = os.getenv("BROKER_IP", "message-broker")
BROKER_PORT = int(os.getenv("BROKER_PORT", 1883))

MINUTES_PER_PUMP = 5
LITERS_PER_MINUTE = 2
MINUTES_FIXED_TIMER_DAY = 120
PRICE_PER_LITER = 0.004 

# ==================== MQTT CLIENT ====================
mqtt_client = mqtt.Client("statistics-service")

def on_mqtt_connect(client, userdata, flags, rc):
    if rc == 0:
        logger.info("✅ Connected to MQTT Broker")
    else:
        logger.error(f"❌ MQTT Error: {rc}")

def on_mqtt_disconnect(client, userdata, rc):
    if rc != 0:
        logger.warning(f"⚠️ Unexpected MQTT disconnection: {rc}")

mqtt_client.on_connect = on_mqtt_connect
mqtt_client.on_disconnect = on_mqtt_disconnect

# Connect to broker in background
def connect_mqtt():
    try:
        mqtt_client.connect(BROKER_IP, BROKER_PORT, keepalive=60)
        mqtt_client.loop_start()
        logger.info(f"📡 MQTT: connection to {BROKER_IP}:{BROKER_PORT}")
    except Exception as e:
        logger.warning(f"⚠️ MQTT not available: {e}")

# ==================== UTILITY FUNCTIONS ====================

def get_pump_history(period: str = "7d") -> list:
    """Retrieving pump history from InfluxDB Adaptor via REST."""
    try:
        logger.info(f"📊 Retrieving pump history for period: {period}")
        
        url = f"{INFLUX_ADAPTOR_URL}/history"
        params = {
            "sensor_type": "pump_status",
            "period": period
        }
        
        response = requests.get(url, params=params, timeout=5)
        response.raise_for_status()
        
        dati = response.json()
        logger.info(f"✅ Data received: {len(dati)} records")
        return dati
        
    except requests.exceptions.RequestException as e:
        logger.warning(f"⚠️ InfluxDB Adaptor not available: {e}")
        logger.warning("📌 Using test data (fallback)")
        
        return [
            {"time": (datetime.now() - timedelta(days=i)).isoformat(), 
             "value": 1, "device": "RPi_001", "sensor": "pump_status"}
            for i in range(5)
        ]


def calculate_water_savings(pump_history: list) -> dict:
    """Calculates water savings and economic savings."""
    pump_activations_smart = sum(1 for dato in pump_history if dato.get("value") == 1)
    
    minutes_used_smart = pump_activations_smart * MINUTES_PER_PUMP
    liters_used_smart = minutes_used_smart * LITERS_PER_MINUTE
    
    days = 7
    minutes_fixed_timer_total = MINUTES_FIXED_TIMER_DAY * days
    liters_fixed = minutes_fixed_timer_total * LITERS_PER_MINUTE
    
    liters_saved = liters_fixed - liters_used_smart
    savings_percentage = round((liters_saved / liters_fixed) * 100, 1) if liters_fixed > 0 else 0
    
    euros_saved = round(liters_saved * PRICE_PER_LITER, 2)
    
    return {
        "pump_activations_smart": pump_activations_smart,
        "minutes_used_smart": minutes_used_smart,
        "liters_used_smart": liters_used_smart,
        "minutes_fixed_timer": minutes_fixed_timer_total,
        "liters_fixed_timer": liters_fixed,
        "liters_saved": liters_saved,
        "savings_percentage": savings_percentage,
        "euros_saved": euros_saved,
        "cost_per_liter": PRICE_PER_LITER
    }


def build_full_report(period: str = "7d") -> dict:
    """Building the complete report."""
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
    """Publishes statistics to MQTT for the Telegram Bot."""
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
        
        logger.info(f"📤 Statistics published on MQTT: {statistics['liters_saved']}L saved")
        
    except Exception as e:
        logger.warning(f"⚠️ Error publishing on MQTT: {e}")


# ==================== API REST ENDPOINTS ====================

@app.route('/api/water-saved', methods=['GET'])
def get_water_saved():
    """Main endpoint - Returns the water savings."""
    period = request.args.get('period', '15m')
    
    logger.info(f"📈 Dashboard request: calculating savings for {period}")
    
    try:
        report = build_full_report(period)
        
        # Publish to MQTT for Telegram  
        publish_to_mqtt(report["statistics"])
        
        return jsonify(report), 200
    
    except Exception as e:
        logger.error(f"❌ Error in calculation: {e}")
        return jsonify({
            "status": "error",
            "message": str(e)
        }), 500


@app.route('/api/pump-history', methods=['GET'])
def get_pump_history_endpoint():
    """Endpoint to retrieve the raw pump history."""
    period = request.args.get('period', '15m')
    
    try:
        history = get_pump_history(period)
        return jsonify({
            "status": "success",
            "period": period,
            "records": len(history),
            "data": history
        }), 200
    
    except Exception as e:
        logger.error(f"❌ Error in pump history retrieval: {e}")
        return jsonify({
            "status": "error",
            "message": str(e)
        }), 500


@app.route('/api/statistics', methods=['GET'])
def get_statistics():
    """Endpoint to retrieve only the calculated statistics."""
    period = request.args.get('period', '15m')
    
    try:
        pump_history = get_pump_history(period)
        statistics = calculate_water_savings(pump_history)
        
        # Publish to MQTT for Telegram  
        publish_to_mqtt(statistics)
        
        return jsonify({
            "status": "success",
            "timestamp": datetime.now().isoformat(),
            "period": period,
            "statistics": statistics
        }), 200
    
    except Exception as e:
        logger.error(f"❌ Error in statistics calculation: {e}")
        return jsonify({
            "status": "error",
            "message": str(e)
        }), 500


@app.route('/health', methods=['GET'])
def health_check():
    """Health check to verify that the service is active."""
    return jsonify({
        "service": "statistics-service",
        "status": "running",
        "timestamp": datetime.now().isoformat(),
        "mqtt_connected": mqtt_client.is_connected()
    }), 200


# ==================== MAIN ====================

if __name__ == '__main__':
    logger.info("🚀 Statistics Service started")
    logger.info(f"📡 InfluxDB Adaptor: {INFLUX_ADAPTOR_URL}")
    
    # Connect to MQTT
    connect_mqtt()
    
    # Start Flask
    app.run(host='0.0.0.0', port=8082, debug=False)