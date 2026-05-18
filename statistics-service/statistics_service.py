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
import time
import threading
from dotenv import load_dotenv

# Configuration logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Load environment variables
load_dotenv()


class MQTTConnection:
    """Manages MQTT connection and callbacks."""
    
    def __init__(self, broker_ip, broker_port):
        """Initialize MQTT connection."""
        self.broker_ip = broker_ip
        self.broker_port = broker_port
        self.client = mqtt.Client("statistics-service")
        self.client.on_connect = self._on_connect
        self.client.on_disconnect = self._on_disconnect
    
    def _on_connect(self, client, userdata, flags, rc):
        """Handle MQTT connection."""
        if rc == 0:
            logger.info("✅ Connected to MQTT Broker")
        else:
            logger.error(f"❌ MQTT Error: {rc}")
    
    def _on_disconnect(self, client, userdata, rc):
        """Handle MQTT disconnection."""
        if rc != 0:
            logger.warning(f"⚠️ Unexpected MQTT disconnection: {rc}")
    
    def connect(self):
        """Connect to broker in background."""
        try:
            self.client.connect(self.broker_ip, self.broker_port, keepalive=60)
            self.client.loop_start()
            logger.info(f"📡 MQTT: connection to {self.broker_ip}:{self.broker_port}")
        except Exception as e:
            logger.warning(f"⚠️ MQTT not available: {e}")
    
    def publish(self, topic, message, qos=1):
        """Publish message to MQTT topic."""
        try:
            self.client.publish(topic, message, qos=qos)
        except Exception as e:
            logger.warning(f"⚠️ Error publishing on MQTT: {e}")
    
    def is_connected(self):
        """Check if MQTT client is connected."""
        return self.client.is_connected()


class StatisticsService:
    """Service for calculating and reporting water savings statistics."""
    
    # Constants
    MINUTES_PER_PUMP = 5
    LITERS_PER_MINUTE = 2
    MINUTES_FIXED_TIMER_DAY = 120
    DEFAULT_PRICE_PER_LITER = 0.004
    
    def __init__(self, influx_url, broker_ip, broker_port, catalog_url):
        """Initialize the statistics service."""
        self.influx_url = influx_url
        self.catalog_url = catalog_url
        self.mqtt = MQTTConnection(broker_ip, broker_port)
        self.mqtt.connect()
    
    def get_price_per_liter(self) -> float:
        """Fetch the current water price from the Service Catalog."""
        try:
            response = requests.get(f"{self.catalog_url}/price", timeout=3)
            response.raise_for_status()
            price_per_m3 = response.json()
            price_per_liter = price_per_m3 / 1000.0
            logger.info(f"💧 Water price fetched from Catalog: {price_per_m3} €/m³ → {price_per_liter} €/L")
            return price_per_liter
        except Exception as e:
            logger.warning(f"⚠️ Could not fetch price from Catalog: {e}. Using default: {self.DEFAULT_PRICE_PER_LITER} €/L")
            return self.DEFAULT_PRICE_PER_LITER
    
    def get_pump_history(self, period: str = "7d") -> list:
        """Retrieve pump history from InfluxDB Adaptor via REST."""
        try:
            logger.info(f"📊 Retrieving pump history for period: {period}")
            
            url = f"{self.influx_url}/history"
            params = {
                "sensor_type": "pump_status",
                "period": period
            }
            
            response = requests.get(url, params=params, timeout=5)
            response.raise_for_status()
            
            data = response.json()
            logger.info(f"✅ Data received: {len(data)} records")
            return data
            
        except requests.exceptions.RequestException as e:
            logger.warning(f"⚠️ InfluxDB Adaptor not available: {e}")
            logger.warning("📌 Using test data (fallback)")
            
            return [
                {"time": (datetime.now() - timedelta(days=i)).isoformat(),
                 "value": 1, "garden_id": "G_001", "slot_id": "P1_R1", "sensor": "pump_status"}
                for i in range(5)
            ]
    
    def calculate_water_savings(self, pump_history: list) -> dict:
        """Calculate water savings and economic savings."""
        pump_activations_smart = sum(1 for dato in pump_history if dato.get("value") == 1)
        
        minutes_used_smart = pump_activations_smart * self.MINUTES_PER_PUMP
        liters_used_smart = minutes_used_smart * self.LITERS_PER_MINUTE
        
        days = 7
        minutes_fixed_timer_total = self.MINUTES_FIXED_TIMER_DAY * days
        liters_fixed = minutes_fixed_timer_total * self.LITERS_PER_MINUTE
        
        liters_saved = liters_fixed - liters_used_smart
        savings_percentage = round((liters_saved / liters_fixed) * 100, 1) if liters_fixed > 0 else 0
        
        price_per_liter = self.get_price_per_liter()
        euros_saved = round(liters_saved * price_per_liter, 2)
        
        return {
            "pump_activations_smart": pump_activations_smart,
            "minutes_used_smart": minutes_used_smart,
            "liters_used_smart": liters_used_smart,
            "minutes_fixed_timer": minutes_fixed_timer_total,
            "liters_fixed_timer": liters_fixed,
            "liters_saved": liters_saved,
            "savings_percentage": savings_percentage,
            "euros_saved": euros_saved,
            "cost_per_liter": price_per_liter
        }
    
    def build_full_report(self, period: str = "7d") -> dict:
        """Build the complete report."""
        pump_history = self.get_pump_history(period)
        statistics = self.calculate_water_savings(pump_history)
        
        return {
            "timestamp": datetime.now().isoformat(),
            "period": period,
            "status": "success",
            "statistics": statistics,
            "history_records": len(pump_history),
            "raw_data": pump_history[:10]
        }
    
    def publish_statistics(self, statistics: dict):
        """Publish statistics to MQTT for the Telegram Bot."""
        try:
            message = {
                "type": "water_statistics",
                "timestamp": int(time.time()),
                "liters_saved": statistics["liters_saved"],
                "savings_percentage": statistics["savings_percentage"],
                "pump_activations": statistics["pump_activations_smart"]
            }
            
            self.mqtt.publish(
                "garden/statistics/water-saved",
                json.dumps(message),
                qos=1
            )
            
            logger.info(f"📤 Statistics published on MQTT: {statistics['liters_saved']}L saved")
            
        except Exception as e:
            logger.warning(f"⚠️ Error publishing on MQTT: {e}")
    
    def get_mqtt_status(self) -> bool:
        """Get MQTT connection status."""
        return self.mqtt.is_connected()


