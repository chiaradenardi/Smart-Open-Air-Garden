import cherrypy
import time
import json

def _load():
    """Reads the JSON database from the local file."""
    with open("catalogManager.json", "r") as f:
        return json.load(f)

def _save(data):
    """Saves the modified JSON database back to the local file."""
    data["lastUpdateJSON"] = time.time()
    with open("catalogManager.json", "w") as f:
        json.dump(data, f, indent=4)

def _find_garden(data, garden_id):
    """Searches the database for a specific garden by its ID."""
    for g in data["gardensList"]:
        if g["gardenID"] == garden_id:
            return g
    return None

class BrokerEndpoint:
    """This endpoint provides the IP and port of the MQTT broker."""
    exposed = True

    def GET(self):
        """Returns the broker configuration as a JSON string."""
        data = _load()
        b = data["broker"]
        return json.dumps({"broker_name": b["broker_name"], "broker_port": b["port"]}, indent=4)

class PriceEndpoint:
    """This endpoint manages the cost of water per cubic meter."""
    exposed = True

    def GET(self):
        """Returns the current water price."""
        data = _load()
        return json.dumps(data["waterPricePerM3"], indent=4)

    def PUT(self):
        """Updates the water price with a new value."""
        body = json.loads(cherrypy.request.body.read().decode('utf-8'))
        if "NewWaterPricePerM3" not in body:
            return json.dumps({"error": "Missing NewWaterPricePerM3"}, indent=4)
        data = _load()
        data["waterPricePerM3"] = body["NewWaterPricePerM3"]
        _save(data)
        return json.dumps({"result": "Price updated", "newPrice": data["waterPricePerM3"]}, indent=4)


# API Reference: /gardens endpoint
# 
# GET    /gardens                      → list all gardens
# POST   /gardens                      → create garden
# GET    /gardens/{gID}                → single garden
# DELETE /gardens/{gID}                → delete garden
# GET    /gardens/{gID}/slots          → slots list
# POST   /gardens/{gID}/slots          → add slot
# GET    /gardens/{gID}/slots/{sID}    → single slot
# PUT    /gardens/{gID}/slots/{sID}    → update slot (plantID)
# DELETE /gardens/{gID}/slots/{sID}    → remove slot
# GET    /gardens/{gID}/device         → device info
# PUT    /gardens/{gID}/device         → update device
# GET    /gardens/{gID}/grid           → grid configuration
# PUT    /gardens/{gID}/grid           → update grid
# GET    /gardens/{gID}/location       → location
# PUT    /gardens/{gID}/location       → update location
# GET    /gardens/{gID}/owners         → owner user objects
# POST   /gardens/{gID}/owners         → add owner (body: {userID})
# DELETE /gardens/{gID}/owners/{uID}   → remove owner

