import asyncio
import edge_tts

TEXT = """Moving on to the Smart Irrigation Service, which acts as the decision-making brain of our system. Instead of relying on hardcoded values, it dynamically queries the Service Catalog to retrieve the specific plant type for each slot and fetch its custom irrigation strategy, determining the exact minimum moisture threshold at runtime. In our live Docker environment, the microservice processes real-time SenML telemetry from the MQTT broker. When soil moisture drops below the threshold, it triggers a weather check. Since no rain is expected, it publishes an MQTT command to start the pump, instantly updating the physical simulator's status to ON. To validate our water-saving logic, we conduct a stress test by mocking a high rainfall forecast of 50 millimeters. Even though the soil is dry, the service detects the upcoming rain through the weather adapter and successfully bypasses irrigation, outputting a 'SKIP' status to prevent resource waste."""

VOICE = "en-US-AriaNeural"
OUTPUT_FILE = "speech_10_minuti.mp3"

async def generate_speech():
    communicate = edge_tts.Communicate(TEXT, VOICE)
    await communicate.save(OUTPUT_FILE)
    print(f"File salvato con successo: {OUTPUT_FILE}")

if __name__ == "__main__":
    asyncio.run(generate_speech())