# ==================== FLASK APP SETUP ====================

app = Flask(__name__)

# Configuration
INFLUX_ADAPTOR_URL = os.getenv("INFLUX_ADAPTOR_URL", "http://influx-adaptor:8081")
BROKER_IP = os.getenv("BROKER_IP", "message-broker")
BROKER_PORT = int(os.getenv("BROKER_PORT", 1883))
CATALOG_URL = os.getenv("CATALOG_URL", "http://service-catalog:8080")

# Initialize service
statistics_service = StatisticsService(
    INFLUX_ADAPTOR_URL,
    BROKER_IP,
    BROKER_PORT,
    CATALOG_URL
)


# ==================== API REST ENDPOINTS ====================

@app.route('/api/water-saved', methods=['GET'])
def get_water_saved():
    """Main endpoint - Returns the water savings."""
    period = request.args.get('period', '15m')
    
    logger.info(f"📈 Dashboard request: calculating savings for {period}")
    
    try:
        report = statistics_service.build_full_report(period)
        
        # Publish to MQTT for Telegram
        statistics_service.publish_statistics(report["statistics"])
        
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
        history = statistics_service.get_pump_history(period)
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
        pump_history = statistics_service.get_pump_history(period)
        statistics = statistics_service.calculate_water_savings(pump_history)
        
        # Publish to MQTT for Telegram
        statistics_service.publish_statistics(statistics)
        
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
        "mqtt_connected": statistics_service.get_mqtt_status()
    }), 200


# ==================== MAIN ====================

if __name__ == '__main__':
    logger.info("🚀 Statistics Service started")
    logger.info(f"📡 InfluxDB Adaptor: {INFLUX_ADAPTOR_URL}")
    
    # Start Flask
    app.run(host='0.0.0.0', port=8082, debug=False)