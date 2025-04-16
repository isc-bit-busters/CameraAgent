# ble-gates/gate1/bridge.py

import asyncio
import os
from bleak import BleakClient, BleakError
import paho.mqtt.client as mqtt

THINGY_ADDRESS = os.getenv("BLE_ADDRESS", "DF:CB:A0:71:A8:6C")
MQTT_BROKER = os.getenv("MQTT_BROKER", "emqx")
MQTT_PORT = int(os.getenv("MQTT_PORT", "1883"))
MQTT_TOPIC = os.getenv("MQTT_TOPIC", "gate/ir")

IR_CHAR_UUID = "794f1fe3-9be8-4875-83ba-731e1037a883"
LED_CHAR_UUID = "794f1fe3-9be8-4875-83ba-731e1037a882"
RED_COLOR = b"\xFF\x00\x00"
BLUE_COLOR = b"\x00\xFF\x00"
GREEN_BLINK = bytearray([0x03, 0x00, 0xFF, 0x00, 0xFF, 0x32])

mqtt_client = mqtt.Client()
mqtt_client.connect(MQTT_BROKER, MQTT_PORT)
mqtt_client.loop_start()

async def main():
    try:
        async with BleakClient(THINGY_ADDRESS) as client:
            print(f"Connected: {client.is_connected}")

            async def ir_handler(_, data):
                await client.write_gatt_char(LED_CHAR_UUID, GREEN_BLINK)
                if data[0] == 1:
                    print("🔴 Object detected")
                    await client.write_gatt_char(LED_CHAR_UUID, RED_COLOR)
                    mqtt_client.publish(MQTT_TOPIC, "object_detected")
                else:
                    print("🔵 No object detected")
                    await client.write_gatt_char(LED_CHAR_UUID, BLUE_COLOR)
                    mqtt_client.publish(MQTT_TOPIC, "clear")

            await client.start_notify(IR_CHAR_UUID, ir_handler)
            print("IR sensor notifications started.")
            await asyncio.sleep(1E9)
    except Exception as e:
        print(f"Error: {e}")

asyncio.run(main())
