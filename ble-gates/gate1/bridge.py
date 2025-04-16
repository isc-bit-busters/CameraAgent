import asyncio
import os
import time
import socket
from bleak import BleakClient, BleakScanner, BleakError
import paho.mqtt.client as mqtt

THINGY_ADDRESS = os.getenv("BLE_ADDRESS", "DF:CB:A0:71:A8:6C")
MQTT_BROKER = os.getenv("MQTT_BROKER", "emqx")
MQTT_PORT = int(os.getenv("MQTT_PORT", "1883"))
MQTT_TOPIC = os.getenv("MQTT_TOPIC", "gate/ir")

IR_CHAR_UUID = "794f1fe3-9be8-4875-83ba-731e1037a883"
LED_CHAR_UUID = "794f1fe3-9be8-4875-83ba-731e1037a882"
RED_COLOR = b"\xFF\x00\x00"
BLUE_COLOR = b"\x00\x00\xFF"
GREEN_COLOR = b"\x00\xFF\x00"


def wait_for_broker(host, port, timeout=30):
    print(f"\U0001F50C Waiting for MQTT broker at {host}:{port}...")
    start = time.time()
    while time.time() - start < timeout:
        try:
            with socket.create_connection((host, port), timeout=2):
                print("✅ MQTT broker is reachable.")
                return
        except OSError:
            print("⏳ MQTT broker not ready, retrying...")
            time.sleep(2)
    raise RuntimeError("❌ MQTT broker not reachable after waiting.")


async def wait_for_ble_device(address, timeout=60):
    print(f"🔍 Waiting for BLE device {address} to appear...")
    start_time = time.time()
    while time.time() - start_time < timeout:
        try:
            devices = await BleakScanner.discover(timeout=5.0)
            for d in devices:
                if d.address.upper() == address.upper():
                    print(f"✅ Found BLE device: {d.name} [{d.address}]")
                    return
        except Exception as e:
            print(f"⚠️ BLE scan failed: {e}")
        print("🔄 Still scanning...")
    raise RuntimeError(f"❌ BLE device {address} not found after waiting.")


async def main():
    wait_for_broker(MQTT_BROKER, MQTT_PORT)

    mqtt_client = mqtt.Client()
    mqtt_client.connect(MQTT_BROKER, MQTT_PORT)
    mqtt_client.loop_start()

    await wait_for_ble_device(THINGY_ADDRESS)

    try:
        async with BleakClient(THINGY_ADDRESS) as client:
            print(f"🔗 Connected to BLE device: {client.is_connected}")

            async def ir_handler(_, data):
                if data[0] == 1:
                    print("🟢 Object detected")
                    await client.write_gatt_char(LED_CHAR_UUID, GREEN_COLOR)
                    mqtt_client.publish(MQTT_TOPIC, "object_detected")
                else:
                    print("🔵 No object detected")
                    await client.write_gatt_char(LED_CHAR_UUID, BLUE_COLOR)
                    mqtt_client.publish(MQTT_TOPIC, "clear")

            await client.start_notify(IR_CHAR_UUID, ir_handler)
            print("✅ IR sensor notifications started.")
            await asyncio.sleep(1e9)  # run forever
    except BleakError as e:
        print(f"❌ BLE Error: {e}")
    except Exception as e:
        print(f"❌ Unexpected Error: {e}")


if __name__ == "__main__":
    asyncio.run(main())
