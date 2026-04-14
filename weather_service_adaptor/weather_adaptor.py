import cherrypy
import requests
import json
import os

class WeatherAdaptor:
    exposed = True

    def GET(self, *uri, **params):
        # 1. Recupero dati sensibili dalle variabili d'ambiente Docker
        api_key = os.getenv('TOMORROW_API_KEY', 'vl2kNb5ZvcIWSMqS7oGfKgOzLTOd7FXf')
        location = os.getenv('CITY_NAME', '44.6458,10.9257')
        
        # URL per previsioni orarie (Hourly)
        url = f"https://api.tomorrow.io/v4/weather/forecast?location={location}&apikey={api_key}"
        headers = {"accept": "application/json"} # <--- Ora è dichiarato correttamente
        
        print(f"[ADAPTOR] Richiesta meteo ricevuta per: {location}")
        try:
            print(f"[ADAPTOR] Richiesta meteo per: {location}") # LOG DI AVVIO
            r = requests.get(url, headers=headers)
            r.raise_for_status()
            data = r.json()
            
            # STAMPA IL JSON PER VEDERE SE CI SONO DATI
            # print(json.dumps(data, indent=2)) # Opzionale, molto lungo
            
            hourly_data = data.get('timelines', {}).get('hourly', [])
            print(f"[ADAPTOR] Trovate {len(hourly_data)} ore di previsioni")

            total_rain_accumulation_6h = 0
            max_precip_probability_6h = 0
            for hour in hourly_data[:6]:
                values = hour.get('values', {})

                # 1. Accumulo di pioggia (somma totale nelle 6 ore)
                rain_acc = values.get('rainAccumulation', 0)
                # Fallback di sicurezza: se rainAccumulation è None, usa 0
                if rain_acc is not None: 
                    total_rain_accumulation_6h += rain_acc
                
                # 2. Probabilità di precipitazione (cerchiamo il picco massimo nelle 6 ore)
                precip_prob = values.get('precipitationProbability', 0)
                if precip_prob is not None and precip_prob > max_precip_probability_6h:
                    max_precip_probability_6h = precip_prob
            
            print(f"[ADAPTOR] Probabilità pioggia massima (6h): {max_precip_probability_6h}%")
            print(f"[ADAPTOR] Accumulo pioggia calcolato (6h): {round(total_rain_accumulation_6h, 2)} mm")
            
            result = {
                "max_precipitation_probability_6h": max_precip_probability_6h,
                "total_rain_accumulation_6h": round(total_rain_accumulation_6h, 2),
                "location": location,
                "status": "success"
            }
            return json.dumps(result)

        except requests.exceptions.RequestException as e:
            cherrypy.response.status = 500
            print(f"[ADAPTOR] Errore di rete: {e}")
            return json.dumps({"status": "error", "message": "Errore di connessione API Tomorrow.io"})
        except Exception as e:
            cherrypy.response.status = 500
            print(f"[ADAPTOR] Errore interno: {e}")
            return json.dumps({"status": "error", "message": str(e)})


if __name__ == '__main__':
    # 1. Configurazione per Docker (0.0.0.0 e porta 8085)
    cherrypy.config.update({
        'server.socket_host': '0.0.0.0',
        'server.socket_port': 8085
    })
    
    # 2. Configurazione del Dispatcher
    conf = {
        '/': {
            'request.dispatch': cherrypy.dispatch.MethodDispatcher(),
            'tools.sessions.on': True,
        }
    }
    
    # 3. Avvio corretto
    # Notare che passiamo l'istanza WeatherAdaptor() E la configurazione 'conf'
    cherrypy.quickstart(WeatherAdaptor(), '/', conf)