class GardensEndpoint:
    """This endpoint manages everything about gardens, including their slots and devices."""
    exposed = True

    def GET(self, *uri, **params):
        """Returns data about gardens. You can ask for a list of all gardens or a specific one."""
        data = _load()

        # /gardens
        if len(uri) == 0:
            return json.dumps(data["gardensList"], indent=4)

        garden_id = uri[0]
        garden = _find_garden(data, garden_id)
        if not garden:
            return json.dumps({"error": f"Garden '{garden_id}' not found"}, indent=4)

        # /gardens/{gID}
        if len(uri) == 1:
            return json.dumps(garden, indent=4)

        section = uri[1]

        # /gardens/{gID}/slots
        if section == "slots":
            if len(uri) == 2:
                return json.dumps(garden.get("slots", []), indent=4)
            # /gardens/{gID}/slots/{sID}
            slot_id = uri[2]
            for s in garden.get("slots", []):
                if s["slotID"] == slot_id:
                    return json.dumps(s, indent=4)
            return json.dumps({"error": f"Slot '{slot_id}' not found"}, indent=4)

        if section == "device":
            return json.dumps(garden.get("device", {}), indent=4)

        if section == "grid":
            return json.dumps(garden.get("grid", {"max_pumps": 4, "max_taps": 4}), indent=4)

        if section == "location":
            return json.dumps({"location": garden.get("location", "")}, indent=4)

        if section == "owners":
            owner_ids = garden.get("ownerIDs", [])
            users = data.get("usersList", [])
            owners = [u for u in users if u["userID"] in owner_ids]
            return json.dumps(owners, indent=4)

        return json.dumps({"error": "Invalid endpoint"}, indent=4)

    def POST(self, *uri, **params):
        """Creates a new garden, adds a new slot, or adds a new owner to a garden."""
        body = json.loads(cherrypy.request.body.read().decode('utf-8'))
        data = _load()

        # POST /gardens — create garden
        if len(uri) == 0:
            required = ["gardenID", "gardenName"]
            for k in required:
                if k not in body:
                    return json.dumps({"error": f"Missing field: {k}"}, indent=4)
            if _find_garden(data, body["gardenID"]):
                return json.dumps({"error": "Garden ID already exists"}, indent=4)
            new_garden = {
                "gardenID":   body["gardenID"],
                "gardenName": body["gardenName"],
                "location":   body.get("location", ""),
                "grid":       body.get("grid", {"max_pumps": 4, "max_taps": 4}),
                "device":     body.get("device", {}),
                "slots":      [],
                "ownerIDs":   body.get("ownerIDs", [])
            }
            data["gardensList"].append(new_garden)
            _save(data)
            return json.dumps({"result": "Garden created", "gardenID": new_garden["gardenID"]}, indent=4)

        garden_id = uri[0]
        garden = _find_garden(data, garden_id)
        if not garden:
            return json.dumps({"error": f"Garden '{garden_id}' not found"}, indent=4)

        if len(uri) < 2:
            return json.dumps({"error": "Specify a sub-resource (slots, owners)"}, indent=4)

        section = uri[1]

        # POST /gardens/{gID}/slots - add slot
        if section == "slots":
            if "slotID" not in body or "plantID" not in body:
                return json.dumps({"error": "Missing slotID or plantID"}, indent=4)
            for s in garden.get("slots", []):
                if s["slotID"] == body["slotID"]:
                    return json.dumps({"error": "Slot ID already exists in this garden"}, indent=4)
            new_slot = {
                "slotID":    body["slotID"],
                "slotName":  body.get("slotName", f"Zone {body['slotID']}"),
                "plantID":   body["plantID"],
                "status":    body.get("status", "active"),
                "sensors":   body.get("sensors", ["SoilMoisture", "DHT11"]),
                "actuators": body.get("actuators", ["MicroServoPump"])
            }
            garden.setdefault("slots", []).append(new_slot)
            _save(data)
            return json.dumps({"result": "Slot added", "slotID": new_slot["slotID"]}, indent=4)

        # POST /gardens/{gID}/owners - add owner
        if section == "owners":
            user_id = body.get("userID")
            if not user_id:
                return json.dumps({"error": "Missing userID"}, indent=4)
            if user_id in garden.get("ownerIDs", []):
                return json.dumps({"error": "User already an owner"}, indent=4)
            garden.setdefault("ownerIDs", []).append(user_id)
            _save(data)
            return json.dumps({"result": "Owner added"}, indent=4)

        return json.dumps({"error": "Invalid endpoint"}, indent=4)

    def PUT(self, *uri, **params):
        """Updates information about an existing garden, its slots, or its device."""
        body = json.loads(cherrypy.request.body.read().decode('utf-8'))
        data = _load()

        if len(uri) < 2:
            return json.dumps({"error": "Specify garden ID and sub-resource"}, indent=4)

        garden_id = uri[0]
        garden = _find_garden(data, garden_id)
        if not garden:
            return json.dumps({"error": f"Garden '{garden_id}' not found"}, indent=4)

        section = uri[1]

        # PUT /gardens/{gID}/slots/{sID} - update slot
        if section == "slots":
            if len(uri) < 3:
                return json.dumps({"error": "Specify slot ID"}, indent=4)
            slot_id = uri[2]
            for s in garden.get("slots", []):
                if s["slotID"] == slot_id:
                    if "plantID" in body:
                        s["plantID"] = body["plantID"]
                    if "slotName" in body:
                        s["slotName"] = body["slotName"]
                    if "status" in body:
                        s["status"] = body["status"]
                    _save(data)
                    return json.dumps(s, indent=4)
            return json.dumps({"error": f"Slot '{slot_id}' not found"}, indent=4)

        # PUT /gardens/{gID}/device - update device
        if section == "device":
            device_id = body.get("deviceID")
            if device_id:
                for g in data["gardensList"]:
                    existing_device_id = g.get("device", {}).get("deviceID")
                    if g["gardenID"] != garden_id and existing_device_id and existing_device_id.lower() == device_id.lower():
                        return json.dumps({"error": f"Device '{device_id}' is already registered in garden '{g['gardenID']}' ({g['gardenName']})"}, indent=4)
            garden["device"] = body
            _save(data)
            return json.dumps({"result": "Device updated"}, indent=4)

        # PUT /gardens/{gID}/grid - update grid
        if section == "grid":
            garden.setdefault("grid", {})
            if "max_pumps" in body:
                garden["grid"]["max_pumps"] = body["max_pumps"]
            if "max_taps" in body:
                garden["grid"]["max_taps"] = body["max_taps"]
            _save(data)
            return json.dumps({"result": "Grid updated", "grid": garden["grid"]}, indent=4)

        # PUT /gardens/{gID}/location - update location
        if section == "location":
            if "location" not in body:
                return json.dumps({"error": "Missing location"}, indent=4)
            garden["location"] = body["location"]
            data["garden_location"] = body["location"]
            _save(data)
            return json.dumps({"result": "Location updated", "location": garden["location"]}, indent=4)

        # PUT /gardens/{gID} - update name or ownerIDs
        if len(uri) == 1:
            if "gardenName" in body:
                garden["gardenName"] = body["gardenName"]
            if "ownerIDs" in body:
                garden["ownerIDs"] = body["ownerIDs"]
            _save(data)
            return json.dumps({"result": "Garden updated"}, indent=4)

        return json.dumps({"error": "Invalid endpoint"}, indent=4)

    def DELETE(self, *uri, **params):
        """Removes a garden, a slot, or an owner from the database."""
        data = _load()

        if len(uri) == 0:
            return json.dumps({"error": "Specify a garden ID"}, indent=4)

        garden_id = uri[0]
        garden = _find_garden(data, garden_id)
        if not garden:
            return json.dumps({"error": f"Garden '{garden_id}' not found"}, indent=4)

        # DELETE /gardens/{gID} - remove garden
        if len(uri) == 1:
            data["gardensList"].remove(garden)
            _save(data)
            return json.dumps({"result": f"Garden '{garden_id}' deleted"}, indent=4)

        section = uri[1]

        # DELETE /gardens/{gID}/slots/{sID}
        if section == "slots" and len(uri) == 3:
            slot_id = uri[2]
            for s in garden.get("slots", []):
                if s["slotID"] == slot_id:
                    garden["slots"].remove(s)
                    _save(data)
                    return json.dumps({"result": f"Slot '{slot_id}' removed"}, indent=4)
            return json.dumps({"error": f"Slot '{slot_id}' not found"}, indent=4)

        # DELETE /gardens/{gID}/owners/{uID}
        if section == "owners" and len(uri) == 3:
            user_id = uri[2]
            if user_id in garden.get("ownerIDs", []):
                garden["ownerIDs"].remove(user_id)
                _save(data)
                return json.dumps({"result": f"Owner '{user_id}' removed"}, indent=4)
            return json.dumps({"error": f"User '{user_id}' is not an owner"}, indent=4)

        return json.dumps({"error": "Invalid endpoint"}, indent=4)

