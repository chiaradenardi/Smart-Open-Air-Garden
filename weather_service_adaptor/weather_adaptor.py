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

            total_rain_6h = 0
            for hour in hourly_data[:6]:
                values = hour.get('values', {})
                rain_intensity = values.get('precipitationIntensity', 0)
                total_rain_6h += rain_intensity
            
            print(f"[ADAPTOR] Pioggia totale calcolata (6h): {total_rain_6h} mm") # QUESTO LO VEDRAI IN DOCKER
            
            result = {
                "rain_6h": round(total_rain_6h, 2),
                "location": location,
                "status": "success"
            }
            return json.dumps(result)

        except Exception as e:
            cherrypy.response.status = 500
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