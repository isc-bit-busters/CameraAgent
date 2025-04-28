import asyncio
import os
import signal

from src.camera_agent import CameraAgent

async def main():
    shutdown_event = asyncio.Event()
    def handle_signal(sig, frame):
        shutdown_event.set()

    # Register signal handlers
    signal.signal(signal.SIGINT, handle_signal)
    signal.signal(signal.SIGTERM, handle_signal)

    xmpp_server = os.environ.get("XMPP_SERVER", "prosody")
    xmpp_username = os.environ.get("XMPP_USERNAME", "camera_agent")
    xmpp_password = os.environ.get("XMPP_PASSWORD", "top_secret")
    
    sender_jid = f"{xmpp_username}@{xmpp_server}"
    sender_password = xmpp_password
    
    print(f"Connecting with JID: {sender_jid}")

    sender = CameraAgent(sender_jid, sender_password)

    await sender.start(auto_register=True)

    if not sender.is_alive():
        print("Camera agent couldn't connect. Check Prosody configuration.")
        await sender.stop()
        return

    print("Camera agent connected successfully. Running...")

    try:
        # Wait for shutdown signal
        while sender.is_alive() and not shutdown_event.is_set():
            await asyncio.sleep(1)
    finally:
        print("Cleaning up...")
        await sender.stop()


if __name__ == "__main__":
    asyncio.run(main())
