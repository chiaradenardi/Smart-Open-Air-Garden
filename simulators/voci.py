import asyncio
import edge_tts

TEXT = """Now, let's see how the Service Catalog actively enforces strict architectural invariance. Here, we create a new First Floor Garden with a custom five-by-five grid. Next, we try to assign an already-registered gateway, RPi 001, to this new garden. As you can see, the catalog instantly blocks this request. Looking at the Service Catalog code, we can see exactly why: the REST endpoint scans all registered gardens to ensure the device is unique. This backend check acts as our Single Source of Truth, guaranteeing a strict one-to-one mapping between microcontrollers and physical zones, and preventing catastrophic MQTT topic conflicts."""

VOICE = "en-US-AriaNeural"
OUTPUT_FILE = "speech_10_minuti.mp3"

async def generate_speech():
    communicate = edge_tts.Communicate(TEXT, VOICE)
    await communicate.save(OUTPUT_FILE)
    print(f"File salvato con successo: {OUTPUT_FILE}")

if __name__ == "__main__":
    asyncio.run(generate_speech())
