import os

file_path = "Telegram_Bot/Telegram_Bot.py"

with open(file_path, "r", encoding="utf-8") as f:
    content = f.read()

replacements = {
    # Commands
    "commands=['coltura']": "commands=['crop']",
    "commands=['aggiungislot']": "commands=['addslot']",
    "commands=['rimuovislot']": "commands=['removeslot']",
    "commands=['aggiungidevice']": "commands=['adddevice']",
    "commands=['rimuovidevice']": "commands=['removedevice']",
    "commands=['aggiungipianta']": "commands=['addplant']",
    "commands=['rimuovipianta']": "commands=['removeplant']",
    "commands=['soglie']": "commands=['thresholds']",
    "commands=['profilo']": "commands=['profile']",
    "commands=['aggiungiutente']": "commands=['adduser']",
    "commands=['rimuoviutente']": "commands=['removeuser']",
    "commands=['citta']": "commands=['city']",
    "commands=['posizione']": "commands=['location']",
    "commands=['dimensionigiardino']": "commands=['gardensize']",
    "commands=['giardino']": "commands=['garden']",

    # UI Buttons
    "🌿 Gestione Colture": "🌿 Crop Management",
    "📟 Stato Dispositivi": "📟 Device Status",
    "💶 Prezzo Acqua": "💶 Water Price",
    "📊 Soglie Irrigazione": "📊 Available Crops",
    "🔧 Gestione Admin": "🔧 Admin Management",
    "🌍 Imposta Posizione Meteo": "🌍 Set Weather Location",
    "👤 Collega Profilo (Ricevi Notifiche)": "👤 Link Profile (Receive Notifications)",
    
    "➕ Aggiungi Slot": "➕ Add Slot",
    "➖ Rimuovi Slot": "➖ Remove Slot",
    "➕ Aggiungi Device": "➕ Add Device",
    "➖ Rimuovi Device": "➖ Remove Device",
    "➕ Aggiungi Pianta": "➕ Add Crop",
    "➖ Rimuovi Pianta": "➖ Remove Crop",
    "➕ Aggiungi Utente": "➕ Add User",
    "➖ Rimuovi Utente": "➖ Remove User",
    "📐 Dimensioni Giardino": "📐 Garden Size",
    "🌱 Mostra Giardino": "🌱 Show Garden",
    
    "✅ Conferma e Rimuovi": "✅ Confirm and Remove",
    "❌ Annulla": "❌ Cancel",

    # Messages (Main Menu)
    "🌱 *Smart Open Air Garden - Pannello di Controllo* 🌱": "🌱 *Smart Open Air Garden - Control Panel* 🌱",
    "Benvenuto nel tuo ecosistema IoT. Da qui puoi monitorare i sensori, ": "Welcome to your IoT ecosystem. From here you can monitor the sensors, ",
    "gestire le irrigazioni e tenere sotto controllo i consumi.\\n\\n": "manage irrigation and monitor your consumption.\\n\\n",
    "Usa i bottoni sottostanti per navigare nel sistema.": "Use the buttons below to navigate the system.",

    "🔧 *Pannello di Amministrazione*\\n\\nScegli l'operazione che desideri effettuare:": "🔧 *Admin Panel*\\n\\nChoose the operation you wish to perform:",

    "🗺️ *Mappa e Griglia:*\\n": "🗺️ *Map and Grid:*\\n",
    "📐 `/dimensionigiardino` | 🌱 `/giardino` \\n\\n": "📐 `/gardensize` | 🌱 `/garden` \\n\\n",
    "🔧 *Gestione Avanzata (Admin):*\\n": "🔧 *Advanced Management (Admin):*\\n",
    "➕ `/aggiungislot` | ➖ `/rimuovislot`\\n": "➕ `/addslot` | ➖ `/removeslot`\\n",
    "➕ `/aggiungidevice` | ➖ `/rimuovidevice`\\n": "➕ `/adddevice` | ➖ `/removedevice`\\n",
    "➕ `/aggiungipianta` | ➖ `/rimuovipianta`\\n": "➕ `/addplant` | ➖ `/removeplant`\\n",
    "➕ `/aggiungiutente` | ➖ `/rimuoviutente`\\n": "➕ `/adduser` | ➖ `/removeuser`\\n",

    # Status & Alerts
    "❌ Nessun dato disponibile": "❌ No data available",
    "✅ Informazioni Pianta aggiornate con successo!": "✅ Crop Information updated successfully!",
    "✅ Slot creato con successo!": "✅ Slot created successfully!",
    "✅ Utente creato con successo!": "✅ User created successfully!",
    "❌ Errore durante la creazione dello slot": "❌ Error creating slot",
    "❌ Errore durante l'eliminazione dello slot": "❌ Error removing slot",
    "❌ Dispositivo non trovato": "❌ Device not found",
    "✅ Dispositivo aggiornato con successo!": "✅ Device updated successfully!",
    "✅ Posizione GPS ricevuta e salvata!\\nCoordinate: `{nuova_posizione}`\\nL'irrigazione ora controllerà il meteo per questa zona.": "✅ GPS Location received and saved!\\nCoordinates: `{nuova_posizione}`\\nThe irrigation system will now check the weather for this zone.",
    "❌ *Operazione annullata*. Le dimensioni del giardino non sono state modificate.": "❌ *Operation cancelled*. The garden dimensions have not been changed.",
    "✅ Dimensioni aggiornate!\\nEcco il tuo nuovo giardino:\\n": "✅ Dimensions updated!\\nHere is your new garden:\\n",
    "✅ Dimensioni aggiornate e {deleted_count} slot eliminati!\\nEcco il tuo nuovo giardino:\\n": "✅ Dimensions updated and {deleted_count} slots removed!\\nHere is your new garden:\\n",
    "🌱 *Mappa del tuo Giardino:*\\n": "🌱 *Map of your Garden:*\\n",
    "❌ Errore aggiornamento DB: {e}": "❌ DB update error: {e}",

    # Crops & Thresholds
    "📊 *Le tue strategie di Irrigazione*": "📊 *Your Available Crops*",
    "Nessuna strategia attiva trovata.": "No active crops found.",
    "Non ci sono informazioni sul prezzo dell'acqua.": "No water price information available.",
    "💶 *Prezzo dell'Acqua Attuale*": "💶 *Current Water Price*",
    "Prezzo:": "Price:",

    # Forms
    "📐 *Imposta le dimensioni del Giardino*\\n": "📐 *Set Garden Dimensions*\\n",
    "Scrivi il numero di Filoni (Pompe) e il numero di Rubinetti (Piante) per filone, ": "Type the number of Rows (Pumps) and the number of Taps (Plants) per row, ",
    "separati da una virgola.\\n\\n": "separated by a comma.\\n\\n",
    "Esempio: *3, 4* (3 Filoni, 4 Piante ciascuno)": "Example: *3, 4* (3 Rows, 4 Plants each)",

    "⚠️ *Attenzione!*\\n": "⚠️ *Warning!*\\n",
    "Vuoi ridurre le dimensioni a {new_max_pumps} filoni e {new_max_taps} rubinetti, ": "You want to reduce dimensions to {new_max_pumps} rows and {new_max_taps} taps, ",
    "ma ci sono delle piante configurate in slot che verrebbero eliminati:\\n": "but there are plants configured in slots that will be deleted:\\n",
    "Vuoi procedere ed eliminare definitivamente queste configurazioni?": "Do you want to proceed and permanently delete these configurations?",
    
    # Legends
    "_Legenda:_  🌱 `Occupato`  |  🟫 `Libero`": "_Legend:_  🌱 `Occupied`  |  🟫 `Empty`",

    # Commands / Inputs
    "Scrivi il nome della Pianta da aggiornare/inserire:": "Type the name of the Crop to update/insert:",
    "Scrivi l'umidità del terreno target (es. 40):": "Type the target soil moisture (e.g., 40):",
    "Quanti ml di acqua servono ogni volta? (es. 200):": "How many ml of water are needed each time? (e.g., 200):",
    "Scrivi il nuovo prezzo in formato decimale (es. 0.001):": "Type the new price in decimal format (e.g., 0.001):",
    "Invia la tua posizione tramite la graffetta 📎, oppure scrivi la città (es. 'Milano').": "Send your location using the paperclip 📎, or type the city (e.g., 'Milan').",
    "Scrivi lo Slot ID da creare/modificare (es. P1_R1):": "Type the Slot ID to create/modify (e.g., P1_R1):",
    "Scrivi il nome personalizzato per questo Slot (es. 'Orto Nord'):": "Type the custom name for this Slot (e.g., 'North Garden'):",
    "Scrivi l'ID della pianta da assegnare (es. P1):": "Type the Crop ID to assign (e.g., P1):",
    "Scrivi il Device ID da associare (es. RPi_001):": "Type the Device ID to associate (e.g., RPi_001):",
    "Scrivi lo Slot ID da rimuovere (es. P1_R1):": "Type the Slot ID to remove (e.g., P1_R1):",
    "Scrivi l'ID del Dispositivo da aggiungere (es. RPi_001):": "Type the Device ID to add (e.g., RPi_001):",
    "Scrivi l'indirizzo IP locale o hostname (es. 192.168.1.10):": "Type the local IP address or hostname (e.g., 192.168.1.10):",
    "Scrivi l'ID del Dispositivo da rimuovere (es. RPi_001):": "Type the Device ID to remove (e.g., RPi_001):",
    "Scrivi l'ID della pianta da rimuovere (es. P1):": "Type the Crop ID to remove (e.g., P1):",
    "Scrivi il Chat ID dell'utente da aggiungere:": "Type the Chat ID of the user to add:",
    "Scrivi il Chat ID dell'utente da rimuovere:": "Type the Chat ID of the user to remove:",
    "Premi il bottone qui sotto per collegare il tuo profilo telegram!": "Press the button below to link your Telegram profile!",

    "❌ Formato non valido. Usa solo numeri (es. 3, 4).": "❌ Invalid format. Use only numbers (e.g., 3, 4).",
    "❌ Valore non valido.": "❌ Invalid value.",
    "Operazione completata.": "Operation completed.",

    # Technical Logs
    "[BOT] Avviato gestore comandi": "[BOT] Command handler started",
    "[BOT] Telegram command": "[BOT] Telegram command",
    "⚠️ Attenzione: Impossibile connettersi al broker MQTT. Il bot si avvierà lo stesso.": "⚠️ Warning: Unable to connect to MQTT broker. The bot will start anyway.",
    "[BOT] Bot Telegram in ascolto...": "[BOT] Telegram Bot listening...",
    "[MQTT] Connesso al broker MQTT!": "[MQTT] Connected to MQTT broker!",
    "[MQTT] Notifica Ricevuta sul topic": "[MQTT] Notification received on topic",
    "🔔 *NOTIFICA DI SISTEMA* 🔔": "🔔 *SYSTEM NOTIFICATION* 🔔"
}

for it, en in replacements.items():
    content = content.replace(it, en)

with open(file_path, "w", encoding="utf-8") as f:
    f.write(content)
