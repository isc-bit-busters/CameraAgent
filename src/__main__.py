import asyncio

from src.camera_agent import CameraAgent


async def main():
    sender_jid = "agent@localhost"
    sender_password = "top_secret"
    receiver_jid = "receiver@localhost/spade"

    # Instantiate camera agent
    sender = CameraAgent(sender_jid, sender_password)
    sender.receiver_jid = receiver_jid

    # Start the camera agent
    await sender.start(auto_register=True)

    # Confirm agent is running
    if not sender.is_alive():
        print("Camera agent couldn't connect. Check Prosody configuration.")
        await sender.stop()
        return

    print("Camera agent connected successfully. Running...")

    try:
        while sender.is_alive():
            await asyncio.sleep(1)
    except KeyboardInterrupt:
        print("Shutting down agent...")
    finally:
        # Clean up: stop the agent
        await sender.stop()


if __name__ == "__main__":
    asyncio.run(main())
