from flask import Flask, jsonify
import requests

app = Flask(__name__)

# L'URL di Natalia come da vostro Contratto API
INFLUX_ADAPTOR_URL = "http://localhost:8081/history"

@app.route('/api/water-saved', methods=['GET'])
def calcola_risparmio():
    print("Ricevuta richiesta dalla Dashboard Node-RED. Calcolo in corso...")
    
    # 1. Prepariamo i parametri per Natalia (Pompa negli ultimi 7 giorni)
    parametri = {
        "sensor_type": "pump_status",
        "period": "7d"
    }

    dati_pompa = []
    
    try:
        # 2. Proviamo a fare la vera chiamata REST a Natalia
        print(f"Bussando alla porta di Natalia: {INFLUX_ADAPTOR_URL}...")
        risposta = requests.get(INFLUX_ADAPTOR_URL, params=parametri)
        risposta.raise_for_status()
        dati_pompa = risposta.json()
        print("Dati storici ricevuti con successo!")
        
    except requests.exceptions.RequestException as e:
        # 3. SE NATALIA E' SPENTA: Usiamo dati finti per non bloccarti il lavoro!
        print("ATTENZIONE: Il servizio di Natalia non risponde. Uso dati di test.")
        # Fingiamo che la pompa si sia accesa 5 volte
        dati_pompa = [
            {"time": "2026-03-16T10:00:00Z", "value": 1, "device": "RPi_001", "sensor": "pump_status"},
            {"time": "2026-03-17T10:00:00Z", "value": 1, "device": "RPi_001", "sensor": "pump_status"},
            {"time": "2026-03-18T10:00:00Z", "value": 1, "device": "RPi_001", "sensor": "pump_status"}
        ]

    # --- INIZIO LA MATEMATICA ---
    # Facciamo finta che ogni "1" (accensione) nel database corrisponda a 5 minuti di irrigazione.
    # Calcoliamo i minuti totali della vostra Smart Strategy:
    accensioni_smart = len([dato for dato in dati_pompa if dato.get("value") == 1])
    minuti_smart_totali = accensioni_smart * 5 
    litri_usati_smart = minuti_smart_totali * 2 # Ipotizziamo 2 litri d'acqua al minuto
    
    # Ora calcoliamo lo spreco di un "Timer Fisso" stupido (es. 15 minuti al giorno fissi per 7 giorni)
    minuti_timer_stupido = 15 * 7
    litri_usati_timer = minuti_timer_stupido * 2
    
    # Il risparmio finale!
    litri_risparmiati = litri_usati_timer - litri_usati_smart
    efficienza = round((litri_risparmiati / litri_usati_timer) * 100, 1)

    # 4. Impacchettiamo i risultati in un bel JSON da mandare a Node-RED
    risultato_finale = {
        "litri_usati_smart": litri_usati_smart,
        "litri_usati_timer_fisso": litri_usati_timer,
        "litri_acqua_risparmiati": litri_risparmiati,
        "percentuale_efficienza": efficienza,
        "messaggio": f"Ottimo lavoro! Hai risparmiato {litri_risparmiati} litri d'acqua questa settimana."
    }
    
    print(f"Calcolo finito: {risultato_finale}")
    return jsonify(risultato_finale)

if __name__ == '__main__':
    # Avviamo il server sulla porta 5000
    print("Avvio dello Statistics & Analytics Service sulla porta 5000...")
    app.run(host='0.0.0.0', port=5000)