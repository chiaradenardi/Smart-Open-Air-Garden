import cherrypy
import time
import json

#**********************************************************************************
# l'approccio che avevo usato prima è sbagliato perchè era software monolitico
# uso corretto di cherrypy e methoddispatcher
#**********************************************************************************

class BrokerEndpoint:
    exposed=True

    def GET(self):
        with open("catalogManager.json", "r") as f:
            data=json.load(f)
        broker=data["broker"]
        pack_to_send={
            "broker_name":broker["broker_name"],
            "broker_port":broker["port"]
        }
        return json.dumps(pack_to_send,indent=4)

class PriceEndpoint:
    exposed=True
    def GET(self):
        with open("catalogManager.json", "r") as f:
            data=json.load(f)
        price=data["waterPricePerM3"]
        return json.dumps(price,indent=4)
    
    def PUT(self):
        body = cherrypy.request.body.read().decode('utf-8')
        body_json=json.loads(body)
        if "NewWaterPricePerM3" not in body_json:
             return json.dumps({"error": "Data missing (NewWaterPricePerM3 not present in body)"}, indent=4)
        
        f=open("catalogManager.json","r")
        data=json.load(f)
        f.close()
        data["waterPricePerM3"]=body_json["NewWaterPricePerM3"]
        file=open("catalogManager.json","w")
        json.dump(data,file,indent=4)
        file.close()
        return json.dumps({
            "result": "Water price successfully updated",
            "newPrice": data["waterPricePerM3"]
        }, indent=4)


#******************************************************************************************
# SLOTS API REST
#******************************************************************************************

class SlotsEndpoint:
    exposed=True
    def GET(self,*uri,**params):
        with open("catalogManager.json", "r") as f:
            data=json.load(f)
        trovato=False
        if len(uri) > 0:
            for i in data["garden_slots"]:
                if uri[0] == i["slotID"]:
                    slot = i
                    trovato=True
                    break
            if trovato:
                return json.dumps(slot, indent=4)
            else:
                return json.dumps({"error": f"Errore: Slot con ID '{uri[0]}' non trovata nel catalogo."}, indent=4)   
        return json.dumps(data["garden_slots"], indent=4)
        
    def PUT(self,*uri,**params):
            body = cherrypy.request.body.read().decode('utf-8')
            body_json=json.loads(body)
            f=open("catalogManager.json","r")
            data=json.load(f)
            trovato=False
            f.close()
            for i in data["garden_slots"]:
                if body_json["slotID"]==i["slotID"]:
                    i["plantID"]=body_json["plantID"]
                    trovato=True
                    break
            if trovato:
                file=open("catalogManager.json","w")
                json.dump(data,file,indent=4)
                file.close()
                return json.dumps(data,indent=4)
            else:
                return json.dumps({"error": "ID NOT FOUND"}, indent=4)
        
    def POST(self):
        body = cherrypy.request.body.read().decode('utf-8')
        body_json=json.loads(body)
        if "slotID" not in body_json or "plantID" not in body_json or "deviceID" not in body_json:
            return json.dumps({"error": "Data missing (slotID, plantID or deviceID not present)"}, indent=4)
              
        f=open("catalogManager.json","r")
        data=json.load(f)
        trovato=False
        f.close()
        
        # Controllo 1: Verifica se lo slotID è già in uso
        for i in data["garden_slots"]:
            if body_json["slotID"]==i["slotID"]:
                trovato=True
                break
        if trovato:
            return json.dumps({"error":"SLOT ID already in the system"})
        
        # Controllo 2: Verifica se il deviceID è già assegnato a un altro slot
        device_already_used = False
        device_used_by_slot = None
        for slot in data["garden_slots"]:
            if body_json["deviceID"] == slot["deviceID"]:
                device_already_used = True
                device_used_by_slot = slot["slotID"]
                break
        
        if device_already_used:
            return json.dumps({
                "error": f"Device '{body_json['deviceID']}' is already in use by slot '{device_used_by_slot}'",
                "deviceID": body_json["deviceID"],
                "used_by_slot": device_used_by_slot
            }, indent=4)
        
        # Se tutti i controlli passano, aggiungi lo slot
        data["garden_slots"].append(body_json)
        file=open("catalogManager.json","w")
        json.dump(data,file,indent=4)
        file.close()
        return json.dumps({"result":"SLOT successfully added"})
    
    def DELETE(self,*uri,**params):     
        f=open("catalogManager.json","r")
        data=json.load(f)
        f.close() 
        trovato=False
        if len(uri) > 0:
            for i in data["garden_slots"]:
                if uri[0]==i["slotID"]:
                    trovato=True
                    data["garden_slots"].remove(i)
                    break
            if trovato:
                file=open("catalogManager.json","w")
                json.dump(data,file,indent=4)
                file.close()
                return json.dumps({"result":"slot successfully removed"})
            else:
                return json.dumps({"error":"SLOT ID not found"})
        return json.dumps({"error": "Missing SLOT ID in the URL"}, indent=4)

