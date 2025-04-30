import asyncio
import os
import time
import json
from bleak import BleakClient, BleakScanner, BleakError
import paho.mqtt.client as mqtt

from asyncio import Lock
RECONNECT_LOCKS = {}
BLE_CONNECTION_LOCK = Lock()
GATES_UPDATE_LOCK = Lock()

GATES = []
connected_clients = []

MQTT_BROKER = os.getenv("MQTT_BROKER", "emqx")
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
    print(f"🔗 Connected to EMQX with result code {rc}", flush=True)
    if rc == 0:
        client.subscribe("gate/mac_config") 
    else:
        print("❌ Failed to connect to MQTT broker.", flush=True)

def on_message(client, userdata, msg):
    print(f"📩 Received on {msg.topic}: {msg.payload.decode()}", flush=True)
    if msg.topic == "gate/mac_config":
        asyncio.run_coroutine_threadsafe(
            update_gates_from_config(msg.payload.decode(), userdata["mqtt_client"]),
            userdata["loop"]
        )

async def wait_for_broker(host, port, timeout=30):
    print(f"🔌 Waiting for MQTT broker at {host}:{port}...", flush=True)
    for _ in range(timeout):
        try:
            reader, writer = await asyncio.open_connection(host, port)
            writer.close()
            await writer.wait_closed()
            print("✅ MQTT broker reachable.", flush=True)
            return
        except Exception:
            print("⏳ MQTT not ready, retrying...", flush=True)
            await asyncio.sleep(2)
    raise RuntimeError("❌ MQTT broker unreachable after timeout.")

async def handle_gate(gate, mqtt_client):
    address = gate["address"].upper()
    name = gate["name"]

    if gate["address"] not in RECONNECT_LOCKS:
        RECONNECT_LOCKS[gate["address"]] = Lock()

    async def connect_and_subscribe():
        print(f"🔌 Attempting connection to {name}", flush=True)
        reconnect_task = None
        connected_once = False
        disconnected_sent = False
        await wait_for_ble_device(address, name)
        await asyncio.sleep(1)

        def on_disconnect(_):
            nonlocal reconnect_task
            nonlocal disconnected_sent
            
            if not connected_once or disconnected_sent:
                return
            
            mqtt_client.publish(gate["topic"], "disconnected")
            disconnected_sent = True
            
            if reconnect_task is None or reconnect_task.done():
                reconnect_task = asyncio.create_task(reconnect())

        client = BleakClient(address, timeout=30.0, disconnected_callback=on_disconnect)

        if client.is_connected:
            print(f"🔄 Already connected to {name}, skipping reconnection.", flush=True)
            return client
        
        async def ir_handler(_, data):
            state = data[0]
            print(f"[{name}] IR State: {state}", flush=True)
            color = GREEN_COLOR if state == 1 else BLUE_COLOR
            message = "object_detected" if state == 1 else "clear"
            try:
                if client.is_connected:
                    await client.write_gatt_char(LED_CHAR_UUID, color, response=False)
            except Exception as e:
                print(f"⚠️ LED write failed: {e}", flush=True)
            print(f"📤 Publishing to {gate['topic']}: {message}", flush=True)
            mqtt_client.publish(gate["topic"], message)

        async def reconnect():
            nonlocal client
            nonlocal disconnected_sent
            async with RECONNECT_LOCKS[address]:
                await asyncio.sleep(5)
                while True:
                    try:
                        print(f"🔄 Reconnecting to {name}...", flush=True)
                        if client.is_connected:
                            print(f"🔁 Already connected to {name}. Skipping reconnect.", flush=True)
                            return
                        try:
                            await client.disconnect()
                        except Exception as e:
                            print(f"⚠️ Failed to disconnect from {name} : {e}", flush=True)

                        async with BLE_CONNECTION_LOCK:
                            await wait_for_ble_device(address, name)
                            new_client = BleakClient(address, timeout=30.0, disconnected_callback=on_disconnect)
                            await new_client.connect()

                        if new_client.is_connected:
                            print(f"🔗 Reconnected to {name}", flush=True)
                            await new_client.write_gatt_char(LED_CHAR_UUID, RED_COLOR, response=False)
                            await new_client.start_notify(IR_CHAR_UUID, ir_handler)
                            client = new_client
                            mqtt_client.publish(gate["topic"], "reconnected")
                            disconnected_sent = False
                            return
                    except Exception as e:
                        if "InProgress" in str(e):
                            print(f"⚠️ BlueZ busy for {name}, retrying in 10s...", flush=True)
                            await asyncio.sleep(10)
                        else:
                            print(f"🔁 Retry failed for {name}: {e}", flush=True)
                            await asyncio.sleep(5)

        try:
            async with BLE_CONNECTION_LOCK:
                await client.connect()

            if not client.is_connected:
                print(f"❌ Failed to connect to {name}. Retrying...", flush=True)
                await reconnect()
                return None

            print(f"🔗 Connected to {name}", flush=True)
            await client.write_gatt_char(LED_CHAR_UUID, RED_COLOR, response=False)

            await client.start_notify(IR_CHAR_UUID, ir_handler)
            print(f"📱 Listening for IR on {name}...", flush=True)
            connected_once = True
            mqtt_client.publish(gate["topic"], "connected")
            return client

        except Exception as e:
            print(f"❌ Exception during connection to {name}: {e}", flush=True)
            await reconnect()
            return None

    return await connect_and_subscribe()