# Users endpoint

class UsersEndpoint:
    """This endpoint handles user registration and linking Telegram IDs."""
    exposed = True

    def GET(self, *uri, **params):
        """Returns a list of all users or details of a specific user."""
        data = _load()
        if len(uri) > 0:
            for u in data["usersList"]:
                if uri[0] == u["userID"]:
                    return json.dumps(u, indent=4)
            return json.dumps({"error": f"User '{uri[0]}' not found"}, indent=4)
        return json.dumps(data["usersList"], indent=4)

    def PUT(self, *uri, **params):
        """Updates a user, usually to add their Telegram Chat ID."""
        body = json.loads(cherrypy.request.body.read().decode('utf-8'))
        data = _load()
        for u in data["usersList"]:
            if body.get("userID") == u["userID"]:
                u["telegramChatID"] = body["telegramChatID"]
                _save(data)
                return json.dumps({"result": "User updated"}, indent=4)
        return json.dumps({"error": "USER ID NOT FOUND"}, indent=4)

    def POST(self):
        """Registers a new user in the system."""
        body = json.loads(cherrypy.request.body.read().decode('utf-8'))
        if "userID" not in body or "userName" not in body or "telegramChatID" not in body:
            return json.dumps({"error": "Missing userID, userName or telegramChatID"}, indent=4)
        data = _load()
        for u in data["usersList"]:
            if body["userID"] == u["userID"]:
                return json.dumps({"error": "USER ID already in the system"}, indent=4)
        data["usersList"].append(body)
        _save(data)
        return json.dumps({"result": "USER successfully added"}, indent=4)

    def DELETE(self, *uri, **params):
        """Deletes a user from the system."""
        data = _load()
        if len(uri) == 0:
            return json.dumps({"error": "Missing USER ID"}, indent=4)
        for u in data["usersList"]:
            if uri[0] == u["userID"]:
                data["usersList"].remove(u)
                _save(data)
                return json.dumps({"result": "User removed"}, indent=4)
        return json.dumps({"error": "USER ID not found"}, indent=4)