#******************************************************************************************
# DEVICES API REST
#******************************************************************************************

    
class DevicesEndpoint:
    exposed=True
    
    def GET(self,*uri,**params):
        with open("catalogManager.json", "r") as f:
            data=json.load(f)
        trovato=False
        if len(uri) > 0:
            for i in data["devicesList"]:
                if uri[0] == i["deviceID"]:
                    device = i
                    trovato=True
                    break
            if trovato:
                return json.dumps(device, indent=4)
            else:
                return json.dumps({"error": f"Errore: Device con ID '{uri[0]}' non trovato nel catalogo."}, indent=4)   
        return json.dumps(data["devicesList"], indent=4)
        
    def PUT(self,*uri,**params):
            body = cherrypy.request.body.read().decode('utf-8')
            body_json=json.loads(body)
            f=open("catalogManager.json","r")
            data=json.load(f)
            trovato=False
            f.close()
            for i in data["devicesList"]:
                if body_json["deviceID"]==i["deviceID"]:
                    # Aggiorniamo lo status al posto del plantID
                    i["status"]=body_json["status"]
                    trovato=True
                    break
            if trovato:
                file=open("catalogManager.json","w")
                json.dump(data,file,indent=4)
                file.close()
                return json.dumps(data,indent=4)
            else:
                return json.dumps({"error": "ID NOT FOUND"}, indent=4)
        
    def POST(self):
        body = cherrypy.request.body.read().decode('utf-8')
        body_json=json.loads(body)
        # Controllo sulle chiavi base per i device
        if "deviceID" not in body_json or "deviceName" not in body_json:
            return json.dumps({"error": "Data missing (deviceID or deviceName not present)"}, indent=4)
              
        f=open("catalogManager.json","r")
        data=json.load(f)
        trovato=False
        f.close()
        for i in data["devicesList"]:
            if body_json["deviceID"]==i["deviceID"]:
                trovato=True
                break
        if trovato:
            return json.dumps({"error":"DEVICE ID already in the system"})
        else:
            data["devicesList"].append(body_json)
            file=open("catalogManager.json","w")
            json.dump(data,file,indent=4)
            file.close()
            return json.dumps({"result":"DEVICE successfully added"})
    
    def DELETE(self,*uri,**params):     
        f=open("catalogManager.json","r")
        data=json.load(f)
        f.close() 
        trovato=False
        if len(uri) > 0:
            for i in data["devicesList"]:
                if uri[0]==i["deviceID"]:
                    trovato=True
                    data["devicesList"].remove(i)
                    break
            if trovato:
                file=open("catalogManager.json","w")
                json.dump(data,file,indent=4)
                file.close()
                return json.dumps({"result":"device successfully removed"})
            else:
                return json.dumps({"error":"DEVICE ID not found"})
        return json.dumps({"error": "Missing DEVICE ID in the URL"}, indent=4)
    
