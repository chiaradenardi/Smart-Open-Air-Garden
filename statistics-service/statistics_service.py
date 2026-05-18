"""
Statistics & Analytics Service
Calculates how much water we save and tracks the pump history.
It also connects to MQTT to send this data to the Telegram Bot.
"""

import cherrypy
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
    """This class helps the statistics service talk to the MQTT broker."""
    
    def __init__(self, broker_ip, broker_port):
        """Prepares the MQTT client with the broker address."""
        self.broker_ip = broker_ip
        self.broker_port = broker_port
        self.client = mqtt.Client("statistics-service")
        self.client.on_connect = self._on_connect
        self.client.on_disconnect = self._on_disconnect
    
    def _on_connect(self, client, userdata, flags, rc):
        """Checks if the connection was successful and prints a message."""
        if rc == 0:
            logger.info("✅ Connected to MQTT Broker")
        else:
            logger.error(f"❌ MQTT Error: {rc}")
    
    def _on_disconnect(self, client, userdata, rc):
        """Prints a warning if the connection drops."""
        if rc != 0:
            logger.warning(f"⚠️ Unexpected MQTT disconnection: {rc}")
    
    def connect(self):
        """Tries to connect to the broker and starts the background loop."""
        try:
            self.client.connect(self.broker_ip, self.broker_port, keepalive=60)
            self.client.loop_start()
            logger.info(f"📡 MQTT: connection to {self.broker_ip}:{self.broker_port}")
        except Exception as e:
            logger.warning(f"⚠️ MQTT not available: {e}")
    
    def publish(self, topic, message, qos=1):
        """Sends a message to a specific topic."""
        try:
            self.client.publish(topic, message, qos=qos)
        except Exception as e:
            logger.warning(f"⚠️ Error publishing on MQTT: {e}")
    
    def is_connected(self):
        """Returns True if the client is currently connected to the broker."""
        return self.client.is_connected()


class StatisticsService:
    """This class calculates how many liters of water and money we saved."""
    
    # Constants
    MINUTES_PER_PUMP = 5
    LITERS_PER_MINUTE = 2
    MINUTES_FIXED_TIMER_DAY = 120
    DEFAULT_PRICE_PER_LITER = 0.004
    
    def __init__(self, influx_url, broker_ip, broker_port, catalog_url):
        """Saves the URLs and starts the MQTT connection."""
        self.influx_url = influx_url
        self.catalog_url = catalog_url
        self.mqtt = MQTTConnection(broker_ip, broker_port)
        self.mqtt.connect()
    
    def get_price_per_liter(self):
        """Gets the water price from the catalog so we can calculate the money saved."""
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
    
    def get_pump_history(self, period: str = "7d"):
        """Asks the InfluxDB database for the history of the pump."""
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
    
    def calculate_water_savings(self, pump_history: list):
        """Does the math to find out how much water we saved compared to a normal timer."""
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
    
    def build_full_report(self, period: str = "7d"):
        """Creates a big dictionary with all the stats and the raw data."""
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
        """Sends the final stats to the Telegram bot using MQTT."""
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
    
    def get_mqtt_status(self):
        """Returns if the MQTT is working, useful for the health check."""
        return self.mqtt.is_connected()


# ==================== CHERRYPY APP SETUP ====================

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

class WaterSavedEndpoint:
    """This web endpoint returns the water savings report."""
    exposed = True
    def GET(self, period='15m', **kwargs):
        """Handles GET requests to calculate savings."""
        logger.info(f"📈 Dashboard request: calculating savings for {period}")
        try:
            report = statistics_service.build_full_report(period)
            statistics_service.publish_statistics(report["statistics"])
            return json.dumps(report).encode('utf-8')
        except Exception as e:
            logger.error(f"❌ Error in calculation: {e}")
            cherrypy.response.status = 500
            return json.dumps({"status": "error", "message": str(e)}).encode('utf-8')

class PumpHistoryEndpoint:
    """This web endpoint returns just the raw pump history data."""
    exposed = True
    def GET(self, period='15m', **kwargs):
        """Handles GET requests for history."""
        try:
            history = statistics_service.get_pump_history(period)
            return json.dumps({
                "status": "success",
                "period": period,
                "records": len(history),
                "data": history
            }).encode('utf-8')
        except Exception as e:
            logger.error(f"❌ Error in pump history retrieval: {e}")
            cherrypy.response.status = 500
            return json.dumps({"status": "error", "message": str(e)}).encode('utf-8')

class StatisticsEndpoint:
    """This web endpoint returns just the calculated statistics."""
    exposed = True
    def GET(self, period='15m', **kwargs):
        """Handles GET requests for statistics."""
        try:
            pump_history = statistics_service.get_pump_history(period)
            statistics = statistics_service.calculate_water_savings(pump_history)
            statistics_service.publish_statistics(statistics)
            return json.dumps({
                "status": "success",
                "timestamp": datetime.now().isoformat(),
                "period": period,
                "statistics": statistics
            }).encode('utf-8')
        except Exception as e:
            logger.error(f"❌ Error in statistics calculation: {e}")
            cherrypy.response.status = 500
            return json.dumps({"status": "error", "message": str(e)}).encode('utf-8')

class HealthEndpoint:
    """This web endpoint is used to check if the service is alive and working."""
    exposed = True
    def GET(self, **kwargs):
        """Returns a simple JSON saying everything is OK."""
        return json.dumps({
            "service": "statistics-service",
            "status": "running",
            "timestamp": datetime.now().isoformat(),
            "mqtt_connected": statistics_service.get_mqtt_status()
        }).encode('utf-8')

# ==================== MAIN ====================

if __name__ == '__main__':
    logger.info("🚀 Statistics Service started")
    logger.info(f"📡 InfluxDB Adaptor: {INFLUX_ADAPTOR_URL}")
    
    conf = {
        '/': {
            'request.dispatch': cherrypy.dispatch.MethodDispatcher(),
            'tools.sessions.on': True,
            'tools.response_headers.on': True,
            'tools.response_headers.headers': [('Content-Type', 'application/json')]
        }
    }
    
    cherrypy.tree.mount(WaterSavedEndpoint(), '/api/water-saved', conf)
    cherrypy.tree.mount(PumpHistoryEndpoint(), '/api/pump-history', conf)
    cherrypy.tree.mount(StatisticsEndpoint(), '/api/statistics', conf)
    cherrypy.tree.mount(HealthEndpoint(), '/health', conf)
    
    cherrypy.config.update({
        'server.socket_host': '0.0.0.0',
        'server.socket_port': 8082
    })
    
    cherrypy.engine.start()
    cherrypy.engine.block()