# Irrigation strategies endpoint

class StrategiesEndpoint:
    """This endpoint holds the irrigation rules (like moisture thresholds) for different crops."""
    exposed = True

    def GET(self, *uri, **params):
        """Returns the irrigation strategy for all crops or a specific crop."""
        data = _load()
        if len(uri) > 0:
            plant_id = uri[0]
            if plant_id in data["irrigation_strategies"]:
                return json.dumps(data["irrigation_strategies"][plant_id], indent=4)
            return json.dumps({"error": f"Strategy '{plant_id}' not found"}, indent=4)
        return json.dumps(data["irrigation_strategies"], indent=4)

    def PUT(self, *uri, **params):
        body = json.loads(cherrypy.request.body.read().decode('utf-8'))
        data = _load()
        plant_id = body.get("plantID")
        if plant_id and plant_id in data["irrigation_strategies"]:
            data["irrigation_strategies"][plant_id]["min_moisture_threshold"] = body["min_moisture_threshold"]
            _save(data)
            return json.dumps({"result": "Strategy updated"}, indent=4)
        return json.dumps({"error": "PLANT ID NOT FOUND"}, indent=4)

    def POST(self):
        body = json.loads(cherrypy.request.body.read().decode('utf-8'))
        if "plantID" not in body or "name" not in body or "min_moisture_threshold" not in body:
            return json.dumps({"error": "Missing data"}, indent=4)
        data = _load()
        plant_id = body["plantID"]
        if plant_id in data["irrigation_strategies"]:
            return json.dumps({"error": "STRATEGY ID already exists"}, indent=4)
        data["irrigation_strategies"][plant_id] = {
            "name": body["name"],
            "min_moisture_threshold": body["min_moisture_threshold"]
        }
        _save(data)
        return json.dumps({"result": "Strategy added"}, indent=4)

    def DELETE(self, *uri, **params):
        data = _load()
        if len(uri) == 0:
            return json.dumps({"error": "Missing STRATEGY ID"}, indent=4)
        plant_id = uri[0]
        if plant_id in data["irrigation_strategies"]:
            del data["irrigation_strategies"][plant_id]
            _save(data)
            return json.dumps({"result": "Strategy removed"}, indent=4)
        return json.dumps({"error": "STRATEGY ID not found"}, indent=4)