#******************************************************************************************
# SERVICES API REST
#******************************************************************************************


class ServicesEndpoint:
    exposed=True
    def GET(self,*uri,**params):
        with open("catalogManager.json", "r") as f:
            data=json.load(f)
        trovato=False
        if len(uri) > 0:
            for i in data["servicesList"]:
                if uri[0] == i["serviceID"]:
                    service = i
                    trovato=True
                    break
            if trovato:
                return json.dumps(service, indent=4)
            else:
                return json.dumps({"error": f"Errore: Service con ID '{uri[0]}' non trovato nel catalogo."}, indent=4)   
        return json.dumps(data["servicesList"], indent=4)
        
    def PUT(self,*uri,**params):
            body = cherrypy.request.body.read().decode('utf-8')
            body_json=json.loads(body)
            f=open("catalogManager.json","r")
            data=json.load(f)
            trovato=False
            f.close()
            for i in data["servicesList"]:
                if body_json["serviceID"]==i["serviceID"]:
                    # Aggiorniamo lo status del servizio (es. se va offline)
                    i["status"]=body_json["status"]
                    trovato=True
                    break
            if trovato:
                file=open("catalogManager.json","w")
                json.dump(data,file,indent=4)
                file.close()
                return json.dumps(data,indent=4)
            else:
                return json.dumps({"error": "ID NOT FOUND"}, indent=4)
        
    def POST(self):
        body = cherrypy.request.body.read().decode('utf-8')
        body_json=json.loads(body)
        if "serviceID" not in body_json or "serviceName" not in body_json:
            return json.dumps({"error": "Data missing (serviceID or serviceName not present)"}, indent=4)
              
        f=open("catalogManager.json","r")
        data=json.load(f)
        trovato=False
        f.close()
        for i in data["servicesList"]:
            if body_json["serviceID"]==i["serviceID"]:
                trovato=True
                break
        if trovato:
            return json.dumps({"error":"SERVICE ID already in the system"})
        else:
            data["servicesList"].append(body_json)
            file=open("catalogManager.json","w")
            json.dump(data,file,indent=4)
            file.close()
            return json.dumps({"result":"SERVICE successfully added"})
    
    def DELETE(self,*uri,**params):     
        f=open("catalogManager.json","r")
        data=json.load(f)
        f.close() 
        trovato=False
        if len(uri) > 0:
            for i in data["servicesList"]:
                if uri[0]==i["serviceID"]:
                    trovato=True
                    data["servicesList"].remove(i)
                    break
            if trovato:
                file=open("catalogManager.json","w")
                json.dump(data,file,indent=4)
                file.close()
                return json.dumps({"result":"service successfully removed"})
            else:
                return json.dumps({"error":"SERVICE ID not found"})
        return json.dumps({"error": "Missing SERVICE ID in the URL"}, indent=4)
    
#******************************************************************************************
# Users API REST
#******************************************************************************************

