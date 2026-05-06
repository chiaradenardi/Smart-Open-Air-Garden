import os

file_path = "Telegram_Bot/Telegram_Bot.py"

with open(file_path, "r", encoding="utf-8") as f:
    content = f.read()

replacements = {
    # Delete / Remove messages
    "Non ci sono slot nel giardino al momento!": "There are no slots in the garden at the moment!",
    "🗑️ Elimina ": "🗑️ Delete ",
    "⚠️ *Attenzione, operazione irreversibile!*\\nQuale slot vuoi eliminare dal sistema?": "⚠️ *Warning, irreversible operation!*\\nWhich slot do you want to delete from the system?",
    "❌ Impossibile eliminare:": "❌ Unable to delete:",
    "eliminato definitivamente dal sistema.": "permanently deleted from the system.",
    "rimosso dal database.": "removed from the database.",
    "rimossa dal catalogo.": "removed from the catalog.",
    
    # Prices
    "✏️ Modifica Prezzo": "✏️ Edit Price",
    "💶 Il prezzo attuale dell'acqua è:": "💶 The current water price is:",
    "Scrivi il nuovo prezzo dell'acqua (es. 2.5):": "Enter the new water price (e.g. 2.5):",
    "✅ Prezzo aggiornato con successo a": "✅ Price successfully updated to",

    # Devices
    "✅ *Successo!* Il dispositivo": "✅ *Success!* Device",
    "è stato registrato. Ora puoi assegnarlo a uno slot!": "has been registered. You can now assign it to a slot!",
    "Non ci sono dispositivi registrati!": "No devices registered!",
    "⚠️ *Attenzione!* Quale dispositivo vuoi scollegare dal sistema?": "⚠️ *Warning!* Which device do you want to disconnect from the system?",

    # Crops / Plants
    "❌ Formato errato. Inserisci 3 valori: ID, Nome, Soglia (es. P3, Lattuga, 50.0). Riprova con /addplant": "❌ Incorrect format. Enter 3 values: ID, Name, Threshold (e.g. P3, Lettuce, 50.0). Try again with /addplant",
    "❌ La soglia deve essere un numero (es. 50.0). Riprova.": "❌ The threshold must be a number (e.g. 50.0). Try again.",
    "✅ *Successo!* ": "✅ *Success!* ",
    " aggiunta con soglia ": " added with threshold ",
    "Nessuna pianta nel catalogo!": "No crops in the catalog!",
    "⚠️ *Quale pianta vuoi eliminare dal catalogo?*\\n_Nota: Assicurati che non sia attualmente usata in nessuno slot!_": "⚠️ *Which crop do you want to delete from the catalog?*\\n_Note: Make sure it is not currently used in any slot!_",

    # Users
    "🙋‍♂️ Sono ": "🙋‍♂️ I am ",
    "✅ Collegamento riuscito!\\nIl profilo": "✅ Linking successful!\\nThe profile",
    "è ora associato a questo telefono. Riceverai qui tutti gli allarmi del giardino.": "is now associated with this phone. You will receive all garden alarms here.",
    "❌ Formato errato. Riprova con /adduser": "❌ Incorrect format. Try again with /adduser",
    " creato.\\nOra la persona può avviare il bot dal suo telefono e usare il pulsante 'Link Profile (Receive Notifications)'.": " created.\\nThe person can now start the bot from their phone and use the 'Link Profile (Receive Notifications)' button.",
    "Nessun utente nel sistema!": "No users in the system!",
    "⚠️ *Quale utente vuoi eliminare?*": "⚠️ *Which user do you want to delete?*",

    # Locations
    "🌍 *Imposta Città Meteo*\\nScrivi il nome della città (es. `Torino,IT`) o le coordinate (es. `45.07,7.68`):": "🌍 *Set Weather City*\\nEnter the city name (e.g. `Turin,IT`) or coordinates (e.g. `45.07,7.68`):",
    "✅ Posizione meteo aggiornata a:": "✅ Weather location updated to:",
    "📍 Invia la mia posizione GPS": "📍 Send my GPS location",
    "Premi il pulsante qui sotto per inviare le tue coordinate GPS esatte per il servizio Meteo:": "Press the button below to send your exact GPS coordinates for the Weather service:",
    
    # Menus
    "Non ci sono slot configurati al momento nel giardino.": "There are no slots configured in the garden at the moment.",
    "Quale slot vuoi aggiornare?": "Which slot do you want to update?",
    "🌍 *Impostazione Posizione Meteo*\\n\\nPremi il pulsante qui sotto per inviare al sistema le tue coordinate GPS esatte.\\n\\n💡 _Se il giardino si trova in un'altra città, scrivi semplicemente il comando testuale:_\\n`/city NomeCitta,IT` (es. `/city Torino,IT`)": "🌍 *Weather Location Settings*\\n\\nPress the button below to send the system your exact GPS coordinates.\\n\\n💡 _If the garden is located in another city, simply write the textual command:_\\n`/city CityName,IT` (e.g. `/city Turin,IT`)"
}

for it, en in replacements.items():
    content = content.replace(it, en)

with open(file_path, "w", encoding="utf-8") as f:
    f.write(content)