async def wait_for_ble_device(address, name, timeout=60):
    print(f"🔍 Waiting for BLE device {name} ({address}) to appear...", flush=True)
    start = time.time()
    while True:
        if time.time() - start > timeout:
            raise TimeoutError(f"⏰ Timeout: {name} not found after {timeout} seconds.")

        devices = await BleakScanner.discover(timeout=5.0)
        for d in devices:
            if d.address.upper() == address:
                print(f"✅ Found {name} [{d.address}]", flush=True)
                return
        print(f"🔄 Still scanning for {name}...", flush=True)
        await asyncio.sleep(2)

async def update_gates_from_config(config_message, mqtt_client):
    global GATES, connected_clients

    async with GATES_UPDATE_LOCK:
        try:
            new_gates = json.loads(config_message)
            if isinstance(new_gates, dict):
                new_gates = [new_gates]

            if isinstance(new_gates, list):
                print(f"🛠️ Adding {len(new_gates)} new gate(s)...", flush=True)
                mqtt_client.publish("gate/mac_config/ack", f"✅ Received {len(new_gates)} gate(s).")
                for gate in new_gates:
                    address = gate["address"].upper()
                    if not any(g["address"].upper() == address for g in GATES):
                        GATES.append(gate)
                        print(f"➕ Added gate: {gate}", flush=True)

                        client = await handle_gate(gate, mqtt_client)
                        if client:
                            connected_clients.append(client)
                    else:
                        print(f"⚠️ Gate {address} already exists. Skipping.", flush=True)
            else:
                print("❌ Config received is not a list or object.", flush=True)
                mqtt_client.publish("gate/mac_config/ack", "❌ Invalid config format")
        except json.JSONDecodeError as e:
            print(f"❌ Failed to parse config: {e}", flush=True)
            mqtt_client.publish("gate/mac_config/ack", "❌ Invalid JSON format")

async def main():
    await wait_for_broker(MQTT_BROKER, MQTT_PORT)

    mqtt_client = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2, client_id="gate-monitor")
    mqtt_client.user_data_set({"mqtt_client": mqtt_client})
    mqtt_client.enable_logger()
    if MQTT_USERNAME and MQTT_PASSWORD:
        mqtt_client.username_pw_set(MQTT_USERNAME, MQTT_PASSWORD)

    mqtt_client.on_connect = on_connect
    mqtt_client.on_message = on_message

    loop = asyncio.get_running_loop()
    mqtt_client.user_data_set({"mqtt_client": mqtt_client, "loop": loop})

    mqtt_client.connect(MQTT_BROKER, MQTT_PORT)
    mqtt_client.loop_start()

    print("🚀 Connecting to gates sequentially and waiting for events", flush=True)
    connected_clients = []

    for gate in GATES:
        client = await handle_gate(gate, mqtt_client)
        if client:
            connected_clients.append(client)
        await asyncio.sleep(3)  # avoid BlueZ connection overlap

    while True:
        await asyncio.sleep(1)

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except Exception as e:
        print(f"❌ Exception occurred: {e}", flush=True)
