import cherrypy
import time
import json

class SmartOpenAirGarden:
    exposed=True

    def GET(self,*uri,**params):
        if uri[0]=="broker":
            f=open("catalogManager.json","r")
            data=json.load(f)
            f.close()
            broker=data["broker"]
            pack_to_send={
                "broker_ip":broker["ip"],
                "broker_port":broker["port"]
            }
            return json.dumps(pack_to_send,indent=4)
        
        if uri[0]=="price":
            f=open("catalogManager.json","r")
            data=json.load(f)
            f.close()
            price=data["water_price_per_m3"]
            return f"water price per m3: {json.dumps(price,indent=4)}"
        
        if uri[0]=="strategies":
            f=open("catalogManager.json","r")
            data=json.load(f)
            f.close() 
            if len(uri) > 1:
                if uri[1] in data["irrigation_strategies"]:
                    strategy = data["irrigation_strategies"][uri[1]]
                    return json.dumps(strategy, indent=4)
                else:
                    return f"Errore: Pianta con ID '{uri[1]}' non trovata nel catalogo."
            return json.dumps(data["irrigation_strategies"], indent=4)
        
        if uri[0]=="slots":
            f=open("catalogManager.json","r")
            data=json.load(f)
            f.close() 
            trovato=False
            if len(uri) > 1:
                for i in data["garden_slots"]:
                    if uri[1]==i["slotID"]:
                        trovato=True
                        return json.dumps(i,indent=4)             
                if trovato:
                    return json.dumps(data["garden_slots"], indent=4) 
                else:
                    return "SLOT ID NON VALIDO"
            else:
                return json.dumps(data["garden_slots"], indent=4)
   

    def PUT(self,*uri,**params):
        if uri[0]=="update":
            body = cherrypy.request.body.read().decode('utf-8')
            body_json=json.loads(body)
            f=open("catalogManager.json","r")
            data=json.load(f)
            trovato=False
            f.close()
            for i in data["garden_slots"]:
                if body_json["slotID"]==i["slotID"]:
                    i["plantID"]=body_json["plantID"]
                    i["mqtt_base_topic"]=f"garden/{body_json['slotID']}"
                    trovato=True
            if trovato:
                file=open("catalogManager.json","w")
                json.dump(data,file,indent=4)
                file.close()
                return f"slot successfully updated!\n{json.dumps(data,indent=4)}"
            else:
                return "ID NOT FOUND"
        
    def POST(self,*uri,**params):
        if uri[0]=="add":
            
            if len(uri)>1 and uri[1]=="slot":
                body = cherrypy.request.body.read().decode('utf-8')
                body_json=json.loads(body)
                if "slotID" not in body_json:
                    return "Error: Data missing (slotID not present in body)"
                if "threshold" not in body_json:
                    return "Error: Data missing (threshold not present in body)"
                
                f=open("catalogManager.json","r")
                data=json.load(f)
                trovato=False
                f.close()
                for i in data["garden_slots"]:
                    if body_json["slotID"]==i["slotID"]:
                        trovato=True
                if trovato:
                    return "SLOT ID already in the system"
                else:
                    data["garden_slots"].append(body_json)
                    file=open("catalogManager.json","w")
                    json.dump(data,file,indent=4)
                    file.close()
                    return "SLOT successfully added"
                
            if len(uri)>1 and uri[1]=="strategy":
                body = cherrypy.request.body.read().decode('utf-8')
                body_json=json.loads(body)
                if "plantID" not in body_json:
                    return "Errore: Dati mancanti (plantID non trovato nel body)"
                
                f=open("catalogManager.json","r")
                data=json.load(f)
                f.close()
                if "plantID" not in body_json:
                    return "Errore: plantID mancante"
                
                if body_json["plantID"] in data["irrigation_strategies"]:
                    return "strategy already present"
                else:
                    data["irrigation_strategies"][body_json["plantID"]] = {
                    "name": body_json["name"],
                    "min_moisture_threshold": body_json["threshold"]
                }
                    file=open("catalogManager.json","w")
                    json.dump(data,file,indent=4)
                    file.close()
                    return "STRATEGY successfully added"

       
    
    def DELETE(self,*uri,**params):
        if uri[0]=="delete":
            f=open("catalogManager.json","r")
            data=json.load(f)
            f.close() 
            trovato=False
            if len(uri) > 1:
                for i in data["garden_slots"]:
                    if uri[1]==i["slotID"]:
                        trovato=True
                        data["garden_slots"].remove(i)
                        break
                if trovato:
                    file=open("catalogManager.json","w")
                    json.dump(data,file,indent=4)
                    file.close()
                    return "slot successfully removed"
                else:
                    return "SLOT ID not found"
                    
               

                



               



if __name__=="__main__":
    conf={
        #Standard configuration to serve the url "localhost:8080"
        '/':{
            'request.dispatch':cherrypy.dispatch.MethodDispatcher(),
            'tools.sessions.on':True
        }
    }
    devReg=SmartOpenAirGarden()
    cherrypy.tree.mount(devReg,'/',conf)
    cherrypy.engine.start()
    cherrypy.engine.block()