class UsersEndpoint:
    exposed=True
    def GET(self,*uri,**params):
        with open("catalogManager.json", "r") as f:
            data=json.load(f)
        trovato=False
        if len(uri) > 0:
            for i in data["usersList"]:
                if uri[0] == i["userID"]:
                    user = i
                    trovato=True
                    break
            if trovato:
                return json.dumps(user, indent=4)
            else:
                return json.dumps({"error": f"Errore: User con ID '{uri[0]}' non trovato."}, indent=4)   
        return json.dumps(data["usersList"], indent=4)
        
    def PUT(self,*uri,**params):
            body = cherrypy.request.body.read().decode('utf-8')
            body_json=json.loads(body)
            f=open("catalogManager.json","r")
            data=json.load(f)
            trovato=False
            f.close()
            for i in data["usersList"]:
                if body_json["userID"]==i["userID"]:
                    # Aggiorniamo ad esempio la chatID di Telegram
                    i["telegramChatID"]=body_json["telegramChatID"]
                    trovato=True
                    break
            if trovato:
                file=open("catalogManager.json","w")
                json.dump(data,file,indent=4)
                file.close()
                return json.dumps(data,indent=4)
            else:
                return json.dumps({"error": "USER ID NOT FOUND"}, indent=4)
        
    def POST(self):
        body = cherrypy.request.body.read().decode('utf-8')
        body_json=json.loads(body)
        if "userID" not in body_json or "userName" not in body_json or "telegramChatID" not in body_json:
            return json.dumps({"error": "Data missing (userID, userName or telegramChatID not present)"}, indent=4)
              
        f=open("catalogManager.json","r")
        data=json.load(f)
        trovato=False
        f.close()
        for i in data["usersList"]:
            if body_json["userID"]==i["userID"]:
                trovato=True
                break
        if trovato:
            return json.dumps({"error":"USER ID already in the system"})
        else:
            data["usersList"].append(body_json)
            file=open("catalogManager.json","w")
            json.dump(data,file,indent=4)
            file.close()
            return json.dumps({"result":"USER successfully added"})
    
    def DELETE(self,*uri,**params):     
        f=open("catalogManager.json","r")
        data=json.load(f)
        f.close() 
        trovato=False
        if len(uri) > 0:
            for i in data["usersList"]:
                if uri[0]==i["userID"]:
                    trovato=True
                    data["usersList"].remove(i)
                    break
            if trovato:
                file=open("catalogManager.json","w")
                json.dump(data,file,indent=4)
                file.close()
                return json.dumps({"result":"user successfully removed"})
            else:
                return json.dumps({"error":"USER ID not found"})
        return json.dumps({"error": "Missing USER ID in the URL"}, indent=4)

#******************************************************************************************
# STRATEGIES API REST
#******************************************************************************************

class StrategiesEndpoint:
    exposed=True
    def GET(self,*uri,**params):
        with open("catalogManager.json", "r") as f:
            data=json.load(f)
            
        if len(uri) > 0:
            plant_id = uri[0]
            # Nei dizionari basta usare 'in' invece del ciclo for!
            if plant_id in data["irrigation_strategies"]:
                return json.dumps(data["irrigation_strategies"][plant_id], indent=4)
            else:
                return json.dumps({"error": f"Errore: Strategia con ID '{plant_id}' non trovata."}, indent=4)   
        return json.dumps(data["irrigation_strategies"], indent=4)
        
    def PUT(self,*uri,**params):
            body = cherrypy.request.body.read().decode('utf-8')
            body_json=json.loads(body)
            f=open("catalogManager.json","r")
            data=json.load(f)
            f.close()
            
            plant_id = body_json.get("plantID")
            if plant_id and plant_id in data["irrigation_strategies"]:
                # Aggiorniamo la soglia di umidità
                data["irrigation_strategies"][plant_id]["min_moisture_threshold"] = body_json["min_moisture_threshold"]
                
                file=open("catalogManager.json","w")
                json.dump(data,file,indent=4)
                file.close()
                return json.dumps(data,indent=4)
            else:
                return json.dumps({"error": "PLANT ID NOT FOUND"}, indent=4)
        
    def POST(self):
        body = cherrypy.request.body.read().decode('utf-8')
        body_json=json.loads(body)
        if "plantID" not in body_json or "name" not in body_json or "min_moisture_threshold" not in body_json:
            return json.dumps({"error": "Data missing"}, indent=4)
              
        f=open("catalogManager.json","r")
        data=json.load(f)
        f.close()
        
        plant_id = body_json["plantID"]
        if plant_id in data["irrigation_strategies"]:
            return json.dumps({"error":"STRATEGY ID already in the system"})
        else:
            # Aggiunta diretta nel dizionario
            data["irrigation_strategies"][plant_id] = {
                "name": body_json["name"],
                "min_moisture_threshold": body_json["min_moisture_threshold"]
            }
            file=open("catalogManager.json","w")
            json.dump(data,file,indent=4)
            file.close()
            return json.dumps({"result":"STRATEGY successfully added"})
    
    def DELETE(self,*uri,**params):     
        f=open("catalogManager.json","r")
        data=json.load(f)
        f.close() 
        
        if len(uri) > 0:
            plant_id = uri[0]
            if plant_id in data["irrigation_strategies"]:
                # Nei dizionari si usa 'del' per eliminare una chiave
                del data["irrigation_strategies"][plant_id]
                file=open("catalogManager.json","w")
                json.dump(data,file,indent=4)
                file.close()
                return json.dumps({"result":"strategy successfully removed"})
            else:
                return json.dumps({"error":"STRATEGY ID not found"})
        return json.dumps({"error": "Missing STRATEGY ID in the URL"}, indent=4)
    
