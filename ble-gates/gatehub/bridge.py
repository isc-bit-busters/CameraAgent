import asyncio
import os
from bleak import BleakClient, BleakScanner
import paho.mqtt.client as mqtt

GATE_1 = {
    "name": "gate1",
    "address": "DF:66:32:49:C8:1A",
    "topic": "gate1/ir"
}

GATE_2 = {
    "name": "gate2",
    "address": "D0:31:D0:79:F2:F3",
    "topic": "gate2/ir"
}

MQTT_BROKER = os.getenv("MQTT_BROKER", "localhost")
MQTT_PORT = int(os.getenv("MQTT_PORT", "1883"))

IR_CHAR_UUID = "794f1fe3-9be8-4875-83ba-731e1037a883"
LED_CHAR_UUID = "794f1fe3-9be8-4875-83ba-731e1037a882"
GREEN_COLOR = b"\x00\xFF\x00"
BLUE_COLOR = b"\x00\x00\xFF"


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


import time

async def wait_for_ble_device(address, name, timeout=60):
    print(f"🔍 Waiting for BLE device {name} ({address}) to appear...",flush=True)
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



async def monitor_gate(gate, mqtt_client):
    await wait_for_ble_device(gate["address"].upper(), gate["name"])

    event = asyncio.Event()

    async def ir_handler(_, data):
        state = data[0]
        print(f"[{gate['name']}] IR State: {state}")
        color = GREEN_COLOR if state == 1 else BLUE_COLOR
        message = "object_detected" if state == 1 else "clear"
        mqtt_client.publish(gate["topic"], message)
        await client.write_gatt_char(LED_CHAR_UUID, color)

        if state == 1:
            print(f"🚦 {gate['name']} triggered")
            event.set()

    async with BleakClient(gate["address"].upper()) as client:
        print(f"🔗 Connected to {gate['name']}")
        await client.start_notify(IR_CHAR_UUID, ir_handler)
        print(f"📡 Listening for IR on {gate['name']}...")
        await event.wait()
        await client.stop_notify(IR_CHAR_UUID)
        print(f"✅ Done with {gate['name']}")
        await asyncio.sleep(1)


async def main():
    await wait_for_broker(MQTT_BROKER, MQTT_PORT)

    mqtt_client = mqtt.Client()
    mqtt_client.connect(MQTT_BROKER, MQTT_PORT)
    mqtt_client.loop_start()

    print("🚀 Starting gate sequence")

    # Monitor gate 1, then gate 2
    await monitor_gate(GATE_1, mqtt_client)
    await monitor_gate(GATE_2, mqtt_client)

    print("✅ Robot passed through both gates!")


if __name__ == "__main__":
    asyncio.run(main())