# Services endpoint

class ServicesEndpoint:
    exposed = True

    def GET(self, *uri, **params):
        data = _load()
        if len(uri) > 0:
            for s in data["servicesList"]:
                if uri[0] == s["serviceID"]:
                    return json.dumps(s, indent=4)
            return json.dumps({"error": f"Service '{uri[0]}' not found"}, indent=4)
        return json.dumps(data["servicesList"], indent=4)

    def PUT(self, *uri, **params):
        body = json.loads(cherrypy.request.body.read().decode('utf-8'))
        data = _load()
        for s in data["servicesList"]:
            if body.get("serviceID") == s["serviceID"]:
                s["status"] = body["status"]
                _save(data)
                return json.dumps({"result": "Service updated"}, indent=4)
        return json.dumps({"error": "SERVICE ID NOT FOUND"}, indent=4)

    def POST(self):
        body = json.loads(cherrypy.request.body.read().decode('utf-8'))
        if "serviceID" not in body or "serviceName" not in body:
            return json.dumps({"error": "Missing serviceID or serviceName"}, indent=4)
        data = _load()
        for s in data["servicesList"]:
            if body["serviceID"] == s["serviceID"]:
                return json.dumps({"error": "SERVICE ID already exists"}, indent=4)
        data["servicesList"].append(body)
        _save(data)
        return json.dumps({"result": "Service added"}, indent=4)

    def DELETE(self, *uri, **params):
        data = _load()
        if len(uri) == 0:
            return json.dumps({"error": "Missing SERVICE ID"}, indent=4)
        for s in data["servicesList"]:
            if uri[0] == s["serviceID"]:
                data["servicesList"].remove(s)
                _save(data)
                return json.dumps({"result": "Service removed"}, indent=4)
        return json.dumps({"error": "SERVICE ID not found"}, indent=4)


# Global location endpoint (used by WeatherServiceAdaptor)

class LocationEndpoint:
    """This endpoint stores the GPS location of the garden to fetch correct weather data."""
    exposed = True

    def GET(self):
        """Returns the current garden location."""
        data = _load()
        return json.dumps({"location": data.get("garden_location", "44.6458,10.9257")}, indent=4)

    def PUT(self):
        """Updates the garden location with new coordinates."""
        body = json.loads(cherrypy.request.body.read().decode('utf-8'))
        if "location" not in body:
            return json.dumps({"error": "Missing location"}, indent=4)
        data = _load()
        data["garden_location"] = body["location"]
        _save(data)
        return json.dumps({"result": "Location updated", "location": data["garden_location"]}, indent=4)


# Server bootstrap

class CatalogRoot:
    pass


if __name__ == "__main__":
    root = CatalogRoot()
    root.broker     = BrokerEndpoint()
    root.price      = PriceEndpoint()
    root.gardens    = GardensEndpoint()
    root.users      = UsersEndpoint()
    root.strategies = StrategiesEndpoint()
    root.services   = ServicesEndpoint()
    root.location   = LocationEndpoint()

    conf = {
        '/': {
            'request.dispatch': cherrypy.dispatch.MethodDispatcher(),
            'tools.sessions.on': True
        }
    }
    cherrypy.config.update({
        'server.socket_host': '0.0.0.0',
        'server.socket_port': 8080
    })
    cherrypy.tree.mount(root, '/', conf)
    cherrypy.engine.start()
    cherrypy.engine.block()