#******************************************************************************************
# LOCATION API REST (Per il Meteo)
#******************************************************************************************
class LocationEndpoint:
    exposed = True
    def GET(self):
        with open("catalogManager.json", "r") as f:
            data = json.load(f)
        # Se non c'è ancora una posizione salvata, restituisce un valore di default
        location = data.get("garden_location", "44.6458,10.9257") 
        return json.dumps({"location": location}, indent=4)

    def PUT(self):
        body = cherrypy.request.body.read().decode('utf-8')
        body_json = json.loads(body)
        if "location" not in body_json:
            return json.dumps({"error": "Missing 'location' parameter"}, indent=4)
            
        with open("catalogManager.json", "r") as f:
            data = json.load(f)
            
        data["garden_location"] = body_json["location"]
        
        with open("catalogManager.json", "w") as f:
            json.dump(data, f, indent=4)
            
        return json.dumps({"result": "Location successfully updated", "location": data["garden_location"]}, indent=4)
    
#******************************************************************************************
# GRID API REST (Dimensioni Giardino)
#******************************************************************************************
class GridEndpoint:
    exposed = True
    def GET(self):
        with open("catalogManager.json", "r") as f:
            data = json.load(f)
        return json.dumps(data.get("garden_grid", {"max_pumps": 3, "max_taps": 3}), indent=4)

    def PUT(self):
        body = cherrypy.request.body.read().decode('utf-8')
        body_json = json.loads(body)
        
        with open("catalogManager.json", "r") as f:
            data = json.load(f)
            
        data["garden_grid"]["max_pumps"] = body_json.get("max_pumps", data["garden_grid"]["max_pumps"])
        data["garden_grid"]["max_taps"] = body_json.get("max_taps", data["garden_grid"]["max_taps"])
        
        with open("catalogManager.json", "w") as f:
            json.dump(data, f, indent=4)
            
        return json.dumps({"result": "Grid updated", "garden_grid": data["garden_grid"]}, indent=4)

class CatalogRoot: #empty class which contains all the endpoints
    pass                     
               

        

if __name__=="__main__":
    root = CatalogRoot()

    root.broker = BrokerEndpoint()          
    root.price = PriceEndpoint()            
    root.slots = SlotsEndpoint()            
    root.devices = DevicesEndpoint()        
    root.services = ServicesEndpoint()      
    root.users = UsersEndpoint()            
    root.strategies = StrategiesEndpoint()  
    root.location = LocationEndpoint()
    root.grid = GridEndpoint()



    conf={
        #Standard configuration to serve the url "localhost:8080"
        '/':{
            'request.dispatch':cherrypy.dispatch.MethodDispatcher(),
            'tools.sessions.on':True
        }
    }
    cherrypy.config.update({
        'server.socket_host': '0.0.0.0',
        'server.socket_port': 8080
    })

    cherrypy.tree.mount(root,'/',conf)
    cherrypy.engine.start()
    cherrypy.engine.block()