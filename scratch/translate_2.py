import os

file_path = "Telegram_Bot/Telegram_Bot.py"

with open(file_path, "r", encoding="utf-8") as f:
    content = f.read()

replacements = {
    # Errore messages
    "Errore di connessione": "Connection error",
    "Errore in on_message": "Error in on_message",
    "Errore nel contattare il Catalogo": "Error contacting the Catalog",
    "Errore nel caricare le piante": "Error loading crops",
    "Errore dal database": "Database error",
    "Errore di formato. Devi inserire 3 valori separati da virgola.\\nEsempio: P1_R2, P3, RPi_003": "Format error. You must enter 3 comma-separated values.\\nExample: P1_R2, P3, RPi_003",
    "Errore: La coordinata dello slot deve essere nel formato Px_Ry (es. P1_R2). Riprova con /addslot.": "Error: Slot coordinate must be in Px_Ry format (e.g., P1_R2). Try again using /addslot.",
    "Errore dal server": "Server error",
    "Errore: Inserisci un numero valido (es. 2.5). Riprova usando /price.": "Error: Enter a valid number (e.g., 2.5). Try again using /price.",
    "Errore di formato. Devi inserire 2 valori separati da virgola. Riprova con /adddevice": "Format error. You must enter 2 comma-separated values. Try again using /adddevice",
    "Errore durante il collegamento": "Error during linking",
    "Errore aggiornamento posizione": "Error updating location",
    "Errore caricamento griglia": "Error loading grid",
    "Errore aggiornamento": "Update error",
    "Errore:": "Error:",

    # Labels and remaining texts
    "Scegli una coltura per aggiornarne la strategia, oppure premi Inserisci Nuova per aggiungerne una.": "Choose a crop to update its strategy, or press Insert New to add one.",
    "Inserisci Nuova": "Insert New",
    "Scegli una Pianta": "Choose a Crop",
    "Ecco lo stato dei tuoi dispositivi:": "Here is the status of your devices:",
    "Nessun dispositivo registrato nel Catalogo.": "No devices registered in the Catalog.",
    "Slot Associato": "Associated Slot",
    "Nessuno": "None",
    "Sconosciuto": "Unknown",
    "Invia la tua posizione": "Send your location",
    "Oppure invia semplicemente il nome della città.": "Or simply send the name of the city.",
    "Umidità Target": "Target Moisture",
    "Acqua": "Water",
    "Prezzo Acqua": "Water Price",
    "Nessun dato": "No data",
    "Per aggiungere un nuovo slot usa il comando /addslot.": "To add a new slot use the command /addslot.",
    "Per rimuovere uno slot usa il comando /removeslot.": "To remove a slot use the command /removeslot.",
    "Dispositivo": "Device",
    "Pianta": "Crop",
    "Utente": "User",
    "Per aggiungere un nuovo dispositivo usa il comando /adddevice.": "To add a new device use the command /adddevice.",
    "Per rimuovere un dispositivo usa il comando /removedevice.": "To remove a device use the command /removedevice.",
    "Per aggiungere una nuova pianta usa il comando /addplant.": "To add a new crop use the command /addplant.",
    "Per rimuovere una pianta usa il comando /removeplant.": "To remove a crop use the command /removeplant.",
    "Per aggiungere un nuovo utente usa il comando /adduser.": "To add a new user use the command /adduser.",
    "Per rimuovere un utente usa il comando /removeuser.": "To remove a user use the command /removeuser.",
    "Attenzione:": "Warning:",
    "Attivo": "Active",
    "Inattivo": "Inactive",
    "Non ci sono informazioni sul prezzo dell'acqua. Usa /price per impostarlo.": "No water price information available. Use /price to set it."
}

for it, en in replacements.items():
    content = content.replace(it, en)

with open(file_path, "w", encoding="utf-8") as f:
    f.write(content)
