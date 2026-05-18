import cherrypy
import requests
import json
import os
import time 

class WeatherAdaptor:
    """This class asks Tomorrow.io for the weather forecast to check if it will rain soon."""
    exposed = True
    def __init__(self):
        """Sets up a cache so we don't ask the weather API too often and get blocked."""
        self.cached_result = None
        self.last_fetch_time = 0
        self.cache_ttl = 900  # 900 seconds = 15 minutes validity

    def GET(self, *uri, **params):
        """Handles the web request. It returns the expected rain for the next 6 hours."""
        current_time = time.time()
        if self.cached_result and (current_time - self.last_fetch_time) < self.cache_ttl:
            print("[ADAPTOR] Using cached data. No call to Tomorrow.io")
            return self.cached_result
        # 1. Get API KEY from environment variables (this remains fixed)
        api_key = os.getenv('TOMORROW_API_KEY', 'vl2kNb5ZvcIWSMqS7oGfKgOzLTOd7FXf')
        
        # 2. ASK THE CATALOG FOR THE POSITION (DYNAMIC!)
        try:
            catalog_res = requests.get("http://service-catalog:8080/location", timeout=5).json()
            location = catalog_res.get("location", "Turin,IT")
        except Exception as e:
            print(f"[ADAPTOR] Unable to contact the catalog for position. Using default. ({e})")
            location = "Turin,IT" # Emergency fallback
        
        # URL for hourly forecasts (Hourly)
        url = f"https://api.tomorrow.io/v4/weather/forecast?location={location}&apikey={api_key}"
        headers = {"accept": "application/json"} 
        
        print(f"[ADAPTOR] Weather request received for: {location}")
        
        try:
            print(f"[ADAPTOR] Weather request for: {location}") # LOG OF START
            r = requests.get(url, headers=headers)
            r.raise_for_status()
            data = r.json()
            
            hourly_data = data.get('timelines', {}).get('hourly', [])
            print(f"[ADAPTOR] Found {len(hourly_data)} hours of forecasts")

            total_rain_accumulation_6h = 0
            max_precip_probability_6h = 0
            for hour in hourly_data[:6]:
                values = hour.get('values', {})

                # Rain accumulation (total sum in 6 hours)
                rain_acc = values.get('rainAccumulation', 0)
                # Safety fallback: if rainAccumulation is None, use 0
                if rain_acc is not None: 
                    total_rain_accumulation_6h += rain_acc
                
                # Precipitation probability (search for the maximum peak in 6 hours)
                precip_prob = values.get('precipitationProbability', 0)
                if precip_prob is not None and precip_prob > max_precip_probability_6h:
                    max_precip_probability_6h = precip_prob
            
            print(f"[ADAPTOR] Maximum precipitation probability (6h): {max_precip_probability_6h}%")
            print(f"[ADAPTOR] Calculated rain accumulation (6h): {round(total_rain_accumulation_6h, 2)} mm")
            
            result = {
                "max_precipitation_probability_6h": max_precip_probability_6h,
                "total_rain_accumulation_6h": round(total_rain_accumulation_6h, 2),
                "location": location,
                "status": "success"
            }
            # Save in cache before sending
            self.cached_result = json.dumps(result)
            self.last_fetch_time = current_time
            return self.cached_result
        except requests.exceptions.RequestException as e:
            print(f"[ADAPTOR] Network error: {e}")
            # Emergency: If Tomorrow.io blocks us (Error 429), we give the old data to the Brain!
            if self.cached_result:
                print("[ADAPTOR] Tomorrow.io blocked. Using old cache data for emergency.")
                cherrypy.response.status = 200 # Lying to the Brain saying everything is ok
                return self.cached_result
            
            cherrypy.response.status = 500
            return json.dumps({"status": "error", "message": "Error connecting to Tomorrow.io API"})

        except Exception as e:
            cherrypy.response.status = 500
            print(f"[ADAPTOR] Internal error: {e}")
            return json.dumps({"status": "error", "message": str(e)})


if __name__ == '__main__':
    cherrypy.config.update({
        'server.socket_host': '0.0.0.0',
        'server.socket_port': 8085
    })  
    conf = {
        '/': {
            'request.dispatch': cherrypy.dispatch.MethodDispatcher(),
            'tools.sessions.on': True,
        }
    }
    cherrypy.quickstart(WeatherAdaptor(), '/', conf)