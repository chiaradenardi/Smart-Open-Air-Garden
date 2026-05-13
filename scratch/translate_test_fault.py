import os

file_path = "/Users/davidechila/Desktop/progettoIoT/Smart-Open-Air-Garden/test_fault_detection.py"

with open(file_path, "r", encoding="utf-8") as f:
    content = f.read()

replacements = {
    "Script di Test: Integrazione Telegram Bot + Fault Detection Service": "Test Script: Telegram Bot Integration + Fault Detection Service",
    "Testa il flusso completo:": "Tests the complete flow:",
    "1. Accende una pompa (pubblica su": "1. Turns on a pump (publishes to",
    "2. Invia dati di umidità stagnanti (pubblica su": "2. Sends stagnant moisture data (publishes to",
    "3. Attende che Fault Detection rilevi il guasto": "3. Waits for Fault Detection to detect the fault",
    "4. Verifica che Telegram Bot riceva l'allarme su": "4. Verifies that the Telegram Bot receives the alarm on",
    "Connessione al broker": "Connection to the broker",
    "✅ [TEST] Connesso al broker": "✅ [TEST] Connected to broker",
    "Iscriviti agli allarmi per ricevere le notifiche": "Subscribe to alarms to receive notifications",
    "📡 In ascolto su:": "📡 Listening on:",
    "❌ Errore connessione:": "❌ Connection error:",
    "Ricevi messaggi MQTT": "Receive MQTT messages",
    "🔔 [ALLARME RICEVUTO] Topic:": "🔔 [ALARM RECEIVED] Topic:",
    "❌ Errore nel parsing messaggio:": "❌ Error parsing message:",
    "Disconnessione": "Disconnection",
    "⚠️  Disconnessione inattesa:": "⚠️  Unexpected disconnection:",
    "✅ Disconnesso correttamente": "✅ Disconnected successfully",
    "Pubblica un messaggio MQTT": "Publish an MQTT message",
    "📤 Pubblicato su": "📤 Published on",
    "Esegue il test completo": "Executes the complete test",
    "🚀 INIZIO TEST: Integrazione Telegram Bot + Fault Detection": "🚀 TEST START: Telegram Bot Integration + Fault Detection",
    "SOTTOSCRIZIONE AGLI ALLARMI": "ALARM SUBSCRIPTION",
    "[STEP 0] Sottoscrizione ai topic di allarme...": "[STEP 0] Subscribing to alarm topics...",
    "✅ Sottoscritto a:": "✅ Subscribed to:",
    "ACCENDI LA POMPA": "TURN ON THE PUMP",
    "[STEP 1] Accensione pompa in corso...": "[STEP 1] Turning on the pump...",
    "⏱️  Attesa registrazione baseline umidità...": "⏱️  Waiting to record moisture baseline...",
    "INVIA DATI INIZIALI DI UMIDITÀ": "SEND INITIAL MOISTURE DATA",
    "[STEP 2] Invio baseline umidità": "[STEP 2] Sending baseline moisture",
    "ATTENDI POMPA TIMEOUT (15 secondi) E RACCOGLI ALLARMI": "WAIT FOR PUMP TIMEOUT (15 seconds) AND COLLECT ALARMS",
    "[STEP 3] Invio dati telemetry senza aumento umidità...": "[STEP 3] Sending telemetry data without moisture increase...",
    "⏱️  Fault Detection attenderà 15 secondi prima di attivare allarme...": "⏱️  Fault Detection will wait 15 seconds before triggering alarm...",
    "Invia telemetry per ~35 secondi per raccogliere allarmi": "Send telemetry for ~35 seconds to collect alarms",
    "Invia umidità ancora a 50% (nessun aumento!)": "Send moisture still at 50% (no increase!)",
    "Umidità stabile a 50% - Allarmi ricevuti:": "Stable moisture at 50% - Alarms received:",
    "Se allarme ricevuto, continua per pochi secondi in più per raccoglierli tutti": "If alarm received, continue for a few more seconds to collect all",
    "✅ ALLARME RILEVATO dopo": "✅ ALARM DETECTED after",
    "📊 RISULTATI DEL TEST": "📊 TEST RESULTS",
    "✅ SUCCESSO! Allarmi ricevuti:": "✅ SUCCESS! Alarms received:",
    "❌ NESSUN ALLARME RICEVUTO!": "❌ NO ALARMS RECEIVED!",
    "Possibili cause:": "Possible causes:",
    "1. Fault Detection Service non sta girando": "1. Fault Detection Service is not running",
    "2. Il broker MQTT non è raggiungibile": "2. The MQTT broker is unreachable",
    "3. Configurazione TIMEOUT non corretta": "3. Incorrect TIMEOUT configuration",
    "Azioni da fare:": "Actions to take:",
    "- Verifica che i container Docker siano in esecuzione": "- Verify that Docker containers are running",
    "- Controlla i log del Fault Detection Service": "- Check the Fault Detection Service logs",
    "- Verifica che PUMP_TIMEOUT_SECONDS < 15 nel config": "- Verify that PUMP_TIMEOUT_SECONDS < 15 in config",
    "Spegnimento della pompa...": "Turning off the pump...",
    "❌ ERRORE durante il test:": "❌ ERROR during the test:",
    "Crea client MQTT - Compatibile con entrambe le versioni di paho-mqtt": "Create MQTT client - Compatible with both paho-mqtt versions",
    "Prova con la nuova API (versione > 1.6)": "Try with the new API (version > 1.6)",
    "Se fallisce, usa l'API vecchia": "If it fails, use the old API",
    "Connetti al broker": "Connect to the broker",
    "🔗 Connessione al broker MQTT in corso": "🔗 Connecting to MQTT broker",
    "Avvia il loop MQTT in background": "Start the background MQTT loop",
    "Attendi connessione": "Wait for connection",
    "Esegui il test": "Run the test",
    "Attendi e poi disconnetti": "Wait and then disconnect",
    "✅ Test completato!": "✅ Test completed!",
    "❌ Impossibile connettersi a": "❌ Unable to connect to",
    "Soluzioni:": "Solutions:",
    "1. Avvia Docker compose: docker-compose up -d": "1. Start Docker compose: docker-compose up -d",
    "2. Se usi WSL/Docker Desktop, verifica che sia attivo": "2. If using WSL/Docker Desktop, verify it is active",
    "3. Se vuoi testare localmente, installa Mosquitto": "3. If you want to test locally, install Mosquitto",
    "⚠️  Test interrotto dall'utente": "⚠️  Test interrupted by user",
    "❌ Errore critico:": "❌ Critical error:",
    "secondi": "seconds"
}

for it, en in replacements.items():
    content = content.replace(it, en)

with open(file_path, "w", encoding="utf-8") as f:
    f.write(content)

print("Translations applied successfully.")
