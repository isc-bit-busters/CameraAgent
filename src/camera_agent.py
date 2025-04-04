import cv2
import asyncio
import base64
import aiofiles
from spade import agent, behaviour
from spade.message import Message


class CameraAgent(agent.Agent):
    class SendPhotoBehaviour(behaviour.OneShotBehaviour):
        async def run(self):
            print("Capturing image...")
            camera = cv2.VideoCapture(0, cv2.CAP_DSHOW)

            await asyncio.sleep(2)

            ret, frame = camera.read()

            if not ret:
                print("Failed to capture image.")
                return


            filename = "photo.jpg"
            cv2.imwrite(filename, frame)

            async with aiofiles.open(filename, "rb") as img_file:
                img_data = await img_file.read()
                encoded_img = base64.b64encode(img_data).decode("utf-8")

            msg = Message(to=self.agent.receiver_jid)
            msg.set_metadata("performative", "inform")
            msg.body = encoded_img

            await self.send(msg)
            print("Photo sent.")
            
    class WaitForRequestBehaviour(behaviour.CyclicBehaviour):
        async def run(self):
            msg = await self.receive(timeout=10)
            if msg:
                print("Received camera image request.")
                self.agent.add_behaviour(self.agent.SendPhotoBehaviour())

    async def setup(self):
        print(f"{self.jid} is ready.")
        # Instead of immediately sending a photo, wait for requests
        self.add_behaviour(self.WaitForRequestBehaviour())
