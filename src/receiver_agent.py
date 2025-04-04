import base64
import aiofiles
from spade import agent, behaviour

class ReceiverAgent(agent.Agent):
    class ReceivePhotoBehaviour(behaviour.CyclicBehaviour):
        async def run(self):
            msg = await self.receive(timeout=10)
            if msg:
                print("Received photo message.")
                img_data = base64.b64decode(msg.body)

                # Save the received image
                async with aiofiles.open("received_photo.jpg", "wb") as img_file:
                    await img_file.write(img_data)

                print("Photo saved as 'received_photo.jpg'.")

    async def setup(self):
        print(f"{self.jid} is ready.")
        self.add_behaviour(self.ReceivePhotoBehaviour())
