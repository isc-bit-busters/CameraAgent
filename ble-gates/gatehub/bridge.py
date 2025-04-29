import asyncio
import os
import time
from bleak import BleakClient, BleakScanner, BleakError
import paho.mqtt.client as mqtt

# Define all gates
GATES = [
    {"name": "s1", "address": "DF:CB:A0:71:A8:6C", "topic": "gate1/ir"},
    {"name": "e1", "address": "DF:66:32:49:C8:1A", "topic": "gate2/ir"},
    {"name": "s2", "address": "FC:32:FA:4B:42:DE", "topic": "gate3/ir"},
    {"name": "e2", "address": "D7:09:01:AC:78:08", "topic": "gate4/ir"},
]

MQTT_BROKER = os.getenv("MQTT_BROKER", "localhost")
MQTT_PORT = int(os.getenv("MQTT_PORT", "1883"))
MQTT_USERNAME = os.getenv("MQTT_USERNAME")
MQTT_PASSWORD = os.getenv("MQTT_PASSWORD")

IR_CHAR_UUID = "794f1fe3-9be8-4875-83ba-731e1037a883"
LED_CHAR_UUID = "794f1fe3-9be8-4875-83ba-731e1037a882"
RED_COLOR = b"\xFF\x00\x00"
GREEN_COLOR = b"\x00\xFF\x00"
BLUE_COLOR = b"\x00\x00\xFF"

# MQTT Callbacks
def on_connect(client, userdata, flags, rc, properties=None):
    print(f"🔗 Connected to EMQX with result code {rc}")
    if rc == 0:
        client.subscribe("test/topic")
    else:
        print("❌ Failed to connect to MQTT broker.")

def on_message(client, userdata, msg):
    print(f"📩 Received on {msg.topic}: {msg.payload.decode()}")

async def wait_for_broker(host, port, timeout=30):
    print(f"🔌 Waiting for MQTT broker at {host}:{port}...")
    for _ in range(timeout):
        try:
            reader, writer = await asyncio.open_connection(host, port)
            writer.close()
            await writer.wait_closed()
            print("✅ MQTT broker reachable.")
            return
        except Exception:
            print("⏳ MQTT not ready, retrying...")
            await asyncio.sleep(2)
    raise RuntimeError("❌ MQTT broker unreachable after timeout.")

async def connect_and_listen(gate, mqtt_client):
    try:
        await wait_for_ble_device(gate["address"].upper(), gate["name"])
        await asyncio.sleep(1)
        client = BleakClient(gate["address"].upper(), timeout=30.0)
        await client.connect()

        if client.is_connected:
            print(f"🔗 Connected to {gate['name']}")
            await client.write_gatt_char(LED_CHAR_UUID, RED_COLOR, response=False)

            async def ir_handler(_, data):
                state = data[0]
                print(f"[{gate['name']}] IR State: {state}")
                color = GREEN_COLOR if state == 1 else BLUE_COLOR
                message = "object_detected" if state == 1 else "clear"
                try:
                    if client.is_connected:
                        await client.write_gatt_char(LED_CHAR_UUID, color, response=False)
                except Exception as e:
                    print(f"⚠️ LED write failed: {e}")
                print(f"📤 Publishing to {gate['topic']}: {message}")
                mqtt_client.publish(gate["topic"], message)

            await client.start_notify(IR_CHAR_UUID, ir_handler)
            print(f"📱 Listening for IR on {gate['name']}...")
            return client
        else:
            print(f"❌ Could not connect to {gate['name']}")
    except Exception as e:
        print(f"❌ Failed to connect to {gate['name']}: {e}")
    return None

async def wait_for_ble_device(address, name, timeout=60):
    print(f"🔍 Waiting for BLE device {name} ({address}) to appear...", flush=True)
    start = time.time()
    while True:
        if time.time() - start > timeout:
            raise TimeoutError(f"⏰ Timeout: {name} not found after {timeout} seconds.")

        devices = await BleakScanner.discover(timeout=5.0)
        for d in devices:
            if d.address.upper() == address:
                print(f"✅ Found {name} [{d.address}]")
                return
        print(f"🔄 Still scanning for {name}...")
        await asyncio.sleep(2)

async def main():
    await wait_for_broker(MQTT_BROKER, MQTT_PORT)

    mqtt_client = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2, client_id="gate-monitor")
    mqtt_client.enable_logger()
    if MQTT_USERNAME and MQTT_PASSWORD:
        mqtt_client.username_pw_set(MQTT_USERNAME, MQTT_PASSWORD)

    mqtt_client.on_connect = on_connect
    mqtt_client.on_message = on_message

    mqtt_client.connect(MQTT_BROKER, MQTT_PORT)
    mqtt_client.loop_start()

    mqtt_client.publish("test/topic", "🚀 MQTT is working")
    print("📱 Test MQTT message sent to test/topic")

    print("🚀 Connecting to gates sequentially and waiting for events")
    connected_clients = []

    for gate in GATES:
        client = await connect_and_listen(gate, mqtt_client)
        if client:
            connected_clients.append(client)
        await asyncio.sleep(3)  # avoid BlueZ connection overlap

    while True:
        await asyncio.sleep(1)

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except Exception as e:
        print(f"❌ Exception occurred: {e}")
