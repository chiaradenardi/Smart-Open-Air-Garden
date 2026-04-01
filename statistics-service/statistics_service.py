"""
Statistics & Analytics Service - Chiara
Calcola il risparmio idrico e ricostruisce lo storico della pompa.
"""

from flask import Flask, jsonify, request
import requests
import logging
from datetime import datetime, timedelta
import os
from dotenv import load_dotenv

# Configurazione logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Carica le variabili d'ambiente
load_dotenv()

app = Flask(__name__)

# ==================== CONFIGURAZIONE ====================
# URL dell'InfluxDB Adaptor (Natalia) per recuperare i dati storici
INFLUX_ADAPTOR_URL = os.getenv("INFLUX_ADAPTOR_URL", "http://influx-adaptor:8081")

# Parametri fissi per il calcolo del risparmio
MINUTI_PER_ACCENSIONE = 5  # Ogni "1" della pompa = 5 minuti di irrigazione
LITRI_AL_MINUTO = 2  # Pompa eroga 2 litri al minuto
MINUTI_TIMER_FISSO_AL_GIORNO = 15  # Timer "stupido" irrigherebbe 15 min al giorno

# ==================== UTILITY FUNCTIONS ====================

def get_pump_history(period: str = "7d") -> list:
    """
    Recupera lo storico della pompa da InfluxDB Adaptor via REST.
    
    Args:
        period: periodo di tempo (es. "7d", "24h", "30d")
    
    Returns:
        Lista di dizionari con i dati della pompa
    """
    try:
        logger.info(f"📊 Recuperando storico pompa per il periodo: {period}")
        
        # Costruisci la richiesta REST a Natalia
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
        
        # FALLBACK: Dati di test per non bloccare lo sviluppo
        return [
            {"time": (datetime.now() - timedelta(days=i)).isoformat(), 
             "value": 1, "device": "RPi_001", "sensor": "pump_status"}
            for i in range(5)
        ]


def calculate_water_savings(pump_history: list) -> dict:
    """
    Calcola il risparmio idrico comparando la strategia smart con un timer fisso.
    
    Args:
        pump_history: Lista di record storici della pompa
    
    Returns:
        Dizionario con i dettagli del calcolo
    """
    # 1. Conta quante volte la pompa si è accesa (value == 1)
    accensioni_smart = sum(1 for dato in pump_history if dato.get("value") == 1)
    
    # 2. Calcola i litri usati dalla strategia SMART
    minuti_smart_totali = accensioni_smart * MINUTI_PER_ACCENSIONE
    litri_smart = minuti_smart_totali * LITRI_AL_MINUTO
    
    # 3. Calcola i litri che avrebbe usato un timer FISSO (stupido)
    # Assumiamo il periodo dei dati sia di 7 giorni per default
    giorni = 7  # TODO: calcolare dinamicamente dal primo e ultimo timestamp
    minuti_timer_fisso_totali = MINUTI_TIMER_FISSO_AL_GIORNO * giorni
    litri_fissi = minuti_timer_fisso_totali * LITRI_AL_MINUTO
    
    # 4. Calcola il risparmio
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
    """
    Costruisce il report completo con storico e statistiche.
    """
    pump_history = get_pump_history(period)
    statistics = calculate_water_savings(pump_history)
    
    return {
        "timestamp": datetime.now().isoformat(),
        "period": period,
        "status": "success",
        "statistics": statistics,
        "history_records": len(pump_history),
        "raw_data": pump_history[:10]  # Mostri i primi 10 record per debug
    }


# ==================== API REST ENDPOINTS ====================

@app.route('/api/water-saved', methods=['GET'])
def get_water_saved():
    """
    Endpoint principale per Node-RED.
    Restituisce il risparmio idrico degli ultimi 7 giorni.
    
    Parametri query opzionali:
        - period: intervallo di tempo (es. "7d", "24h", "30d")
    """
    period = request.args.get('period', '7d')
    
    logger.info(f"📈 Richiesta dashboard: calcolo risparmio per {period}")
    
    try:
        report = build_full_report(period)
        return jsonify(report), 200
    
    except Exception as e:
        logger.error(f"❌ Errore nel calcolo: {e}")
        return jsonify({
            "status": "error",
            "message": str(e)
        }), 500


@app.route('/api/pump-history', methods=['GET'])
def get_pump_history_endpoint():
    """
    Endpoint per recuperare lo storico grezzo della pompa.
    
    Parametri query opzionali:
        - period: intervallo di tempo
    """
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
    """
    Endpoint per recuperare solo le statistiche calcolate.
    
    Parametri query opzionali:
        - period: intervallo di tempo
    """
    period = request.args.get('period', '7d')
    
    try:
        pump_history = get_pump_history(period)
        statistics = calculate_water_savings(pump_history)
        
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
    """
    Health check per verificare che il servizio sia attivo.
    """
    return jsonify({
        "service": "statistics-service",
        "status": "running",
        "timestamp": datetime.now().isoformat()
    }), 200


# ==================== MAIN ====================

if __name__ == '__main__':
    logger.info("🚀 Statistics Service avviato")
    logger.info(f"📡 InfluxDB Adaptor: {INFLUX_ADAPTOR_URL}")
    
    # Avvia Flask in ascolto su 0.0.0.0:8082 (raggiungibile da Node-RED)
    app.run(host='0.0.0.0', port=8082, debug=False)