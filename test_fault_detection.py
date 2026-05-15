#!/usr/bin/env python3
"""
Test Script: Telegram Bot Integration + Fault Detection Service
====================================================================
Tests the complete flow:
1. Turns on a pump (publishes to garden/RPi_test/pump)
2. Sends stagnant moisture data (publishes to garden/RPi_test/telemetry)
3. Waits for Fault Detection to detect the fault
4. Verifies that the Telegram Bot receives the alarm on garden/alerts/faults
"""

import paho.mqtt.client as mqtt
import json
import time
import threading
from datetime import datetime


BROKER_IP = "localhost"  
BROKER_PORT = 1883
TEST_DEVICE = "RPi_test"


TOPIC_PUMP = f"garden/{TEST_DEVICE}/pump"
TOPIC_TELEMETRY = f"garden/{TEST_DEVICE}/telemetry"
TOPIC_ALARMS = "garden/alerts/faults"


alarms_received = []

# ============ CALLBACK MQTT ============
def on_connect(client, userdata, flags, rc):
    """Connection to the broker"""
    if rc == 0:
        print(f"✅ [TEST] Connected to broker {BROKER_IP}:{BROKER_PORT}")
        # Subscribe to alarms to receive notifications
        client.subscribe(TOPIC_ALARMS)
        print(f"📡 Listening on: {TOPIC_ALARMS}")
    else:
        print(f"❌ Connection error: {rc}")

def on_message(client, userdata, msg):
    """Receive MQTT messages"""
    try:
        payload = msg.payload.decode('utf-8')
        print(f"\n🔔 [ALARM RECEIVED] Topic: {msg.topic}")
        print(f"   Payload: {payload}")
        alarms_received.append({
            'topic': msg.topic,
            'payload': payload,
            'time': datetime.now().isoformat()
        })
    except Exception as e:
        print(f"❌ Error parsing message: {e}")

def on_disconnect(client, userdata, rc):
    """Disconnection"""
    if rc != 0:
        print(f"⚠️  Disconnection inattesa: {rc}")
    else:
        print(f"✅ Disconnected successfully")

# ============ FUNZIONI DI TEST ============
def publish_message(client, topic, payload, delay=0):
    """Publish an MQTT message"""
    if delay > 0:
        time.sleep(delay)
    client.publish(topic, json.dumps(payload), qos=1)
    print(f"📤 Published on {topic}")
    print(f"   Payload: {json.dumps(payload)}")

def test_fault_detection(client):
    """Executes the complete test"""
    
    print("\n" + "="*70)
    print("🚀 TEST START: Telegram Bot Integration + Fault Detection")
    print("="*70)
    
    try:
        # ===== STEP 0: ALARM SUBSCRIPTION =====
        print("\n[STEP 0] Subscribing to alarm topics...")
        client.subscribe(TOPIC_ALARMS)
        print(f"✅ Subscribed to: {TOPIC_ALARMS}")
        time.sleep(1)
        
        # ===== STEP 1: TURN ON THE PUMP =====
        print("\n[STEP 1] Turning on the pump...")
        pump_on = [{"n": "pump_status", "v": 1}]
        publish_message(client, TOPIC_PUMP, pump_on, delay=1)
        print("⏱️  Waiting to record moisture baseline...")
        time.sleep(2)
        
        # ===== STEP 2: SEND INITIAL MOISTURE DATA =====
        print("\n[STEP 2] Sending baseline moisture (50%)...")
        telemetry_1 = [{"n": "soil_moisture", "v": 50.0}]
        publish_message(client, TOPIC_TELEMETRY, telemetry_1)
        time.sleep(2)
        
        # ===== STEP 3: WAIT FOR PUMP TIMEOUT (15 seconds) AND COLLECT ALARMS =====
        print("\n[STEP 3] Sending telemetry data without moisture increase...")
        print("⏱️  Fault Detection will wait 15 seconds before triggering alarm...")
        
        # Send telemetry for ~35 seconds to collect alarms
        for i in range(7):
            time.sleep(5)
            # Send moisture still at 50% (no increase!)
            telemetry_update = [{"n": "soil_moisture", "v": 50.0}]
            publish_message(client, TOPIC_TELEMETRY, telemetry_update)
            elapsed = (i + 1) * 5
            print(f"   [{elapsed}s] Stable moisture at 50% - Alarms received: {len(alarms_received)}")
            
            # If alarm received, continue for a few more seconds to collect all
            if len(alarms_received) > 0 and i > 2:
                print(f"✅ ALARM DETECTED after {elapsed} seconds!")
                break
        
        # ===== RESULT =====
        print("\n" + "="*70)
        print("📊 TEST RESULTS")
        print("="*70)
        
        if len(alarms_received) > 0:
            print(f"✅ SUCCESS! Alarms received: {len(alarms_received)}")
            for i, alarm in enumerate(alarms_received, 1):
                print(f"\n   [{i}] Time: {alarm['time']}")
                print(f"       Topic: {alarm['topic']}")
                print(f"       Payload: {alarm['payload']}")
        else:
            print("❌ NO ALARMS RECEIVED!")
            print("\n   Possible causes:")
            print("   1. Fault Detection Service is not running")
            print("   2. The MQTT broker is unreachable")
            print("   3. Incorrect TIMEOUT configuration")
            print("\n   Actions to take:")
            print("   - Verify that Docker containers are running")
            print("   - Check the Fault Detection Service logs")
            print("   - Verify that PUMP_TIMEOUT_SECONDS < 15 in config")
        
        # ===== CLEANUP =====
        print("\n[CLEANUP] Turning off the pump...")
        pump_off = [{"n": "pump_status", "v": 0}]
        publish_message(client, TOPIC_PUMP, pump_off)
        time.sleep(1)
        
    except Exception as e:
        print(f"❌ ERROR during the test: {e}")
        import traceback
        traceback.print_exc()

# ============ MAIN ============
if __name__ == "__main__":
    # Create MQTT client
    global_client = mqtt.Client(client_id="TestClient")
    
    global_client.on_connect = on_connect
    global_client.on_message = on_message
    global_client.on_disconnect = on_disconnect
    
    try:
        # Connect to the broker
        print(f"🔗 Connection to the broker MQTT in corso ({BROKER_IP}:{BROKER_PORT})...")
        global_client.connect(BROKER_IP, BROKER_PORT, keepalive=60)
        
        # Start the background MQTT loop
        global_client.loop_start()
        time.sleep(1)  # Wait for connection
        
        # Run the test
        test_fault_detection(global_client)
        
        # Wait and then disconnect
        time.sleep(2)
        global_client.loop_stop()
        global_client.disconnect()
        
        print("\n✅ Test completed!")
        
    except ConnectionRefusedError:
        print(f"❌ Unable to connect to {BROKER_IP}:{BROKER_PORT}")
        print("\n   Solutions:")
        print("   1. Start Docker compose: docker-compose up -d")
        print("   2. If using WSL/Docker Desktop, verify it is active")
        print("   3. If you want to test locally, install Mosquitto")
    except KeyboardInterrupt:
        print("\n⚠️  Test interrupted by user")
        global_client.loop_stop()
        global_client.disconnect()
    except Exception as e:
        print(f"❌ Critical error: {e}")
        import traceback
        traceback.print_exc()
